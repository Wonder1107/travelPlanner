from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# 距离和用户偏好加权的动态重规划策略配置，支持全局默认和城市级别覆盖。
DEFAULT_POLICY: dict[str, Any] = {
    "thresholds": {
        "crowd_index_threshold": 0.8,
        "queue_minutes_threshold": 90,
        "tired_duration_threshold": 120,
        "max_route_minutes": 60,
        "min_preference_score": 0.0,
    },
    "ranking_weights": {
        "route_minutes_weight": 1.0,
        "preference_score_weight": 1.0,
    },
}


def _normalize_city(city: str | None) -> str:
    if not city:
        return "default"
    lowered = city.strip().lower()
    head = lowered.split(",")[0].strip()
    normalized = re.sub(r"[^a-z0-9_]+", "_", head).strip("_")
    alias = {
        "shanghai_china": "shanghai",
        "beijing_china": "beijing",
    }
    if normalized in alias:
        return alias[normalized]
    return normalized or "default"


def _config_path() -> Path:
    custom = os.getenv("REPLAN_POLICY_PATH")
    if custom:
        return Path(custom).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "config" / "replan_policy.json"


def _merge_policy(override: dict[str, Any] | None) -> dict[str, Any]:
    override = override or {}
    merged = {
        "thresholds": dict(DEFAULT_POLICY["thresholds"]),
        "ranking_weights": dict(DEFAULT_POLICY["ranking_weights"]),
    }
    if isinstance(override.get("thresholds"), dict):
        merged["thresholds"].update(override["thresholds"])
    if isinstance(override.get("ranking_weights"), dict):
        merged["ranking_weights"].update(override["ranking_weights"])
    return merged


@lru_cache(maxsize=1)
def load_replan_policy_map() -> dict[str, dict[str, Any]]:
    path = _config_path()
    if not path.exists():
        return {"default": _merge_policy(None)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"default": _merge_policy(None)}
    if not isinstance(payload, dict):
        return {"default": _merge_policy(None)}

    policy_map: dict[str, dict[str, Any]] = {"default": _merge_policy(payload.get("default"))}
    for key, value in payload.items():
        if key == "default":
            continue
        if isinstance(value, dict):
            policy_map[_normalize_city(str(key))] = _merge_policy(value)
    return policy_map


def get_replan_policy(city: str | None) -> tuple[str, dict[str, Any]]:
    policy_map = load_replan_policy_map()
    city_key = _normalize_city(city)
    if city_key in policy_map:
        return city_key, policy_map[city_key]
    return "default", policy_map["default"]
