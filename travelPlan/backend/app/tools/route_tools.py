from __future__ import annotations

import math

# 距离是通过经纬度真实计算得到的，但时间计算是模拟的，没有外接交通API
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def estimate_route_minutes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    mode: str = "walk",
) -> int:
    speed_kmh = {"walk": 4.5, "metro": 20.0, "taxi": 28.0}.get(mode, 4.5)
    distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
    base_minutes = (distance_km / max(speed_kmh, 1.0)) * 60.0
    transfer_penalty = 8 if mode == "metro" else 0
    return max(3, int(round(base_minutes + transfer_penalty)))
