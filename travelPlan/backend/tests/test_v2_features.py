from __future__ import annotations

from fastapi.testclient import TestClient

from app import main


def test_replan_config_endpoint() -> None:
    with TestClient(main.app) as client:
        response = client.get("/api/config/replan", params={"city": "Shanghai"})
        assert response.status_code == 200
        body = response.json()
        assert body["active_city"] in {"shanghai", "default"}
        assert "thresholds" in body["policy"]
        assert "ranking_weights" in body["policy"]
        assert body["prompt_variant"] in {"A", "B"}


def test_feedback_versions_and_rollback_flow() -> None:
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
            json={
                "event_type": "crowd",
                "payload": {"crowd_index": 0.95, "queue_minutes": 130},
                "source": "manual",
                "occurred_at": "2026-02-10T14:00:00",
            },
        )
        assert event_resp.status_code == 200
        event_body = event_resp.json()
        decision_id = event_body["agent_log_id"]
        assert isinstance(event_body.get("meta"), dict)
        assert "itinerary_version" in event_body["meta"]
        assert "critic_passed" in event_body["meta"]

        feedback_resp = client.post(
            f"/api/trips/{trip_id}/decisions/{decision_id}/feedback",
            json={"accepted": True, "reason": "Looks better for current context."},
        )
        assert feedback_resp.status_code == 200
        feedback_body = feedback_resp.json()
        assert feedback_body["accepted"] is True
        assert feedback_body["decision_id"] == decision_id

        versions_resp = client.get(f"/api/trips/{trip_id}/versions")
        assert versions_resp.status_code == 200
        versions_body = versions_resp.json()
        assert versions_body["current_version"] >= 2
        assert len(versions_body["versions"]) >= 2

        rollback_resp = client.post(f"/api/trips/{trip_id}/versions/1/rollback")
        assert rollback_resp.status_code == 200
        rollback_body = rollback_resp.json()
        assert rollback_body["restored_version"] == 1
        assert rollback_body["active_version"] > rollback_body["restored_version"]

        logs_resp = client.get(f"/api/trips/{trip_id}/logs")
        assert logs_resp.status_code == 200
        logs = logs_resp.json()["logs"]
        assert any(log.get("tool_name") == "decision_feedback" for log in logs)
        assert any(log.get("tool_name") == "version_rollback" for log in logs)
