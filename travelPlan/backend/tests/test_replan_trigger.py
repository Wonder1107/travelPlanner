from app.services.replanner import evaluate_trigger


def test_weather_trigger_for_outdoor_activity() -> None:
    current_item = {"indoor": False}
    triggered, reason, policy = evaluate_trigger("weather", {"condition": "rain"}, current_item)
    assert triggered is True
    assert "rain" in reason.lower()
    assert policy["require_indoor"] is True


def test_crowd_trigger_threshold() -> None:
    current_item = {"indoor": True}
    triggered, _, _ = evaluate_trigger(
        "crowd",
        {"crowd_index": 0.91, "queue_minutes": 110},
        current_item,
    )
    assert triggered is True


def test_crowd_trigger_threshold_with_policy_override() -> None:
    current_item = {"indoor": True}
    triggered, _, _ = evaluate_trigger(
        "crowd",
        {"crowd_index": 0.91, "queue_minutes": 110},
        current_item,
        thresholds={"crowd_index_threshold": 0.95, "queue_minutes_threshold": 120},
    )
    assert triggered is False
