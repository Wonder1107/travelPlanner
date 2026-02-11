from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm.client import LLMProvider
from app.services.replanner import apply_replan, evaluate_trigger
from app.tools.rag_tools import POIRetriever

CASES_PATH = ROOT / "evals" / "replan_cases.json"
REPORT_PATH = ROOT / "evals" / "eval_report.md"


def _noop_log(stage: str, tool: str, message: str, payload: dict[str, Any] | None = None) -> str:
    _ = (stage, tool, message, payload)
    return "eval-log"


def _base_item(override: dict[str, Any]) -> dict[str, Any]:
    item = {
        "slot_id": "day1-1",
        "poi_id": "current_spot",
        "name": "Current Spot",
        "category": "landmark",
        "tags": ["outdoor", "landmark"],
        "start_time": "10:00",
        "end_time": "11:00",
        "duration_minutes": 60,
        "indoor": False,
        "lat": 31.2304,
        "lng": 121.4737,
        "queue_minutes": 80,
        "crowd_index": 0.6,
        "ticket_left": 999,
        "booking_status": "available",
        "notes": "Baseline item for replanner evaluation.",
    }
    item.update(override)
    return item


def _build_itinerary(current_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "city": "Shanghai",
        "days": [{"day": 1, "date": "2026-02-09", "items": [current_item]}],
        "meta": {"source": "eval"},
    }


def _is_explanation_complete(decision: Any) -> bool:
    return bool(
        decision.primary_reason
        and decision.user_message
        and isinstance(decision.tradeoffs, list)
        and len(decision.tradeoffs) > 0
    )


def run_eval() -> dict[str, Any]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    retriever = POIRetriever()
    llm_provider = LLMProvider()

    trigger_correct = 0
    relevance_hits = 0
    explanation_hits = 0
    fallback_count = 0
    triggered_total = 0
    confidences: list[float] = []
    used_llm_count = 0

    for case in cases:
        current_item = _base_item(case.get("current_item", {}))
        expected_trigger = bool(case.get("expected_trigger", False))
        preferences = case.get("preferences", ["museum", "coffee"])
        event_type = str(case["event_type"])
        payload = dict(case.get("payload", {}))

        triggered, _, _ = evaluate_trigger(event_type, payload, current_item)
        if triggered == expected_trigger:
            trigger_correct += 1

        candidates = retriever.search(
            preferences=preferences,
            context=json.dumps(payload, ensure_ascii=True),
            top_k=10,
        )
        itinerary = _build_itinerary(current_item)
        updated, _, _, decision, meta = apply_replan(
            itinerary=itinerary,
            event_type=event_type,
            payload=payload,
            preferences=preferences,
            candidates=candidates,
            log=_noop_log,
            llm_provider=llm_provider,
        )
        confidences.append(float(decision.confidence))
        if _is_explanation_complete(decision):
            explanation_hits += 1
        if meta.decision_source == "llm":
            used_llm_count += 1
        if triggered:
            triggered_total += 1
            if meta.fallback_used:
                fallback_count += 1
            new_item = updated["days"][0]["items"][0]
            is_replacement = new_item.get("poi_id") != current_item.get("poi_id")
            relevant = bool(decision.should_replan and is_replacement)
            if relevant and event_type == "weather" and bool(case.get("expect_indoor_replacement", False)):
                relevant = bool(new_item.get("indoor", False))
            if relevant and event_type == "user_status":
                status = str(payload.get("status", "")).lower()
                if status == "tired":
                    relevant = bool(new_item.get("indoor", False))
            if relevant:
                relevance_hits += 1

    total = len(cases)
    trigger_consistency = trigger_correct / total if total else 0.0
    explanation_completeness = explanation_hits / total if total else 0.0
    replacement_relevance = relevance_hits / triggered_total if triggered_total else 0.0
    fallback_rate = fallback_count / triggered_total if triggered_total else 0.0
    confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
    confidence_bins = {
        "0.0-0.4": len([x for x in confidences if x < 0.4]),
        "0.4-0.7": len([x for x in confidences if 0.4 <= x < 0.7]),
        "0.7-1.0": len([x for x in confidences if x >= 0.7]),
    }

    return {
        "total_cases": total,
        "triggered_cases": triggered_total,
        "trigger_consistency": round(trigger_consistency, 4),
        "replacement_relevance": round(replacement_relevance, 4),
        "explanation_completeness": round(explanation_completeness, 4),
        "fallback_rate": round(fallback_rate, 4),
        "confidence_avg": round(confidence_avg, 4),
        "confidence_bins": confidence_bins,
        "llm_decision_count": used_llm_count,
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_report(metrics: dict[str, Any]) -> None:
    lines = [
        "# Replanner Evaluation Report",
        "",
        f"- Generated at: {metrics['evaluated_at']}",
        f"- Total cases: {metrics['total_cases']}",
        f"- Triggered cases: {metrics['triggered_cases']}",
        "",
        "## KPI Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| trigger_consistency | {metrics['trigger_consistency']:.2%} |",
        f"| replacement_relevance | {metrics['replacement_relevance']:.2%} |",
        f"| explanation_completeness | {metrics['explanation_completeness']:.2%} |",
        f"| fallback_rate | {metrics['fallback_rate']:.2%} |",
        f"| llm_decision_count | {metrics['llm_decision_count']} |",
        "",
        "## Confidence Distribution",
        "",
        f"- avg confidence: {metrics['confidence_avg']:.2f}",
        f"- 0.0-0.4: {metrics['confidence_bins']['0.0-0.4']}",
        f"- 0.4-0.7: {metrics['confidence_bins']['0.4-0.7']}",
        f"- 0.7-1.0: {metrics['confidence_bins']['0.7-1.0']}",
        "",
        "## Notes",
        "",
        "- If OPENAI_API_KEY is missing or call fails, fallback_rule will increase.",
        "- replacement_relevance focuses on triggered cases only.",
        "- explanation_completeness checks reason, user message, and tradeoff fields.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    results = run_eval()
    write_report(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
