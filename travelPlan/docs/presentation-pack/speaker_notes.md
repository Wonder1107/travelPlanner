## Slide 1｜动态智能行程引擎 MVP
这套项目是我为 AI PM 面试准备的动态行程引擎 demo。核心不是一次性生成 itinerary，而是用户在执行过程中遇到变化时，系统可以持续修正计划。当前形态是 FastAPI 后端 + Next.js 前端，结合 RAG 检索和 Agent 工作流，目标是让“计划失效”这件事变成可实时处理的问题。

## Slide 2｜问题与目标
旅行产品常见问题是“计划做得出来，但走不下去”。PRD 中把高频中断源归为天气、拥挤排队、用户体力状态变化。MVP 目标聚焦周末 2-3 天游：先给出可执行初始行程，再在触发事件后提供可采纳替代。成功指标在文档里有明确阈值：首行程成功率 >=95%，重规划成功率 >=90%，并关注触发后的采纳率。

## Slide 3｜用户路径与页面设计
前端分成三页：首页做 onboarding，采集偏好和避雷项；Trip 页展示时间轴并支持一键触发事件；Console 页展示 Agent 调用日志和决策来源。演示逻辑也按这三页走：先生成，再触发，再解释，面试官可以完整看到“生成-执行-复盘”的闭环。

## Slide 4｜系统架构（后端）
后端提供 4 个核心接口：创建行程、查看行程、事件重规划、日志查询。Agent 侧是 Planner/Monitor/Replanner 三段，代码支持 LangGraph，有依赖就走图编排，没有也能 fallback 到函数流程。所有过程写入 SQLite 的 Trip 和 AgentLog 表，重规划响应里返回结构化 `decision` 和 `meta`，方便前端展示“为什么改、怎么改、由谁改”。

## Slide 5｜重规划策略与可解释性
触发逻辑是明确规则：雨天且当前点是室外才触发 weather；crowd_index > 0.8 且排队 > 90 分钟才触发 crowd；用户 tired/hungry 且持续时长 >=120 分钟触发 user_status。触发后会根据偏好分和路径时间排序候选点。决策优先走 LLM 结构化输出，失败时自动回落到确定性规则，因此不会因为模型不可用而中断服务。

## Slide 6｜数据与 RAG 基础
当前知识库是本地 `poi_shanghai.json`，共 30 个上海点位。类别以 museum、district、walking 为主，室内 13 个、室外 17 个，价格层级覆盖 free/low/mid/high。检索层先做词法打分，再在配置了 API key 时融合 Chroma 向量召回，这样可以兼顾离线稳定性和语义召回能力。

## Slide 7｜质量验证（真实运行结果）
我在本地跑过 `pytest -q`，结果是 9 个测试全部通过。评测脚本覆盖 30 个重规划 case，三类事件各 10 条。当前 `eval_report` 里 trigger consistency、replacement relevance、explanation completeness 都是 100%。但也有一个真实现状：fallback_rate 100%，llm_decision_count 0，说明当前环境未启用可用 LLM key，系统完全跑在规则回退路径。

## Slide 8｜一次真实重规划案例
我用 TestClient 复现了一次真实链路：用户偏好 museum+coffee+nightwalk，初始首站是 Power Station of Art。触发 crowd 事件（0.95、120 分钟）后，系统把首站替换成 Sinan Mansions，给出约 23 分钟路程和替代解释。这个案例体现了系统行为是可复现的，不是随机“讲故事”。

## Slide 9｜性能与观测
本地做了 30 次 in-process 小基准，创建行程 P95 约 8.84ms，事件重规划 P95 约 9.68ms。单次 trip 的日志样本有 8 条，能覆盖 planner、monitor、replanner 三阶段。Console 页面把 `decision_source`、`fallback_used`、`latency_ms` 直接展示出来，方便排障和面试讲解。

## Slide 10｜下一步与收尾
这版 MVP 已经证明动态重规划链路可跑通、可解释、可验证。下一阶段重点是三件事：接入更真实的外部数据、把单槽位替换升级为多槽位联动优化、提升 LLM 命中率并降低 fallback_rate。演示时我建议按 `/` -> `/trip/[id]` -> `/console` 顺序，并现场跑 `pytest -q` 和评测脚本，强化可信度。
