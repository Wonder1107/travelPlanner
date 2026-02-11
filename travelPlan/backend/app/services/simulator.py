from __future__ import annotations

from datetime import datetime


def _stable_number(seed: str) -> int:
    return sum(ord(ch) for ch in seed)


def simulate_crowd_metrics(poi_id: str, hour: int | None = None) -> dict[str, float | int]:
    use_hour = hour if hour is not None else datetime.now().hour
    base = (_stable_number(poi_id) % 100) / 100.0
    peak_boost = 0.28 if use_hour in {10, 11, 14, 15, 16} else 0.05
    crowd_index = min(0.98, max(0.1, 0.35 + base * 0.4 + peak_boost))
    queue_minutes = int(round(crowd_index * 130))
    return {"crowd_index": round(crowd_index, 2), "queue_minutes": queue_minutes}


def simulate_ticket_left(poi_id: str, day_offset: int) -> int:
    raw = (_stable_number(f"{poi_id}-{day_offset}") % 90) + 10
    scarcity = 0.7 if day_offset == 0 else 1.0
    return max(0, int(raw * scarcity))
