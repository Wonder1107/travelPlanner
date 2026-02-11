from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from app.llm.client import LLMProvider
from app.schemas import ReplanDecision, ReplanMeta
from app.services.decision_critic import evaluate_candidate
from app.services.replan_policy import get_replan_policy
from app.services.simulator import simulate_crowd_metrics, simulate_ticket_left
from app.tools.route_tools import estimate_route_minutes
from app.tools.weather_tools import normalize_weather_condition

LogFn = Callable[[str, str, str, dict[str, Any] | None], str]

RAIN_CONDITIONS = {"rain", "heavy_rain", "rain_showers", "thunderstorm"}

# 定位最需要更换的事件，LLM根据需求重规划，并且有一个决策评审机制（decision critic）来判断是否接受LLM的建议
# 若不接受，启用基于规则（ranking最高的计划）的fallback方案。
def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_event_datetime(occurred_at: str | None) -> datetime:
    if not occurred_at:
        return datetime.now()
    raw = occurred_at.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now()
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _minutes_from_hhmm(value: Any) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except (TypeError, ValueError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _find_target_slot(
    itinerary: dict[str, Any],
    *,
    occurred_at: str | None = None,
    location: tuple[float, float] | None = None,
) -> tuple[int, int, dict[str, Any]] | None:
    """按事件时间/可选位置选择最应被替换的 slot。"""
    event_dt = _parse_event_datetime(occurred_at)
    event_minutes = event_dt.hour * 60 + event_dt.minute
    event_date = event_dt.date()
    best: tuple[tuple[int, int, int, int], tuple[int, int, dict[str, Any]]] | None = None

    for day_idx, day_data in enumerate(itinerary.get("days", [])):
        items = list(day_data.get("items", []))
        if not items:
            continue
        day_priority = day_idx
        day_raw = str(day_data.get("date", "")).strip()
        try:
            day_date = datetime.strptime(day_raw, "%Y-%m-%d").date()
            delta = (day_date - event_date).days
            day_priority = delta if delta >= 0 else 365 + abs(delta)
        except ValueError:
            pass

        for item_idx, item in enumerate(items):
            start_minutes = _minutes_from_hhmm(item.get("start_time"))
            if start_minutes is None:
                time_priority = 999
            elif day_priority == 0 and start_minutes >= event_minutes:
                time_priority = start_minutes - event_minutes
            elif day_priority == 0:
                time_priority = 600 + abs(start_minutes - event_minutes)
            else:
                time_priority = start_minutes

            route_priority = 0
            if location is not None:
                route_priority = estimate_route_minutes(
                    location,
                    (_safe_float(item.get("lat"), 31.23), _safe_float(item.get("lng"), 121.47)),
                )

            sort_key = (day_priority, time_priority, route_priority, item_idx)
            value = (day_idx, item_idx, item)
            if best is None or sort_key < best[0]:
                best = (sort_key, value)

    if best is not None:
        return best[1]

    for day_idx, day_data in enumerate(itinerary.get("days", [])):
        for item_idx, item in enumerate(day_data.get("items", [])):
            return day_idx, item_idx, item
    return None


def _preference_score(poi: dict[str, Any], preferences: list[str]) -> float:
    tags = [str(tag).lower() for tag in poi.get("tags", [])]
    category = str(poi.get("category", "")).lower()
    desc = str(poi.get("desc", "")).lower()
    score = 0.0
    for token in preferences:
        use_token = token.lower()
        if use_token in tags:
            score += 2.0
        if use_token in category:
            score += 1.2
        if use_token in desc:
            score += 0.6
    return round(score, 2)


def evaluate_trigger(
    event_type: str,
    payload: dict[str, Any],
    current_item: dict[str, Any],
    *,
    thresholds: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Monitor 触发器：判断是否需要重规划，并输出约束策略 policy。"""
    thresholds = thresholds or {}
    crowd_threshold = _safe_float(thresholds.get("crowd_index_threshold"), 0.8)
    queue_threshold = _safe_int(thresholds.get("queue_minutes_threshold"), 90)
    tired_duration_threshold = _safe_int(thresholds.get("tired_duration_threshold"), 120)

    policy: dict[str, Any] = {"require_indoor": None, "extra_tags": []}
    if event_type == "weather":
        raw = str(payload.get("condition", "unknown"))
        condition = normalize_weather_condition(raw)
        if condition in RAIN_CONDITIONS and not bool(current_item.get("indoor", False)):
            policy["require_indoor"] = True
            policy["extra_tags"] = ["museum", "coffee", "indoor"]
            return True, "Outdoor activity is risky due to rain.", policy
        return False, "Weather does not require replanning.", policy

    if event_type == "crowd":
        crowd_index = _safe_float(payload.get("crowd_index", current_item.get("crowd_index")), 0.0)
        queue_minutes = _safe_int(payload.get("queue_minutes", current_item.get("queue_minutes")), 0)
        if crowd_index > crowd_threshold and queue_minutes > queue_threshold:
            policy["extra_tags"] = ["hidden_gem", "less_crowded", "coffee"]
            return True, "Queue is too long and crowd level is high.", policy
        return False, "Crowd level does not cross the threshold.", policy

    if event_type == "user_status":
        status = str(payload.get("status", "")).lower()
        duration = _safe_int(payload.get("duration_minutes"), tired_duration_threshold)
        if status in {"tired", "hungry"} and duration >= tired_duration_threshold:
            policy["extra_tags"] = ["coffee", "food", "rest", "indoor"]
            policy["require_indoor"] = True if status == "tired" else None
            return True, f"User status '{status}' suggests a lower-intensity stop.", policy
        return False, "User status does not trigger replanning.", policy

    return False, "Unsupported event type.", policy


def build_replan_context(
    *,
    event_type: str,
    payload: dict[str, Any],
    current_item: dict[str, Any],
    policy: dict[str, Any],
    preferences: list[str],
    candidate_infos: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "event": {"type": event_type, "payload": payload},
        "trigger_policy": policy,
        "preferences": preferences,
        "current_item": {
            "poi_id": current_item.get("poi_id"),
            "name": current_item.get("name"),
            "category": current_item.get("category"),
            "indoor": current_item.get("indoor"),
            "queue_minutes": current_item.get("queue_minutes"),
            "crowd_index": current_item.get("crowd_index"),
        },
        "candidate_options": candidate_infos,
        "output_requirement": {
            "should_replan": "boolean",
            "primary_reason": "string",
            "selected_poi_id": "string|null",
            "alternatives": "string[]",
            "tradeoffs": "string[]",
            "user_message": "string",
            "confidence": "0~1 float",
        },
    }


def choose_replacement_with_llm(
    *,
    llm_provider: LLMProvider,
    context: dict[str, Any],
    candidate_ids: set[str],
    log: LogFn,
) -> tuple[ReplanDecision | None, dict[str, Any]]:
    decision, llm_meta = llm_provider.generate_structured_decision(context)
    log(
        "replanner",
        "llm_replan_decision",
        "Attempted LLM structured decision for replanning.",
        {
            "decision": decision.model_dump() if decision else None,
            "meta": llm_meta,
        },
    )
    if decision is None:
        return None, llm_meta
    if decision.selected_poi_id and decision.selected_poi_id not in candidate_ids:
        decision.selected_poi_id = None
    return decision, llm_meta


def _build_replacement_item(
    *,
    current_item: dict[str, Any],
    replacement: dict[str, Any],
    day_idx: int,
) -> dict[str, Any]:
    crowd = simulate_crowd_metrics(str(replacement.get("id", "")))
    return {
        "slot_id": current_item.get("slot_id"),
        "poi_id": replacement.get("id"),
        "name": replacement.get("name"),
        "category": replacement.get("category"),
        "tags": replacement.get("tags", []),
        "start_time": current_item.get("start_time"),
        "end_time": current_item.get("end_time"),
        "duration_minutes": int(replacement.get("avg_visit_minutes", current_item.get("duration_minutes", 90))),
        "indoor": bool(replacement.get("indoor", False)),
        "lat": replacement.get("lat"),
        "lng": replacement.get("lng"),
        "queue_minutes": crowd["queue_minutes"],
        "crowd_index": crowd["crowd_index"],
        "ticket_left": simulate_ticket_left(str(replacement.get("id", "")), day_offset=day_idx),
        "booking_status": "available",
        "notes": replacement.get("desc", ""),
    }


def _route_minutes(origin_item: dict[str, Any], replacement: dict[str, Any]) -> int:
    return estimate_route_minutes(
        (_safe_float(origin_item.get("lat"), 31.23), _safe_float(origin_item.get("lng"), 121.47)),
        (_safe_float(replacement.get("lat"), 31.23), _safe_float(replacement.get("lng"), 121.47)),
    )


def apply_replan(
    *,
    itinerary: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    preferences: list[str],
    candidates: list[dict[str, Any]],
    log: LogFn,
    llm_provider: LLMProvider | None = None,
    occurred_at: str | None = None,
    location: tuple[float, float] | None = None,
    city: str | None = None,
    policy_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str], str, ReplanDecision, ReplanMeta]:
    updated = deepcopy(itinerary)
    policy_city, city_policy = get_replan_policy(city)
    if policy_config is not None:
        city_policy = policy_config
        policy_city = "override"
    thresholds = city_policy.get("thresholds", {})
    ranking_weights = city_policy.get("ranking_weights", {})

    target = _find_target_slot(updated, occurred_at=occurred_at, location=location)
    if target is None:
        decision = ReplanDecision(
            should_replan=False,
            primary_reason="No slot available for replanning.",
            selected_poi_id=None,
            alternatives=[],
            tradeoffs=["No active slot could be updated."],
            user_message="No slot available for replanning.",
            confidence=0.4,
        )
        meta = ReplanMeta(decision_source="fallback_rule", fallback_used=False, latency_ms=0, critic_passed=None)
        return updated, [decision.user_message], "No-op", decision, meta

    day_idx, item_idx, current_item = target
    triggered, reason, policy = evaluate_trigger(
        event_type,
        payload,
        current_item,
        thresholds=thresholds,
    )
    log(
        "monitor",
        "monitor_event",
        "Monitor agent evaluated event trigger.",
        {
            "event_type": event_type,
            "triggered": triggered,
            "reason": reason,
            "payload": payload,
            "policy_city": policy_city,
        },
    )
    if not triggered:
        decision = ReplanDecision(
            should_replan=False,
            primary_reason=reason,
            selected_poi_id=None,
            alternatives=[],
            tradeoffs=["Keeping original plan avoids unnecessary context switching."],
            user_message=f"No replan needed: {reason}",
            confidence=0.88,
        )
        meta = ReplanMeta(decision_source="fallback_rule", fallback_used=False, latency_ms=0, critic_passed=None)
        return updated, [decision.user_message], reason, decision, meta

    route_weight = _safe_float(ranking_weights.get("route_minutes_weight"), 1.0)
    preference_weight = _safe_float(ranking_weights.get("preference_score_weight"), 1.0)
    exclude_ids = {str(current_item.get("poi_id", ""))}
    require_indoor = policy.get("require_indoor")
    extra_tags = list(policy.get("extra_tags", []))

    candidate_infos: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for poi in candidates:
        poi_id = str(poi.get("id", ""))
        if poi_id in exclude_ids:
            continue
        if require_indoor is True and not bool(poi.get("indoor", False)):
            continue
        route_minutes = _route_minutes(current_item, poi)
        preference_score = _preference_score(poi, preferences + extra_tags)
        ranking_score = round(preference_weight * preference_score - route_weight * route_minutes, 4)
        candidate_infos.append(
            {
                "poi_id": poi_id,
                "name": poi.get("name", ""),
                "category": poi.get("category", ""),
                "indoor": bool(poi.get("indoor", False)),
                "route_minutes": route_minutes,
                "preference_score": preference_score,
                "ranking_score": ranking_score,
            }
        )
        filtered.append(poi)
    if not filtered:
        decision = ReplanDecision(
            should_replan=False,
            primary_reason="Trigger detected but no suitable candidate is available.",
            selected_poi_id=None,
            alternatives=[],
            tradeoffs=["No valid nearby alternative satisfies current constraints."],
            user_message="Trigger detected but no alternative found.",
            confidence=0.62,
        )
        meta = ReplanMeta(decision_source="fallback_rule", fallback_used=False, latency_ms=0, critic_passed=False)
        return updated, [decision.user_message], "No candidate", decision, meta

    filtered_map = {str(item.get("id", "")): item for item in filtered}
    candidate_infos.sort(key=lambda item: (-_safe_float(item.get("ranking_score"), -9999.0), item["route_minutes"]))
    candidate_info_map = {str(item["poi_id"]): item for item in candidate_infos}

    selected_replacement: dict[str, Any] | None = None
    selected_decision: ReplanDecision | None = None
    llm_meta: dict[str, Any] = {}
    fallback_used = False

    if llm_provider is not None and llm_provider.enabled:
        context = build_replan_context(
            event_type=event_type,
            payload=payload,
            current_item=current_item,
            policy=policy,
            preferences=preferences,
            candidate_infos=candidate_infos[:8],
        )
        selected_decision, llm_meta = choose_replacement_with_llm(
            llm_provider=llm_provider,
            context=context,
            candidate_ids=set(filtered_map.keys()),
            log=log,
        )
        if (
            selected_decision is not None
            and selected_decision.should_replan
            and selected_decision.selected_poi_id
            and selected_decision.selected_poi_id in filtered_map
        ):
            selected_replacement = filtered_map[selected_decision.selected_poi_id]
        else:
            fallback_used = True
    else:
        fallback_used = True

    if selected_replacement is None:
        best_id = str(candidate_infos[0]["poi_id"])
        selected_replacement = filtered_map[best_id]

    selected_id = str(selected_replacement.get("id", ""))
    selected_score = _safe_float(candidate_info_map.get(selected_id, {}).get("preference_score"), 0.0)
    critic_passed, critic_reason, route_minutes = evaluate_candidate(
        current_item=current_item,
        replacement=selected_replacement,
        require_indoor=require_indoor,
        preference_score=selected_score,
        thresholds=thresholds,
    )
    if not critic_passed:
        fallback_used = True
        for candidate in candidate_infos:
            candidate_id = str(candidate["poi_id"])
            candidate_item = filtered_map[candidate_id]
            passed, reason_text, _ = evaluate_candidate(
                current_item=current_item,
                replacement=candidate_item,
                require_indoor=require_indoor,
                preference_score=_safe_float(candidate.get("preference_score"), 0.0),
                thresholds=thresholds,
            )
            if passed:
                selected_replacement = candidate_item
                selected_id = candidate_id
                selected_score = _safe_float(candidate.get("preference_score"), 0.0)
                critic_passed = True
                critic_reason = f"Critic fallback adjusted candidate. {reason_text}"
                route_minutes = _route_minutes(current_item, selected_replacement)
                break
        if selected_decision is not None and not critic_passed:
            selected_decision.confidence = min(selected_decision.confidence, 0.45)
            selected_decision.tradeoffs = list(selected_decision.tradeoffs) + [critic_reason]

    replacement_item = _build_replacement_item(
        current_item=current_item,
        replacement=selected_replacement,
        day_idx=day_idx,
    )
    updated["days"][day_idx]["items"][item_idx] = replacement_item
    updated.setdefault("meta", {})
    updated["meta"]["last_replan_reason"] = reason
    updated["meta"]["policy_city"] = policy_city

    alternatives = [
        str(item["name"])
        for item in candidate_infos[:4]
        if str(item["poi_id"]) != str(selected_replacement.get("id", ""))
    ][:3]

    if selected_decision is None:
        selected_decision = ReplanDecision(
            should_replan=True,
            primary_reason=reason,
            selected_poi_id=str(selected_replacement.get("id", "")),
            alternatives=alternatives,
            tradeoffs=[
                "Reduces queue or weather risk but may change the original thematic flow.",
                "Adds a short transfer to keep the day feasible.",
            ],
            user_message=(
                f"Recommend switching to {selected_replacement.get('name')} "
                f"({route_minutes} min away) due to {reason.lower()}"
            ),
            confidence=0.76 if critic_passed else 0.58,
        )
    selected_decision.should_replan = True

    if not selected_decision.selected_poi_id:
        selected_decision.selected_poi_id = str(selected_replacement.get("id", ""))
    if not selected_decision.alternatives:
        selected_decision.alternatives = alternatives
    if not selected_decision.user_message:
        selected_decision.user_message = (
            f"Recommend switching to {selected_replacement.get('name')} "
            f"({route_minutes} min away)."
        )
    if not critic_passed:
        selected_decision.tradeoffs = list(selected_decision.tradeoffs) + [critic_reason]

    meta = ReplanMeta(
        decision_source="llm" if not fallback_used and llm_provider is not None and llm_provider.enabled else "fallback_rule",
        fallback_used=fallback_used,
        latency_ms=_safe_int(llm_meta.get("latency_ms"), 0) if llm_meta else 0,
        model=str(llm_meta.get("model")) if llm_meta.get("model") else None,
        error=str(llm_meta.get("error")) if llm_meta.get("error") else None,
        critic_passed=critic_passed,
        prompt_variant=str(llm_meta.get("prompt_variant")) if llm_meta.get("prompt_variant") else None,
    )

    log(
        "replanner",
        "search_poi_rag",
        "Replanner selected alternative POI candidates.",
        {
            "query_preferences": preferences + extra_tags,
            "selected": selected_replacement.get("name"),
            "route_minutes": route_minutes,
            "decision_source": meta.decision_source,
            "fallback_used": meta.fallback_used,
            "critic_passed": critic_passed,
            "policy_city": policy_city,
        },
    )
    rationale = (
        "Replanned itinerary based on monitor trigger, candidate ranking, "
        "and LLM decision with deterministic fallback."
    )
    return updated, [selected_decision.user_message], rationale, selected_decision, meta
