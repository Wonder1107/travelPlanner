from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.agents.workflow import run_planner_agent, run_replanner_agent
from app.db import (
    create_decision_feedback,
    create_itinerary_version,
    create_log,
    create_trip,
    get_itinerary_version,
    get_latest_version_id,
    get_log,
    get_trip,
    init_db,
    list_itinerary_versions,
    list_logs,
    update_trip,
)
from app.llm.client import LLMProvider
from app.schemas import (
    AgentLogItem,
    AgentLogsResponse,
    DecisionFeedbackRequest,
    DecisionFeedbackResponse,
    ItineraryRollbackResponse,
    ItineraryVersionItem,
    ItineraryVersionsResponse,
    ReplanConfigResponse,
    TripCreateRequest,
    TripCreateResponse,
    TripEventRequest,
    TripEventResponse,
    TripResponse,
)
from app.services.replan_policy import get_replan_policy
from app.tools.rag_tools import POIRetriever
from app.tools.weather_tools import fetch_weather_snapshot

app = FastAPI(title="Dynamic Smart Itinerary Engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = POIRetriever()
llm_provider = LLMProvider()


def _create_log(
    *,
    trip_id: str,
    stage: str,
    tool_name: str,
    message: str,
    payload: dict | None = None,
) -> str:
    log_id = str(uuid4())
    create_log(
        log_id=log_id,
        trip_id=trip_id,
        stage=stage,
        tool_name=tool_name,
        message=message,
        payload=payload,
    )
    return log_id


def _pick_itinerary_location(itinerary: dict[str, Any]) -> tuple[float, float] | None:
    for day in itinerary.get("days", []):
        for item in day.get("items", []):
            try:
                lat = float(item.get("lat"))
                lng = float(item.get("lng"))
                return lat, lng
            except (TypeError, ValueError):
                continue
    return None


def _fetch_weather_snapshot_sync(lat: float, lng: float) -> dict[str, Any]:
    try:
        return asyncio.run(fetch_weather_snapshot(lat, lng))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(fetch_weather_snapshot(lat, lng))
        finally:
            loop.close()


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    retriever.build_index()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds")}


@app.post("/api/trips", response_model=TripCreateResponse)
def create_trip_api(request: TripCreateRequest) -> TripCreateResponse:
    trip_id = str(uuid4())
    first_log_id = _create_log(
        trip_id=trip_id,
        stage="planner",
        tool_name="onboarding",
        message="Received onboarding preferences for itinerary generation.",
        payload=request.model_dump(),
    )
    candidates = retriever.search(
        request.preferences,
        city=request.city,
        context=request.travel_note or "",
        top_k=max(12, request.days * 8),
    )
    itinerary, rationale = run_planner_agent(
        request=request.model_dump(),
        candidates=candidates,
        log=lambda stage, tool, message, payload: _create_log(
            trip_id=trip_id,
            stage=stage,
            tool_name=tool,
            message=message,
            payload=payload,
        ),
    )
    create_trip(
        trip_id=trip_id,
        city=request.city,
        days=request.days,
        budget_level=request.budget_level,
        preferences=request.preferences,
        avoid=request.avoid,
        pace=request.pace,
        itinerary=itinerary,
        rationale=rationale,
    )
    create_itinerary_version(
        trip_id=trip_id,
        version_id=1,
        itinerary=itinerary,
        diff_summary="Initial itinerary created.",
    )
    _create_log(
        trip_id=trip_id,
        stage="planner",
        tool_name="planner_done",
        message="Initial itinerary was stored.",
        payload={"trip_id": trip_id, "itinerary_version": 1},
    )
    return TripCreateResponse(
        trip_id=trip_id,
        itinerary=itinerary,
        rationale=rationale,
        agent_log_id=first_log_id,
    )


@app.get("/api/trips/{trip_id}", response_model=TripResponse)
def get_trip_api(trip_id: str) -> TripResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse(
        trip_id=row.id,
        itinerary=json.loads(row.itinerary_json),
        rationale=row.rationale,
    )


@app.post("/api/trips/{trip_id}/events", response_model=TripEventResponse)
def event_trip_api(trip_id: str, request: TripEventRequest) -> TripEventResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    itinerary = json.loads(row.itinerary_json)
    preferences = json.loads(row.preferences_json)
    payload = dict(request.payload)

    event_location: tuple[float, float] | None = None
    if request.location is not None:
        event_location = (float(request.location.lat), float(request.location.lng))
    else:
        event_location = _pick_itinerary_location(itinerary)

    if request.source == "system" and request.event_type == "weather" and not payload.get("condition") and event_location is not None:
        weather_payload = _fetch_weather_snapshot_sync(event_location[0], event_location[1])
        payload = {**weather_payload, **payload}

    event_dict = request.model_dump()
    event_dict["payload"] = payload

    _create_log(
        trip_id=trip_id,
        stage="monitor",
        tool_name=request.event_type,
        message="Received event for potential replanning.",
        payload=event_dict,
    )
    candidates = retriever.search(
        preferences,
        city=row.city,
        context=json.dumps(payload),
        top_k=12,
    )
    updated_itinerary, alerts, rationale, decision, meta = run_replanner_agent(
        itinerary=itinerary,
        event=event_dict,
        preferences=preferences,
        candidates=candidates,
        log=lambda stage, tool, message, payload: _create_log(
            trip_id=trip_id,
            stage=stage,
            tool_name=tool,
            message=message,
            payload=payload,
        ),
        llm_provider=llm_provider,
    )
    update_trip(trip_id=trip_id, itinerary=updated_itinerary, rationale=rationale)
    next_version = get_latest_version_id(trip_id) + 1
    create_itinerary_version(
        trip_id=trip_id,
        version_id=next_version,
        itinerary=updated_itinerary,
        diff_summary=decision.user_message,
    )
    meta.itinerary_version = next_version

    final_log_id = _create_log(
        trip_id=trip_id,
        stage="replanner",
        tool_name="replan_done",
        message="Replan pipeline finished.",
        payload={
            "alerts": alerts,
            "decision_source": meta.decision_source,
            "fallback_used": meta.fallback_used,
            "model": meta.model,
            "latency_ms": meta.latency_ms,
            "error": meta.error,
            "critic_passed": meta.critic_passed,
            "itinerary_version": meta.itinerary_version,
            "prompt_variant": meta.prompt_variant,
            "event_type": request.event_type,
            "source": request.source,
            "decision": decision.model_dump(),
        },
    )
    return TripEventResponse(
        updated_itinerary=updated_itinerary,
        alerts=alerts,
        agent_log_id=final_log_id,
        decision=decision,
        meta=meta,
    )


@app.post(
    "/api/trips/{trip_id}/decisions/{decision_id}/feedback",
    response_model=DecisionFeedbackResponse,
)
def create_decision_feedback_api(
    trip_id: str,
    decision_id: str,
    request: DecisionFeedbackRequest,
) -> DecisionFeedbackResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    decision_log = get_log(decision_id, trip_id=trip_id)
    if decision_log is None or decision_log.tool_name != "replan_done":
        raise HTTPException(status_code=404, detail="Decision not found")

    decision_payload = json.loads(decision_log.payload_json) if decision_log.payload_json else {}
    feedback = create_decision_feedback(
        trip_id=trip_id,
        decision_id=decision_id,
        accepted=request.accepted,
        reason=request.reason,
        decision_source=str(decision_payload.get("decision_source")) if decision_payload.get("decision_source") else None,
        event_type=str(decision_payload.get("event_type")) if decision_payload.get("event_type") else None,
        latency_ms=int(decision_payload.get("latency_ms")) if isinstance(decision_payload.get("latency_ms"), (int, float)) else None,
    )
    _create_log(
        trip_id=trip_id,
        stage="replanner",
        tool_name="decision_feedback",
        message="Received decision feedback.",
        payload={
            "decision_id": decision_id,
            "accepted": request.accepted,
            "reason": request.reason,
            "decision_source": decision_payload.get("decision_source"),
            "event_type": decision_payload.get("event_type"),
        },
    )
    return DecisionFeedbackResponse(
        trip_id=trip_id,
        decision_id=decision_id,
        accepted=feedback.accepted,
        reason=feedback.reason,
        decision_source=feedback.decision_source,
        event_type=feedback.event_type,
        latency_ms=feedback.latency_ms,
        created_at=feedback.created_at.isoformat(timespec="seconds"),
    )


@app.get("/api/trips/{trip_id}/versions", response_model=ItineraryVersionsResponse)
def get_trip_versions_api(trip_id: str) -> ItineraryVersionsResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    versions = list_itinerary_versions(trip_id)
    current_version = versions[-1].version_id if versions else 0
    items = [
        ItineraryVersionItem(
            version_id=item.version_id,
            diff_summary=item.diff_summary,
            created_at=item.created_at.isoformat(timespec="seconds"),
        )
        for item in versions
    ]
    return ItineraryVersionsResponse(
        trip_id=trip_id,
        current_version=current_version,
        versions=items,
    )


@app.post("/api/trips/{trip_id}/versions/{version_id}/rollback", response_model=ItineraryRollbackResponse)
def rollback_trip_version_api(trip_id: str, version_id: int) -> ItineraryRollbackResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    target = get_itinerary_version(trip_id, version_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")

    restored_itinerary = json.loads(target.itinerary_json)
    rationale = f"Rolled back to version {version_id}"
    update_trip(trip_id=trip_id, itinerary=restored_itinerary, rationale=rationale)
    active_version = get_latest_version_id(trip_id) + 1
    create_itinerary_version(
        trip_id=trip_id,
        version_id=active_version,
        itinerary=restored_itinerary,
        diff_summary=f"Rollback to v{version_id}",
    )
    _create_log(
        trip_id=trip_id,
        stage="replanner",
        tool_name="version_rollback",
        message="Itinerary rollback executed.",
        payload={
            "restored_version": version_id,
            "active_version": active_version,
        },
    )
    return ItineraryRollbackResponse(
        trip_id=trip_id,
        restored_version=version_id,
        active_version=active_version,
        itinerary=restored_itinerary,
        rationale=rationale,
    )


@app.get("/api/config/replan", response_model=ReplanConfigResponse)
def get_replan_config_api(city: str | None = Query(default=None)) -> ReplanConfigResponse:
    active_city, policy = get_replan_policy(city)
    settings = getattr(llm_provider, "settings", None)
    prompt_variant = getattr(settings, "prompt_variant", "A")
    return ReplanConfigResponse(
        active_city=active_city,
        policy=policy,
        prompt_variant=str(prompt_variant),
    )


@app.get("/api/trips/{trip_id}/logs", response_model=AgentLogsResponse)
def get_logs_api(trip_id: str) -> AgentLogsResponse:
    row = get_trip(trip_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    logs = []
    for item in list_logs(trip_id):
        logs.append(
            AgentLogItem(
                id=item.id,
                stage=item.stage,
                tool_name=item.tool_name,
                message=item.message,
                payload=json.loads(item.payload_json) if item.payload_json else None,
                created_at=item.created_at.isoformat(timespec="seconds"),
            )
        )
    return AgentLogsResponse(trip_id=trip_id, logs=logs)
