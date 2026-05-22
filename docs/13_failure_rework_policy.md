# 13 失败与返工策略（技术债）

本文件用于记录当前工作流在“状态未就绪 / 候选不足 / LLM 输出不合规”等情况下的处理策略与后续规划（技术债），避免逻辑分散在节点代码里难以统一演进。

## 1. 背景

当前 Graph 主要链路为：

`extract_constraints -> retrieve_candidates_node -> filter_rank_node -> plan_itinerary_node -> END`

其中：

- `retrieve_candidates_node` 负责从 mock_db 粗召回候选。
- `filter_rank_node` 负责确定性过滤 + 排序打分（产出 score）。
- `plan_itinerary_node` 将 candidates 直接传给 LLM，并用 schema 约束输出 itinerary。

## 2. 失败分类（建议统一语义）

建议将失败分为三类，分别对应不同处理方式：

1) **状态未就绪（Precondition/Not Ready）**
- 定义：当前节点的前置条件不满足，例如 `processed_steps` 不符合预期。
- 特点：通常是流程分支/调度策略导致，也可能是测试/外部调用使用方式不一致。

2) **候选不足（Insufficient Candidates）**
- 定义：候选列表为空或缺失某一必需类型（例如缺 gift_shop）。
- 特点：属于业务数据不足，往往可通过放宽约束、扩大距离、调整预算分配来修复。

3) **LLM 输出不合规（Invalid LLM Output）**
- 定义：LLM 输出未满足 schema 或“只能从 candidates 选”的约束（例如使用了不存在的 id，或缺少必需类型）。
- 特点：属于外部依赖不确定性，通常需要 deterministic fallback 或二次修正（adjust/replan）。

## 3. 当前实现的“记录”方式

当前节点层面已记录两类信息：

- **日志**：使用 `logger.error(...)` 记录 phase + error + 关键上下文（例如 processed_steps / missing_types）。
- **对外状态**：将失败结果写入 `state["itinerary"]`：
  - `status`
  - `missing_types`
  - `plans`（为空或 fallback 生成的最小可用方案）

这使得 API 层可以返回结构稳定的 state，而不是直接 500。

## 4. 技术债：返工（rework）应当在 Graph 层完成

当前 `plan_itinerary_node` 对“processed_steps 不就绪”只做止损：不继续调用 LLM，并返回一个可对外表达的结果。

后续建议把“返工/补跑”放在 Graph 的控制流（条件边、循环边）里统一处理，而不是在节点内部调用上游节点，避免：

- 节点间隐式依赖导致的强耦合
- 可观测性变差（图上看不到内部补跑）
- 测试与推理复杂度上升

### 4.1 返工决策表（建议）

基于 `candidates.processed_steps` 做调度：

- `None` 或 `[]`：跳回 `retrieve_candidates_node`
- `["retrieve_candidates_node"]`：跳回 `filter_rank_node`
- `["retrieve_candidates_node","filter_rank_node"]`：允许进入 `plan_itinerary_node`
- 其他未知值：记录 error，重置 candidates 并重新从 `retrieve_candidates_node` 走起

## 5. 技术债：预算紧导致 gift_shop 缺失的处理策略

当前 `filter_rank_node.hard_filter` 对 gift_shop 使用预算上限（例如 `price > budget * 0.3` 则过滤）。

当预算很紧时，gift_shop 可能被全部过滤导致 `missing_types=["gift_shop"]`。

后续建议的处理层级（从保守到激进）：

1) **放宽策略（推荐优先）**
- 在 rework 分支中引入“放宽一次”的确定性策略，例如：
  - gift_shop 的预算比例从 `0.3` 放宽到 `0.4/0.5`
  - distance 偏好从 `<2km` 放宽到 `2km-5km`（或从 `2km-5km` 放宽到 `>5km`）
- 放宽后重新执行 `retrieve -> filter_rank -> plan`

2) **交互式确认**
- 若放宽后仍缺 gift_shop，则向用户确认：
  - 增加预算
  - 放宽距离
  - 或允许“无礼品店”版本（此时需要调整 schema/产品要求）

3) **概念扩展（需要产品决策）**
- 将“礼物”从 `gift_shop` 扩展为更宽的类型（例如 `gift_option`），允许更丰富的候选来源与表达。
- 该变更需要同步修改 Candidates 数据契约与 itinerary schema。

## 6. 建议的后续落地（不在本次范围）

- 在 Graph 中加入 verify/adjust/replan 节点，并实现上述 rework 分支。
- 将 failure status 统一成一套错误码/业务态枚举（包含 not_ready / insufficient_candidates / invalid_llm_output 等）。
- 为关键分支补充单测：返工跳转、放宽策略生效、交互确认触发条件。

