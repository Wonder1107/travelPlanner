from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from app.services.simulator import simulate_crowd_metrics, simulate_ticket_left

LogFn = Callable[[str, str, str, dict[str, Any] | None], str]

# 规划层，不依赖LLM，利用RAG，输出结构化的行程初稿，供后续决策和执行模块使用。
def _time_slots_for_pace(pace: str) -> list[str]:
    # 用 pace 控制每日槽位数量，等价于控制节奏密度。
    if pace == "slow":
        return ["10:00", "13:00", "16:30"]
    if pace == "fast":
        return ["09:00", "11:00", "13:30", "16:00", "19:00"]
    return ["09:30", "12:00", "15:00", "18:30"]


def build_initial_itinerary(
    *,
    city: str,
    days: int,
    preferences: list[str],
    avoid: list[str],
    pace: str,
    budget_level: str,
    travel_note: str | None,
    candidates: list[dict[str, Any]],
    log: LogFn,
) -> tuple[dict[str, Any], str]:
    """基于候选 POI 生成初始行程。

    关键策略：
    1) 优先满足 avoid 约束并去重；
    2) 数量不足时执行回填，优先保证时间槽完整；
    3) 注入模拟 crowd/ticket 指标，便于后续 monitor/replan 触发。
    """
    if not candidates:
        raise ValueError("No POI candidate available for itinerary planning.")

    top_names = [poi.get("name", "") for poi in candidates[:6]]
    log(
        "planner",
        "search_poi_rag",
        "Retrieved POI candidates from local knowledge base.",
        {"candidate_preview": top_names, "count": len(candidates)},
    )

    slots = _time_slots_for_pace(pace)
    items_per_day = len(slots)
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for poi in candidates:
        poi_id = str(poi.get("id", ""))
        if poi_id in used_ids:
            continue
        tags = [str(tag).lower() for tag in poi.get("tags", [])]
        # avoid 与标签命中即跳过，防止显性负偏好被纳入初始日程。
        if any(term.lower() in tags for term in avoid):
            continue
        selected.append(poi)
        used_ids.add(poi_id)
        if len(selected) >= items_per_day * days:
            break

    if len(selected) < items_per_day * days:
        # 回填策略：过滤过严时继续补齐，保持行程可执行性。
        for poi in candidates:
            poi_id = str(poi.get("id", ""))
            if poi_id in used_ids:
                continue
            selected.append(poi)
            used_ids.add(poi_id)
            if len(selected) >= items_per_day * days:
                break

    today = datetime.now()
    by_day: list[dict[str, Any]] = []
    cursor = 0
    for day_no in range(1, days + 1):
        day_items: list[dict[str, Any]] = []
        for slot in slots:
            if cursor >= len(selected):
                break
            poi = selected[cursor]
            cursor += 1
            metrics = simulate_crowd_metrics(str(poi.get("id", "")))
            ticket_left = simulate_ticket_left(str(poi.get("id", "")), day_offset=day_no - 1)
            duration = int(poi.get("avg_visit_minutes", 90))
            start_dt = datetime.strptime(slot, "%H:%M")
            end_dt = start_dt + timedelta(minutes=duration)
            day_items.append(
                {
                    "slot_id": f"day{day_no}-{len(day_items)+1}",
                    "poi_id": poi.get("id"),
                    "name": poi.get("name"),
                    "category": poi.get("category"),
                    "tags": poi.get("tags", []),
                    "start_time": start_dt.strftime("%H:%M"),
                    "end_time": end_dt.strftime("%H:%M"),
                    "duration_minutes": duration,
                    "indoor": bool(poi.get("indoor", False)),
                    "lat": poi.get("lat"),
                    "lng": poi.get("lng"),
                    "queue_minutes": metrics["queue_minutes"],
                    "crowd_index": metrics["crowd_index"],
                    "ticket_left": ticket_left,
                    "booking_status": "available" if ticket_left > 20 else "selling_fast",
                    "notes": poi.get("desc", ""),
                }
            )

        by_day.append(
            {
                "day": day_no,
                "date": (today + timedelta(days=day_no - 1)).strftime("%Y-%m-%d"),
                "items": day_items,
            }
        )

    itinerary = {
        "city": city,
        "days": by_day,
        "meta": {
            "pace": pace,
            "budget_level": budget_level,
            "preferences": preferences,
            "avoid": avoid,
            "travel_note": travel_note or "",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
    rationale = (
        "Initial itinerary generated with preference-aware POI retrieval, "
        "pace-based scheduling, and simulated real-world constraints."
    )
    log("planner", "compose_itinerary", "Built day-by-day timeline for the trip.", {"days": days, "pace": pace})
    return itinerary, rationale
