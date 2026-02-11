from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TripCreateRequest(BaseModel):
    city: str = Field(default="Shanghai")
    days: int = Field(default=2, ge=1, le=3)
    budget_level: Literal["low", "mid", "high"] = "mid"
    preferences: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    pace: Literal["slow", "balanced", "fast"] = "balanced"
    travel_note: str | None = None


class TripCreateResponse(BaseModel):
    trip_id: str
    itinerary: dict[str, Any]
    rationale: str
    agent_log_id: str


class EventLocation(BaseModel):
    lat: float
    lng: float


class TripEventRequest(BaseModel):
    event_type: Literal["weather", "crowd", "user_status"]
    payload: dict[str, Any] = Field(default_factory=dict)
    source: Literal["manual", "system"] = "manual"
    occurred_at: str | None = None
    location: EventLocation | None = None


class ReplanDecision(BaseModel):
    # 重规划“业务决策体”：既用于接口返回，也用于 LLM 结构化输出校验。
    should_replan: bool = True
    primary_reason: str
    selected_poi_id: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    user_message: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ReplanMeta(BaseModel):
    # 决策元信息，用于可观测性与回放分析。
    decision_source: Literal["llm", "fallback_rule"]
    # True 表示本次曾尝试 LLM 但最终采用规则结果（超时/异常/无效输出等）。
    fallback_used: bool
    # latency_ms/model/error 仅在启用 LLM 且发生调用时有意义。
    latency_ms: int | None = None
    model: str | None = None
    error: str | None = None
    critic_passed: bool | None = None
    itinerary_version: int | None = None
    prompt_variant: str | None = None


class TripEventResponse(BaseModel):
    updated_itinerary: dict[str, Any]
    alerts: list[str]
    agent_log_id: str
    decision: ReplanDecision | None = None
    meta: ReplanMeta | None = None


class TripResponse(BaseModel):
    trip_id: str
    itinerary: dict[str, Any]
    rationale: str


class AgentLogItem(BaseModel):
    id: str
    stage: str
    tool_name: str | None = None
    message: str
    payload: dict[str, Any] | None = None
    created_at: str


class AgentLogsResponse(BaseModel):
    trip_id: str
    logs: list[AgentLogItem]


class DecisionFeedbackRequest(BaseModel):
    accepted: bool
    reason: str | None = None


class DecisionFeedbackResponse(BaseModel):
    trip_id: str
    decision_id: str
    accepted: bool
    reason: str | None = None
    decision_source: str | None = None
    event_type: str | None = None
    latency_ms: int | None = None
    created_at: str


class ItineraryVersionItem(BaseModel):
    version_id: int
    diff_summary: str
    created_at: str


class ItineraryVersionsResponse(BaseModel):
    trip_id: str
    current_version: int
    versions: list[ItineraryVersionItem]


class ItineraryRollbackResponse(BaseModel):
    trip_id: str
    restored_version: int
    active_version: int
    itinerary: dict[str, Any]
    rationale: str


class ReplanConfigResponse(BaseModel):
    active_city: str
    policy: dict[str, Any]
    prompt_variant: str
