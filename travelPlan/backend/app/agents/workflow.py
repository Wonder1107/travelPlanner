from __future__ import annotations

from typing import Any, Callable, TypedDict

from app.llm.client import LLMProvider
from app.schemas import ReplanDecision, ReplanMeta
from app.services.planner import build_initial_itinerary
from app.services.replanner import apply_replan, evaluate_trigger

try:
    from langgraph.graph import END, START, StateGraph

    HAS_LANGGRAPH = True
except Exception:
    HAS_LANGGRAPH = False
    END = "__end__"
    START = "__start__"


LogFn = Callable[[str, str, str, dict[str, Any] | None], str]


class PlannerState(TypedDict, total=False):
    request: dict[str, Any]
    candidates: list[dict[str, Any]]
    itinerary: dict[str, Any]
    rationale: str


class ReplanState(TypedDict, total=False):
    itinerary: dict[str, Any]
    event: dict[str, Any]
    preferences: list[str]
    candidates: list[dict[str, Any]]
    alerts: list[str]
    rationale: str
    decision: ReplanDecision
    meta: ReplanMeta


def run_planner_agent(
    *,
    request: dict[str, Any],
    candidates: list[dict[str, Any]],
    log: LogFn,
) -> tuple[dict[str, Any], str]:
    """规划阶段入口。

    设计目标：统一 Planner 执行接口，既支持 LangGraph 编排，
    也支持在缺少依赖时的函数式降级执行，避免本地演示环境被框架绑定。
    """

    def planner_node(state: PlannerState) -> PlannerState:
        # 核心规划节点：把用户偏好、节奏和候选 POI 转换为日程草案。
        itinerary, rationale = build_initial_itinerary(
            city=state["request"]["city"],
            days=state["request"]["days"],
            preferences=state["request"]["preferences"],
            avoid=state["request"]["avoid"],
            pace=state["request"]["pace"],
            budget_level=state["request"]["budget_level"],
            travel_note=state["request"].get("travel_note"),
            candidates=state["candidates"],
            log=log,
        )
        return {"itinerary": itinerary, "rationale": rationale}

    if HAS_LANGGRAPH:
        # 生产/演示环境可切换到图编排，便于后续插入 critic 等节点。
        graph = StateGraph(PlannerState)
        graph.add_node("planner", planner_node)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", END)
        result = graph.compile().invoke({"request": request, "candidates": candidates})
        return result["itinerary"], result["rationale"]

    result = planner_node({"request": request, "candidates": candidates})
    return result["itinerary"], result["rationale"]


def run_replanner_agent(
    *,
    itinerary: dict[str, Any],
    event: dict[str, Any],
    preferences: list[str],
    candidates: list[dict[str, Any]],
    log: LogFn,
    llm_provider: LLMProvider | None = None,
) -> tuple[dict[str, Any], list[str], str, ReplanDecision, ReplanMeta]:
    """重规划阶段入口。

    责任拆分为 Monitor(是否触发) + Replanner(如何替换)，
    保持“触发判断”与“替换策略”解耦，便于单测覆盖与策略迭代。
    """

    def monitor_node(state: ReplanState) -> ReplanState:
        # 当前实现选择“首个待执行 slot”作为重规划目标。
        # 这是 MVP 的简化策略，后续可扩展为按时间窗口或用户实时位置定位。
        days = state["itinerary"].get("days", [])
        current_item = {}
        if days and days[0].get("items"):
            current_item = days[0]["items"][0]
        triggered, reason, policy = evaluate_trigger(
            state["event"]["event_type"],
            state["event"]["payload"],
            current_item,
        )
        return {
            "itinerary": state["itinerary"],
            "event": state["event"],
            "preferences": state["preferences"],
            "candidates": state["candidates"],
            "alerts": [reason],
            "rationale": "triggered" if triggered else "not_triggered",
        }

    def replanner_node(state: ReplanState) -> ReplanState:
        # Replanner 会再次执行完整触发与替换流程，确保单函数可独立复用。
        raw_location = state["event"].get("location")
        location = None
        if isinstance(raw_location, dict):
            try:
                location = (float(raw_location.get("lat")), float(raw_location.get("lng")))
            except (TypeError, ValueError):
                location = None
        updated, alerts, rationale, decision, meta = apply_replan(
            itinerary=state["itinerary"],
            event_type=state["event"]["event_type"],
            payload=state["event"]["payload"],
            preferences=state["preferences"],
            candidates=state["candidates"],
            log=log,
            llm_provider=llm_provider,
            occurred_at=state["event"].get("occurred_at"),
            location=location,
            city=str(state["itinerary"].get("city", "")),
        )
        return {
            "itinerary": updated,
            "alerts": alerts,
            "rationale": rationale,
            "decision": decision,
            "meta": meta,
        }

    if HAS_LANGGRAPH:
        # 图编排顺序：START -> monitor -> replanner -> END
        graph = StateGraph(ReplanState)
        graph.add_node("monitor", monitor_node)
        graph.add_node("replanner", replanner_node)
        graph.add_edge(START, "monitor")
        graph.add_edge("monitor", "replanner")
        graph.add_edge("replanner", END)
        result = graph.compile().invoke(
            {
                "itinerary": itinerary,
                "event": event,
                "preferences": preferences,
                "candidates": candidates,
            }
        )
        return (
            result["itinerary"],
            result["alerts"],
            result["rationale"],
            result["decision"],
            result["meta"],
        )

    monitor_state = monitor_node(
        {
            "itinerary": itinerary,
            "event": event,
            "preferences": preferences,
            "candidates": candidates,
        }
    )
    result = replanner_node(monitor_state)
    return (
        result["itinerary"],
        result["alerts"],
        result["rationale"],
        result["decision"],
        result["meta"],
    )
