# 动态智能行程引擎 MVP
- 场景：AI 产品经理面试演示（2-3 天游动态行程）
- 核心命题：不是“生成一次计划”，而是“执行中持续适配”
- 交付形态：FastAPI + Next.js + RAG + Agent 工作流
- 证据锚点：README.md, docs/PRD.md

---

# 1. 问题与目标
- 用户痛点：天气、排队、疲劳会让静态行程快速失效
- MVP 目标：在执行阶段实时给出可采纳替代方案
- 成功指标（PRD）：首行程成功率 >=95%，重规划成功率 >=90%
- 北极星指标：Dynamic Replan Value Rate（触发后采纳率）
- 证据锚点：docs/PRD.md, docs/metrics.md

---

# 2. 用户路径与页面设计
- `/` Onboarding：采集城市/预算/偏好/避雷，创建行程
- `/trip/[id]` 执行页：时间轴 + 事件触发 + 决策证据卡
- `/console` 控制台：查看 Agent 日志与 fallback/LLM 来源
- 演示主线：生成行程 -> 触发事件 -> 解释重规划
- 证据锚点：docs/user_journey.md, frontend/app/page.tsx, frontend/app/trip/[id]/page.tsx, frontend/components/console-client.tsx

---

# 3. 系统架构（后端）
- API：`POST /api/trips`、`GET /api/trips/{id}`、`POST /events`、`GET /logs`
- Agent 编排：Planner + Monitor + Replanner（可选 LangGraph）
- 持久化：SQLite + SQLModel（Trip/AgentLog）
- 重规划返回结构化字段：`decision` + `meta`（来源、延迟、fallback）
- 证据锚点：backend/app/main.py, backend/app/agents/workflow.py, backend/app/db.py, backend/app/schemas.py

---

# 4. 重规划策略与可解释性
- 触发阈值：
  - weather：雨天 + 当前点室外
  - crowd：crowd_index > 0.8 且 queue_minutes > 90
  - user_status：tired/hungry 且 duration >= 120
- 候选排序：偏好匹配分 + 路径时间（Haversine 估算）
- 决策机制：优先 LLM 结构化决策，失败自动 fallback 规则
- 输出解释：reason / tradeoffs / user_message / confidence
- 证据锚点：backend/app/services/replanner.py, backend/app/tools/route_tools.py, backend/app/llm/client.py

---

# 5. 数据与 RAG 基础
- POI 数据：`data/poi_shanghai.json` 共 30 个点位
- 类别分布：museum(6), district(5), walking(4), landmark(3) ...
- 室内/室外：13 / 17；价格层级：mid(12), free(8), low(6), high(4)
- 检索策略：词法打分 +（可选）Chroma 向量检索融合
- 证据锚点：data/poi_shanghai.json, backend/app/tools/rag_tools.py

---

# 6. 质量验证（真实运行结果）
- 单元测试：`pytest -q` 结果 `9 passed`（0.66s）
- Replanner 评测：30 条 case（weather/crowd/user_status 各 10）
- 指标结果：trigger consistency/replacement relevance/explanation completeness = 100%
- 当前状态：fallback_rate = 100%，llm_decision_count = 0（未注入可用 API key）
- 证据锚点：backend/tests/*.py, backend/evals/replan_cases.json, backend/evals/eval_report.md

---

# 7. 一次真实重规划案例
- 输入：上海 2 天游，偏好 museum+coffee+nightwalk
- 触发事件：crowd（crowd_index=0.95, queue_minutes=120）
- 行程变化：Power Station of Art -> Sinan Mansions（约 23 分钟）
- 决策来源：fallback_rule；用户提示含原因与替代权衡
- 证据锚点：backend/tests/test_api.py, backend/app/services/replanner.py（本地 TestClient 复现实验）

---

# 8. 性能与观测
- 本地 in-process 压测（TestClient, 30 次）：
  - 创建行程 P95 ≈ 8.84ms
  - 事件重规划 P95 ≈ 9.68ms
- 单次行程日志样本：8 条，覆盖 planner/monitor/replanner 三阶段
- 控制台可直接查看 `decision_source`、`fallback_used`、`latency_ms`
- 证据锚点：frontend/components/console-client.tsx, backend/app/main.py（本地基准脚本）

---

# 9. 下一步迭代计划
- 接入真实天气/人流流式源，替换部分模拟数据
- 将 Replanner 从“首槽位替换”扩展到“整天多槽位联动优化”
- 提升 LLM 命中率并把 fallback_rate 从 100% 降到 <30%
- 建立线上指标看板：采纳率、重规划成功率、P95 延迟
- 证据锚点：backend/app/services/replanner.py, docs/metrics.md

---

# 10. Demo 话术收尾
- 这版 MVP 已证明：动态重规划链路完整且可解释
- 当前最关键增量：提升真实数据接入与 LLM 可用率
- 演示顺序建议：`/` -> `/trip/[id]` 触发 crowd/rain -> `/console`
- 可现场展示的命令：`pytest -q`、`.venv/bin/python scripts/eval_replanner.py`
- 证据锚点：README.md, docs/frontend-page-plan.md
