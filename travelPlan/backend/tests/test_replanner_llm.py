from __future__ import annotations

from typing import Any

from app.schemas import ReplanDecision
from app.services.replanner import apply_replan, build_replan_context


class _LLMSuccess:
    enabled = True

    def generate_structured_decision(
        self,
        context: dict[str, Any],
    ) -> tuple[ReplanDecision | None, dict[str, Any]]:
        _ = context
        return (
            ReplanDecision(
                should_replan=True,
                primary_reason="Rain risk detected for outdoor activity.",
                selected_poi_id="indoor_museum",
                alternatives=["coffee_hub", "urban_gallery"],
                tradeoffs=["Slight detour but lower weather risk."],
                user_message="Switch to indoor_museum to avoid rain delays.",
                confidence=0.9,
            ),
            {"model": "fake-llm", "latency_ms": 120, "error": None},
        )


class _LLMTimeout:
    enabled = True

    def generate_structured_decision(
        self,
        context: dict[str, Any],
    ) -> tuple[ReplanDecision | None, dict[str, Any]]:
        _ = context
        return None, {"model": "fake-llm", "latency_ms": 8021, "error": "timeout"}


class _LLMInvalidJson:
    enabled = True

    def generate_structured_decision(
        self,
        context: dict[str, Any],
    ) -> tuple[ReplanDecision | None, dict[str, Any]]:
        _ = context
        return None, {"model": "fake-llm", "latency_ms": 164, "error": "invalid_json"}


def _noop_log(stage: str, tool: str, message: str, payload: dict[str, Any] | None = None) -> str:
    _ = (stage, tool, message, payload)
    return "log-id"


def _base_itinerary() -> dict[str, Any]:
    return {
        "city": "Shanghai",
        "days": [
            {
                "day": 1,
                "date": "2026-02-09",
                "items": [
                    {
                        "slot_id": "day1-1",
                        "poi_id": "bund_walk",
                        "name": "Bund Walk",
                        "category": "landmark",
                        "tags": ["nightwalk", "outdoor"],
                        "start_time": "10:00",
                        "end_time": "11:00",
                        "duration_minutes": 60,
                        "indoor": False,
                        "lat": 31.2400,
                        "lng": 121.4900,
                        "queue_minutes": 20,
                        "crowd_index": 0.4,
                        "ticket_left": 999,
                        "booking_status": "available",
                        "notes": "Riverside outdoor walk.",
                    }
                ],
            }
        ],
        "meta": {},
    }


def _candidate_pool() -> list[dict[str, Any]]:
    return [
        {
            "id": "indoor_museum",
            "name": "Indoor Museum",
            "category": "museum",
            "lat": 31.235,
            "lng": 121.485,
            "avg_visit_minutes": 90,
            "price_level": "mid",
            "tags": ["museum", "indoor", "art"],
            "indoor": True,
            "desc": "Rain-safe museum.",
        },
        {
            "id": "coffee_hub",
            "name": "Coffee Hub",
            "category": "coffee",
            "lat": 31.238,
            "lng": 121.488,
            "avg_visit_minutes": 60,
            "price_level": "mid",
            "tags": ["coffee", "rest", "indoor"],
            "indoor": True,
            "desc": "Relaxed coffee stop.",
        },
        {
            "id": "urban_gallery",
            "name": "Urban Gallery",
            "category": "gallery",
            "lat": 31.241,
            "lng": 121.492,
            "avg_visit_minutes": 70,
            "price_level": "mid",
            "tags": ["art", "gallery", "indoor"],
            "indoor": True,
            "desc": "Small local gallery.",
        },
    ]


def test_replanner_context_builder() -> None:
    context = build_replan_context(
        event_type="weather",
        payload={"condition": "rain"},
        current_item={"poi_id": "bund_walk", "name": "Bund Walk", "category": "landmark", "indoor": False},
        policy={"require_indoor": True, "extra_tags": ["museum", "indoor"]},
        preferences=["museum", "coffee"],
        candidate_infos=[
            {
                "poi_id": "indoor_museum",
                "name": "Indoor Museum",
                "category": "museum",
                "indoor": True,
                "route_minutes": 12,
                "preference_score": 3.2,
            }
        ],
    )
    assert context["event"]["type"] == "weather"
    assert context["trigger_policy"]["require_indoor"] is True
    assert len(context["candidate_options"]) == 1
    assert "output_requirement" in context


def test_replanner_llm_success() -> None:
    updated, alerts, _, decision, meta = apply_replan(
        itinerary=_base_itinerary(),
        event_type="weather",
        payload={"condition": "rain"},
        preferences=["museum", "coffee"],
        candidates=_candidate_pool(),
        log=_noop_log,
        llm_provider=_LLMSuccess(),  # type: ignore[arg-type]
    )
    first_item = updated["days"][0]["items"][0]
    assert alerts
    assert first_item["poi_id"] == "indoor_museum"
    assert decision.selected_poi_id == "indoor_museum"
    assert meta.decision_source == "llm"
    assert meta.fallback_used is False


def test_replanner_llm_timeout_fallback() -> None:
    updated, _, _, decision, meta = apply_replan(
        itinerary=_base_itinerary(),
        event_type="weather",
        payload={"condition": "rain"},
        preferences=["museum", "coffee"],
        candidates=_candidate_pool(),
        log=_noop_log,
        llm_provider=_LLMTimeout(),  # type: ignore[arg-type]
    )
    first_item = updated["days"][0]["items"][0]
    assert first_item["poi_id"] != "bund_walk"
    assert decision.should_replan is True
    assert meta.decision_source == "fallback_rule"
    assert meta.fallback_used is True
    assert meta.error == "timeout"


def test_replanner_llm_invalid_json_fallback() -> None:
    updated, _, _, decision, meta = apply_replan(
        itinerary=_base_itinerary(),
        event_type="weather",
        payload={"condition": "rain"},
        preferences=["museum", "coffee"],
        candidates=_candidate_pool(),
        log=_noop_log,
        llm_provider=_LLMInvalidJson(),  # type: ignore[arg-type]
    )
    first_item = updated["days"][0]["items"][0]
    assert first_item["poi_id"] != "bund_walk"
    assert decision.selected_poi_id is not None
    assert meta.decision_source == "fallback_rule"
    assert meta.fallback_used is True
    assert meta.error == "invalid_json"


def test_replanner_selects_slot_by_occurred_at() -> None:
    itinerary = _base_itinerary()
    itinerary["days"][0]["items"][0]["indoor"] = True
    itinerary["days"][0]["items"][0]["start_time"] = "09:00"
    itinerary["days"][0]["items"][0]["end_time"] = "10:00"
    itinerary["days"][0]["items"].append(
        {
            "slot_id": "day1-2",
            "poi_id": "evening_walk",
            "name": "Evening Walk",
            "category": "landmark",
            "tags": ["outdoor", "nightwalk"],
            "start_time": "18:00",
            "end_time": "19:00",
            "duration_minutes": 60,
            "indoor": False,
            "lat": 31.2380,
            "lng": 121.4920,
            "queue_minutes": 18,
            "crowd_index": 0.35,
            "ticket_left": 999,
            "booking_status": "available",
            "notes": "Outdoor evening route.",
        }
    )

    updated, _, _, decision, _ = apply_replan(
        itinerary=itinerary,
        event_type="weather",
        payload={"condition": "rain"},
        preferences=["museum", "coffee"],
        candidates=_candidate_pool(),
        log=_noop_log,
        llm_provider=_LLMTimeout(),  # type: ignore[arg-type]
        occurred_at="2026-02-09T17:30:00",
    )
    first_item = updated["days"][0]["items"][0]
    second_item = updated["days"][0]["items"][1]
    assert first_item["poi_id"] == "bund_walk"
    assert second_item["poi_id"] != "evening_walk"
    assert decision.should_replan is True
