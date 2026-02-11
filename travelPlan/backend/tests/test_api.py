from fastapi.testclient import TestClient

from app import main


class _FailingLLMProvider:
    enabled = True

    def generate_structured_decision(self, context: dict) -> tuple[None, dict]:
        _ = context
        return None, {"model": "fake-llm", "latency_ms": 8010, "error": "timeout"}


def test_api_create_get_event_flow() -> None:
    with TestClient(main.app) as client:
        create_resp = client.post(
            "/api/trips",
            json={
                "city": "Shanghai",
                "days": 2,
                "budget_level": "mid",
                "preferences": ["museum", "coffee", "nightwalk"],
                "avoid": ["kids"],
                "pace": "slow",
                "travel_note": "I enjoy art and slower pacing with cafe breaks.",
            },
        )
        assert create_resp.status_code == 200
        create_body = create_resp.json()
        trip_id = create_body["trip_id"]
        assert create_body["itinerary"]["days"]

        get_resp = client.get(f"/api/trips/{trip_id}")
        assert get_resp.status_code == 200

        event_resp = client.post(
            f"/api/trips/{trip_id}/events",
            json={
                "event_type": "crowd",
                "payload": {"crowd_index": 0.95, "queue_minutes": 125},
            },
        )
        assert event_resp.status_code == 200
        event_body = event_resp.json()
        assert event_body["alerts"]
        assert event_body["updated_itinerary"]["days"]
        assert event_body.get("decision") is not None
        assert event_body.get("meta") is not None
        assert "decision_source" in event_body["meta"]

        logs_resp = client.get(f"/api/trips/{trip_id}/logs")
        assert logs_resp.status_code == 200
        logs_body = logs_resp.json()
        assert len(logs_body["logs"]) >= 3
        assert any(
            isinstance(item.get("payload"), dict) and "decision_source" in item["payload"]
            for item in logs_body["logs"]
        )


def test_api_event_fallback_meta_when_llm_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "llm_provider", _FailingLLMProvider())
    with TestClient(main.app) as client:
        create_resp = client.post(
            "/api/trips",
            json={
                "city": "Shanghai",
                "days": 2,
                "budget_level": "mid",
                "preferences": ["museum", "coffee"],
                "avoid": [],
                "pace": "balanced",
            },
        )
        assert create_resp.status_code == 200
        trip_id = create_resp.json()["trip_id"]

        event_resp = client.post(
            f"/api/trips/{trip_id}/events",
            json={"event_type": "crowd", "payload": {"crowd_index": 0.95, "queue_minutes": 130}},
        )
        assert event_resp.status_code == 200
        body = event_resp.json()
        assert body["meta"]["fallback_used"] is True
        assert body["meta"]["decision_source"] == "fallback_rule"
