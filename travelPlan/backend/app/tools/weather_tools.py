from __future__ import annotations

from typing import Any

import httpx

# 联网获取当前位置的天气情况
WEATHER_CODE_MAP: dict[int, str] = {
    0: "clear",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing_drizzle",
    57: "freezing_drizzle",
    61: "rain",
    63: "rain",
    65: "heavy_rain",
    66: "freezing_rain",
    67: "freezing_rain",
    71: "snow",
    73: "snow",
    75: "heavy_snow",
    80: "rain_showers",
    81: "rain_showers",
    82: "heavy_rain_showers",
    95: "thunderstorm",
}


def normalize_weather_condition(raw: str | None) -> str:
    if raw is None:
        return "unknown"
    value = raw.lower().strip()
    if "rain" in value or "drizzle" in value:
        return "rain"
    if "thunder" in value:
        return "thunderstorm"
    if "snow" in value:
        return "snow"
    return value


async def fetch_weather_snapshot(lat: float, lng: float) -> dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lng,
        "current": "temperature_2m,weather_code",
        "timezone": "Asia/Shanghai",
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        body = response.json()
        current = body.get("current", {})
        weather_code = int(current.get("weather_code", -1))
        raw_condition = WEATHER_CODE_MAP.get(weather_code, "unknown")
        return {
            "condition": normalize_weather_condition(raw_condition),
            "temperature": current.get("temperature_2m"),
            "source": "open-meteo",
        }
    except Exception:
        return {
            "condition": "unknown",
            "temperature": None,
            "source": "fallback",
        }
