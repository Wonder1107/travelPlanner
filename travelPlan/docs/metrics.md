# 指标与实验（MVP）

## 北极星指标
- Dynamic Replan Value Rate = 触发后被采纳的建议次数 / 触发次数

## 核心过程指标
- Itinerary Generation Latency（P95）
- Replan Response Latency（P95）
- Trigger Precision（满足阈值时触发正确率）
- Alternative Feasibility Rate（替代方案可达率）
- Fallback Rate（LLM 失败后回退规则策略的占比）
- Decision Confidence Distribution（`confidence` 分布，按 0.0-0.4 / 0.4-0.7 / 0.7-1.0）

## 业务代理指标
- Mock Booking Click-through（预约/导航/替换按钮点击率）
- Console Inspection Depth（每次会话查看日志条数）

## A/B 假设
- A：只给提醒，不自动给替代点
- B：提醒 + 一键替代（当前策略）
- 预期：B 在采纳率与完成率上显著提升

## Replanner 质量评测（新增）
- trigger_consistency：规则触发与预期触发的一致率
- replacement_relevance：触发后替代点与触发原因的一致率
- explanation_completeness：结构化解释字段完整率（reason/message/tradeoffs）
- fallback_rate：触发场景中 fallback 使用比例
