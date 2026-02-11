from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlmodel import Field, Session, SQLModel, create_engine, select


def _default_database_url() -> str:
    backend_dir = Path(__file__).resolve().parents[1]
    return f"sqlite:///{backend_dir / 'travel_agent.db'}"


DATABASE_URL = os.getenv("DATABASE_URL", _default_database_url())
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=CONNECT_ARGS)


class Trip(SQLModel, table=True):
    id: str = Field(primary_key=True)
    city: str
    days: int
    budget_level: str
    preferences_json: str
    avoid_json: str
    pace: str
    itinerary_json: str
    rationale: str
    created_at: datetime
    updated_at: datetime


class AgentLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    trip_id: str = Field(index=True)
    stage: str
    tool_name: str | None = None
    message: str
    payload_json: str | None = None
    created_at: datetime


class ItineraryVersion(SQLModel, table=True):
    id: str = Field(primary_key=True)
    trip_id: str = Field(index=True)
    version_id: int = Field(index=True)
    itinerary_json: str
    diff_summary: str
    created_at: datetime


class DecisionFeedback(SQLModel, table=True):
    id: str = Field(primary_key=True)
    trip_id: str = Field(index=True)
    decision_id: str = Field(index=True)
    accepted: bool
    reason: str | None = None
    decision_source: str | None = None
    event_type: str | None = None
    latency_ms: int | None = None
    created_at: datetime


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def create_trip(
    *,
    trip_id: str,
    city: str,
    days: int,
    budget_level: str,
    preferences: list[str],
    avoid: list[str],
    pace: str,
    itinerary: dict[str, Any],
    rationale: str,
) -> None:
    now = utcnow()
    trip = Trip(
        id=trip_id,
        city=city,
        days=days,
        budget_level=budget_level,
        preferences_json=json.dumps(preferences, ensure_ascii=True),
        avoid_json=json.dumps(avoid, ensure_ascii=True),
        pace=pace,
        itinerary_json=json.dumps(itinerary, ensure_ascii=True),
        rationale=rationale,
        created_at=now,
        updated_at=now,
    )
    with Session(engine) as session:
        session.add(trip)
        session.commit()


def get_trip(trip_id: str) -> Trip | None:
    with Session(engine) as session:
        return session.exec(select(Trip).where(Trip.id == trip_id)).first()


def update_trip(
    *,
    trip_id: str,
    itinerary: dict[str, Any],
    rationale: str | None = None,
) -> None:
    with Session(engine) as session:
        trip = session.exec(select(Trip).where(Trip.id == trip_id)).first()
        if trip is None:
            return
        trip.itinerary_json = json.dumps(itinerary, ensure_ascii=True)
        if rationale is not None:
            trip.rationale = rationale
        trip.updated_at = utcnow()
        session.add(trip)
        session.commit()


def create_log(
    *,
    log_id: str,
    trip_id: str,
    stage: str,
    message: str,
    tool_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    row = AgentLog(
        id=log_id,
        trip_id=trip_id,
        stage=stage,
        tool_name=tool_name,
        message=message,
        payload_json=json.dumps(payload, ensure_ascii=True) if payload is not None else None,
        created_at=utcnow(),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()


def get_log(log_id: str, *, trip_id: str | None = None) -> AgentLog | None:
    with Session(engine) as session:
        stmt = select(AgentLog).where(AgentLog.id == log_id)
        if trip_id is not None:
            stmt = stmt.where(AgentLog.trip_id == trip_id)
        return session.exec(stmt).first()


def list_logs(trip_id: str) -> list[AgentLog]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(AgentLog).where(AgentLog.trip_id == trip_id).order_by(AgentLog.created_at.asc())
            )
        )


def get_latest_version_id(trip_id: str) -> int:
    with Session(engine) as session:
        rows = list(
            session.exec(
                select(ItineraryVersion.version_id)
                .where(ItineraryVersion.trip_id == trip_id)
                .order_by(ItineraryVersion.version_id.desc())
            )
        )
    return int(rows[0]) if rows else 0


def create_itinerary_version(
    *,
    trip_id: str,
    version_id: int,
    itinerary: dict[str, Any],
    diff_summary: str,
) -> ItineraryVersion:
    row = ItineraryVersion(
        id=str(uuid4()),
        trip_id=trip_id,
        version_id=version_id,
        itinerary_json=json.dumps(itinerary, ensure_ascii=True),
        diff_summary=diff_summary,
        created_at=utcnow(),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def list_itinerary_versions(trip_id: str) -> list[ItineraryVersion]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(ItineraryVersion)
                .where(ItineraryVersion.trip_id == trip_id)
                .order_by(ItineraryVersion.version_id.asc())
            )
        )


def get_itinerary_version(trip_id: str, version_id: int) -> ItineraryVersion | None:
    with Session(engine) as session:
        return session.exec(
            select(ItineraryVersion)
            .where(ItineraryVersion.trip_id == trip_id)
            .where(ItineraryVersion.version_id == version_id)
        ).first()


def create_decision_feedback(
    *,
    trip_id: str,
    decision_id: str,
    accepted: bool,
    reason: str | None,
    decision_source: str | None,
    event_type: str | None,
    latency_ms: int | None,
) -> DecisionFeedback:
    row = DecisionFeedback(
        id=str(uuid4()),
        trip_id=trip_id,
        decision_id=decision_id,
        accepted=accepted,
        reason=reason,
        decision_source=decision_source,
        event_type=event_type,
        latency_ms=latency_ms,
        created_at=utcnow(),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def list_decision_feedback(trip_id: str) -> list[DecisionFeedback]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(DecisionFeedback)
                .where(DecisionFeedback.trip_id == trip_id)
                .order_by(DecisionFeedback.created_at.asc())
            )
        )
