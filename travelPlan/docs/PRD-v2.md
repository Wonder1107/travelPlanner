# PRD v2.0 - 动态智能行程引擎（MVP+）

- 版本：`v2.0`
- 日期：`2026-02-10`
- 状态：`Draft for Review`
- 文档类型：产品需求文档（新增版本，不替换 `docs/PRD.md`）

---

## 1. 背景与问题定义

### 1.1 背景
- 传统旅游规划产品在“生成计划”阶段体验良好，但在“执行计划”阶段缺少动态调整能力。
- 用户真实旅程中高频出现天气、拥挤、体力状态变化，静态计划容易失效。

### 1.2 核心问题
- 用户在行程执行中遇到突发变化时，无法快速得到可信、可执行的替代建议。
- 即使给出建议，若缺乏解释与证据，用户采纳意愿低。

### 1.3 产品机会
- 以“短途高频场景（2-3 天城市游）”切入，构建“可重规划、可解释、可回退”的智能行程引擎。

---

## 2. 目标与范围

## 2.1 目标（本版本）
- 实现从行程生成到事件驱动重规划的闭环体验。
- 让用户在触发事件后，可在秒级获得替代建议与解释。
- 提供可观测控制台，支持回放 Agent 决策过程。

## 2.2 范围（In Scope）
- Onboarding 信息采集（城市、天数、预算、偏好、避雷、备注）。
- 初始行程生成（RAG 候选召回 + 节奏化时间槽编排）。
- 事件重规划（`weather` / `crowd` / `user_status`）。
- 决策解释输出（`reason` / `tradeoffs` / `confidence` / `meta`）。
- 控制台日志追踪（工具调用、决策来源、fallback 状态）。

## 2.3 非范围（Out of Scope）
- 真实支付与票务闭环。
- 多用户协同编辑与投票机制。
- 商业级实时交通/人流接入与 SLA 承诺。

---

## 3. 目标用户与场景

## 3.1 目标用户
- 22-35 岁城市用户，偏好短途自由行。
- 对“效率 + 体验平衡”敏感，愿意接受 AI 建议但需要可解释证据。

## 3.2 关键场景
1. 用户创建行程后，遇到下雨，系统自动建议室内替代点。  
2. 当前景点排队超长，系统建议近距离低拥挤替代点。  
3. 用户疲劳/饥饿，系统建议低强度或餐饮休息点。  
4. 用户在 Console 中查看本次决策是 LLM 还是 fallback 规则完成。  

---

## 4. 产品方案概览

## 4.1 能力架构（Agent 视角）
- **PlannerAgent**：生成初始日程（偏好对齐 + 节奏排布）。
- **MonitorAgent**：判断事件是否触发重规划。
- **ReplannerAgent**：选择替代 POI 并替换对应行程槽位。
- **LLM 决策层**：输出结构化 JSON 决策；失败时自动降级。
- **Fallback 规则层**：LLM 不可用时，基于路径与偏好分执行确定性替代。
- **Console 可观测层**：回放日志、统计 RAG 调用与 fallback 频率。

## 4.2 决策原则
- 优先安全与可执行性，再兼顾偏好与体验连续性。
- 输出必须结构化，避免不可消费的自由文本。
- 失败可降级，降级可被观察。

---

## 5. 关键功能需求

## 5.1 行程创建（Create Trip）
### 输入
- `city`, `days`, `budget_level`, `preferences`, `avoid`, `pace`, `travel_note`

### 输出
- `trip_id`, `itinerary`, `rationale`, `agent_log_id`

### 规则
- 若候选为空，返回可理解错误（不生成空行程）。
- 按 `pace` 映射每日槽位并填充 POI。

---

## 5.2 事件重规划（Event Replan）
### 支持事件
- `weather`: condition（如 rain）
- `crowd`: crowd_index + queue_minutes
- `user_status`: status + duration_minutes

### 输出
- `updated_itinerary`, `alerts`, `decision`, `meta`

### 规则
- 先触发判断，再做替代决策。
- 允许 LLM 决策；若失败则 fallback。
- 返回替代原因与用户可执行建议（`user_message`）。

---

## 5.3 决策解释与可观测
### 必须返回字段
- `decision_source`（`llm` / `fallback_rule`）
- `fallback_used`（boolean）
- `latency_ms`、`model`、`error`（可选）

### 控制台展示
- RAG 命中调用次数（`search_poi_rag`）
- LLM 决策次数、fallback 次数
- 最新决策摘要（理由、用户提示、模型与耗时）

---

## 6. 用户流程（端到端）

1. 用户填写旅行信息 -> 创建行程。  
2. 系统返回时间轴计划与基础解释。  
3. 用户触发事件（雨天/拥挤/疲劳）。  
4. Monitor 判定是否触发。  
5. Replanner 生成替代建议，更新 itinerary。  
6. UI 显示“为何更改 + 改成什么 + 风险权衡”。  
7. 用户可在 Console 查看决策证据链。  

---

## 7. API 与数据契约（产品视角）

## 7.1 API 列表
- `POST /api/trips`
- `GET /api/trips/{trip_id}`
- `POST /api/trips/{trip_id}/events`
- `GET /api/trips/{trip_id}/logs`

## 7.2 关键对象
- `ReplanDecision`
  - `should_replan`, `primary_reason`, `selected_poi_id`, `alternatives`, `tradeoffs`, `user_message`, `confidence`
- `ReplanMeta`
  - `decision_source`, `fallback_used`, `latency_ms`, `model`, `error`

---

## 8. 成功指标（KPI）

## 8.1 北极星指标
- `Dynamic Replan Value Rate = 触发后被采纳建议次数 / 触发次数`

## 8.2 过程指标
- `Itinerary Generation Latency (P95)`
- `Replan Response Latency (P95)`
- `Trigger Precision`
- `Alternative Feasibility Rate`
- `Fallback Rate`
- `Decision Confidence Distribution`

## 8.3 质量评估指标
- `trigger_consistency`
- `replacement_relevance`
- `explanation_completeness`
- `fallback_rate`

---

## 9. 验收标准（Acceptance Criteria）

1. 能成功创建 2-3 天行程并展示时间轴。  
2. 三类事件触发后，系统都可返回结构化结果。  
3. LLM 失败时，`meta.fallback_used=true` 且仍返回可执行替代方案。  
4. Console 能看到日志与决策来源统计。  
5. 不破坏既有 API 契约与测试基线。  

---

## 10. 版本里程碑

## M1（当前完成）
- Create Trip + Event Replan 全链路跑通
- LLM + fallback 双通路
- 控制台日志追踪与决策摘要

## M2（下一阶段建议）
- 触发阈值配置化（城市/用户分层）
- 目标 slot 选择策略升级（时间窗口 + 位置信息）
- 增加 DecisionCritic 节点做结果二次审阅

## M3（扩展方向）
- 接入外部实时天气/交通/票务数据
- 引入“建议采纳”闭环埋点与策略学习

---

## 11. 风险与缓解

1. **LLM 不稳定**：超时或格式漂移。  
   - 缓解：结构化输出约束 + fallback 规则 + error 透传。

2. **阈值泛化不足**：固定阈值不适配所有城市/人群。  
   - 缓解：配置化阈值 + 实验分桶。

3. **可解释性不足导致低采纳**。  
   - 缓解：强制返回 reason/tradeoffs/user_message/confidence。

4. **链路可观测性弱导致排障慢**。  
   - 缓解：agent logs + meta 指标 + console 聚合展示。

---

## 12. 非功能要求

- 响应稳定性：重规划接口在常规负载下保持可用，失败可降级。
- 可调试性：每次重规划都可通过日志追踪关键决策。
- 可维护性：决策字段与接口契约保持向后兼容。

---

## 13. 附录

- 旧版 PRD：`docs/PRD.md`
- 指标文档：`docs/metrics.md`
- 用户旅程：`docs/user_journey.md`
- Agent 评审：`docs/agent-core-review.md`
