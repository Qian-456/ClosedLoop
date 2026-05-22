# Handoff 架构（窗口化工具箱）

本文记录将当前 LangGraph 流水线演进为 handoff 架构的设计要点：把“生成文本”改为“产出可交接的结构化工作包”，并把能力拆成可组合、可验证、可回滚的窗口（window）。

## 目标

- 将一次性 `/invoke` 的“端到端生成”演进为分阶段的 **Plan → Tune/Confirm → Execute**。
- 每个阶段以结构化产物（handoff packet）为交接物，允许重复进入 Tune 窗口做局部微调。
- 让规则计算（召回/过滤/排序/规划）尽量保持确定性，LLM 主要负责结构化抽取与解释。
- 为后续引入 “LLM 生成 pattern” 预留受控通道（Draft + Validator），避免直接改代码/在线污染主流程。

## 现状（当前 Graph）

当前后端 `build_graph()` 真实包含节点：

```text
extract_constraints
→ retrieve_candidates_node
→ filter_node
→ rerank_node
→ planner_node
→ copywriting_node
```

现状更接近“单条流水线产出方案”。handoff 的改造重点是：把节点产物升格为阶段交接物，并引入 Tune/Confirm/Execute 的门禁。

## Handoff Packet（交接物）分层

建议将状态分层为以下“交接物”，每一层都要求可序列化、可复检、可重放：

- `constraints`：从自然语言抽取出的结构化约束（含归一化字段）
- `candidates`：候选池（raw/filtered/ranked 的阶段性统计与结果）
- `plan_options`：规划阶段产出的多套结构化方案（每套包含 steps、时间/成本/得分摘要）
- `user_decision`：用户在 Tune/Confirm 阶段做出的结构化决策（选哪套、锁定项、替换指令等）
- `confirmed_itinerary`：确认后的最终行程（必须通过 validator）
- `execution_plan`：将 confirmed itinerary 编译成可执行的 mock actions 列表
- `execution_result`：逐步执行的事件与结果（失败原因、回滚、重试等）

核心原则：

- 上游输出必须足够结构化，下游不需要“再理解一次自然语言”。
- validator 的输出永远是结构化报告；LLM 不负责判断“是否合法”，只负责解释与给选项。

## Window 1：Plan Window（一个工具箱窗口）

Plan Window 负责把 `user_input` 变成 `plan_options`，内部可以仍然是现有确定性流水线，但对外表现为一个“Plan 工具”。

输入：

- `user_input`
- 可选 `plan_params`（候选池上限、距离 cap、偏好权重等）

内部步骤：

1. Extract：LLM 结构化约束抽取
2. Normalize：确定性归一化（时段/开始时间/人数折算等）
3. Retrieve：Mock DB 召回
4. Filter：硬性规则过滤
5. Rerank：确定性打分排序（含时段分流）
6. Planner：pattern 驱动组合生成（DFS+剪枝）产出 `plan_options`

输出：

- `constraints`
- `candidates`（包含 raw/filtered/ranked 的结果与统计）
- `plan_options`
- `plan_debug`（可选：用于 Tune 的统计信息，如被过滤原因分布、pattern 剪枝计数等）

## Window 2：Tune/Confirm Window（微调与验收）

Tune Window 允许围绕一个已生成的 `plan_option` 做局部修改，并且每次修改都必须经过确定性 validator 才能进入 Execute。

建议拆成两个能力：改（PlanEdit）与判（Validator），避免 LLM 自己“改完就说 OK”。

### 2.1 Pattern 相关能力

建议保留两条路径：

- PatternSelect（在线低风险）：只选择/加权现有 pattern（不改 pattern 定义）
- PatternDraft（受控高收益）：LLM 生成新的 pattern 草案（结构化 JSON），必须通过 PatternValidator + 单测后才进入正式 patterns

### 2.2 方案微调能力

- PlanEdit：执行结构化 edit ops（替换餐品/替换活动/删除 step/插入 buffer/锁定 step/调整开始时间等），只负责“改出一个新 itinerary”
- ItineraryValidator：输出结构化冲突报告；可选择应用“五级冲突修复策略”生成 repaired itinerary；但始终保持可解释、可复检

输出：

- `user_decision`
- `confirmed_itinerary`
- `confirmation`（给前端展示的确认卡片数据）

## Window 3：Handoff Window（编译/转换）

该窗口只做一件事：把 `confirmed_itinerary` 编译成 `execution_plan`。

原则：

- 不在执行阶段临时决定路线/替换 POI
- 执行阶段只消费 confirmed 的结构化计划

## Window 4：Execute Window（执行 Agent）

Execute Window 仅负责 mock 执行与事件回传：

- `compile_execution_plan`：行程 → mock actions
- `execute_mock`：逐条执行、产出 SSE 事件、失败回滚/重试

输出：

- `execution_result`

## 推荐的 API 切分（对应 handoff 门禁）

- `POST /invoke`：Plan Window（返回 `plan_options`）
- `POST /confirm`：Tune/Confirm Window（提交选项与 edit ops，返回 `confirmed_itinerary`）
- `POST /execute`：Execute Window（只接受 confirmed itinerary 或其 id，返回 execution_id / result）

## 分阶段落地建议（不推倒重来）

1. 不动现有 Plan 流水线，只把 planner/copywriting 的“用户文案输出”与“结构化方案输出”分离：先确保 `plan_options` 足够结构化
2. 先落地 Confirm：哪怕第一版仅支持“选择某套方案不改动”，也能形成 handoff 门禁
3. 再落地 Execute：先覆盖 2-3 类 mock action，把执行闭环跑通

