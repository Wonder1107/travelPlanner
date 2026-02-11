from __future__ import annotations

from typing import Any

from app.tools.route_tools import estimate_route_minutes

# 判断是否接受替换方案的决策者，主要是根据距离和用户偏好来判断
def evaluate_candidate(
    *,
    current_item: dict[str, Any],
    replacement: dict[str, Any],
    require_indoor: bool | None,
    preference_score: float,
    thresholds: dict[str, Any],
) -> tuple[bool, str, int]:
    route_minutes = estimate_route_minutes(
        (float(current_item.get("lat", 31.23)), float(current_item.get("lng", 121.47))),
        (float(replacement.get("lat", 31.23)), float(replacement.get("lng", 121.47))),
    )
    if require_indoor is True and not bool(replacement.get("indoor", False)):
        return False, "Critic rejected: replacement is not indoor under indoor-required policy.", route_minutes

    max_route_minutes = int(float(thresholds.get("max_route_minutes", 60)))
    if route_minutes > max_route_minutes:
        return False, f"Critic rejected: route too long ({route_minutes} > {max_route_minutes}).", route_minutes

    min_preference_score = float(thresholds.get("min_preference_score", 0.0))
    if preference_score < min_preference_score:
        return (
            False,
            f"Critic rejected: preference score too low ({preference_score} < {min_preference_score}).",
            route_minutes,
        )

    return True, "Critic passed.", route_minutes
