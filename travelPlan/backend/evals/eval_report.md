# Replanner Evaluation Report

- Generated at: 2026-02-10T01:42:14
- Total cases: 30
- Triggered cases: 15

## KPI Summary

| Metric | Value |
| --- | ---: |
| trigger_consistency | 100.00% |
| replacement_relevance | 100.00% |
| explanation_completeness | 100.00% |
| fallback_rate | 100.00% |
| llm_decision_count | 0 |

## Confidence Distribution

- avg confidence: 0.82
- 0.0-0.4: 0
- 0.4-0.7: 0
- 0.7-1.0: 30

## Notes

- If OPENAI_API_KEY is missing or call fails, fallback_rule will increase.
- replacement_relevance focuses on triggered cases only.
- explanation_completeness checks reason, user message, and tradeoff fields.
