# LangGraph 工作流方案

本文提出一个面向 ClosedLoop 的 LangGraph 工作流设计，并给出一套便于迭代与测试驱动开发（TDD）的推荐仓库结构。

---

## 当前实现（已落地）

后端当前对外接口为 `POST /invoke`，会在一次调用内执行并返回 `state`。

当前 `build_graph()` 实际包含节点：

```text
extract_constraints
→ retrieve_candidates_node
→ filter_node
→ rerank_node
→ planner_node
```

说明：

- `verify_node / adjust_node / request_confirmation / execute_step` 属于后续扩展能力（本文后半部分为规划稿），当前版本尚未接入。

## 目标

- 将用户一句话需求转换为「4–6 小时」的具体行程单，步骤明确且可执行。
- 在执行任何动作之前，必须先获得用户确认。
- 执行阶段只通过 Mock 集成完成（预订 / 排队 / 通知等），避免真实网络调用。
- 首版以“默认每次都能正确完成”为前提，优先跑通主流程，不引入复杂恢复分支。
- 保持“单 Planner Agent 家族”设计：planner 用于生成主计划；adjust 是“更多记忆/上下文”的强化版，用于局部修正。其他节点要么是 LLM 结构化输出，要么是确定性函数。

## 高层状态机

### 阶段划分

1. **预处理（Pre-User-Card）**：在返回用户卡片前完成提取、召回、过滤排序与规划、校验与必要修正。
2. **确认（Confirm）**：请求用户批准或提出修改意见。
3. **执行（Execute, Mock）**：按步骤执行，产生模拟副作用与结果记录。
4. **完成（Complete）**：汇总执行结果与确认信息。

### 核心节点（Graph）

- 说明：以下为规划稿节点命名；当前实现中约束提取节点名为 `extract_constraints`，规划节点名为 `intent_extract_node`。
- `intent_extract_node`：LLM structured output（约束提取，支持忌口限制归一化处理）
- `retrieve_candidates_node`：MockDB 召回（确定性）
- `filter_node`：规则过滤（确定性剔除不合规单品）
- `rerank_node`：三维度打分 + 商业提权 + 时段分流（细化到套餐级别排序）
- `planner_agent_node`：Planner Agent（基于多 Pattern DFS 回溯、剪枝与语义降级策略，生成行程草案并包含明确的通勤步骤）
- `verify_node`：代码校验（确定性，支持时间段与餐次约束的指标评分）
- `adjust_node`：Planner Agent（强化版：更多记忆/上下文，用于局部修正）
- `request_confirmation`：返回用户卡片并请求确认
- `execute_step`：Mock 执行（预约/排队/下单/发消息）
- `finalize_summary`：汇总

### 关键边（转移关系）

- 约束提取完成后：进入召回与过滤排序，再交给 planner agent 生成行程草案。
- verify 校验失败：进入 adjust；若无法确定性修复，可复用 planner agent 生成“补丁式”修正。
- 生成可执行草案后：进入请求确认（返回用户卡片）。
- 确认阶段：同意 → 执行；要求修改 → 回到 adjust/planner；取消 → 结束。
- 执行阶段：按步骤顺序执行直至结束，然后进入汇总阶段。

## 状态模型（数据契约）

### 原则

- 图状态只存可序列化的数据。
- 分离“面向模型的提示词”与“面向用户的 UI 文案”。
- 首版仅保留主流程必需字段，避免过早引入恢复/回退复杂度。

### 建议的状态字段

- `user_input`: str
- `constraints`: dict
- `candidates`: dict
- `itinerary`: dict
- `confirmation`: dict
- `current_step`: str | None

### 行程单结构（建议）

- `window_hours`: float（4–6）
- `start_time_local`: str
- `steps`: list，元素包含
  - `id`: str
  - `title`: str
  - `location`: str | None
  - `duration_min`: int
  - `cost_estimate`: str | None
  - `prerequisites`: list[str]
  - `action`: dict（工具名 + 参数）
  - `success_criteria`: list[str]

## 执行策略

### 工具边界

- `planner_agent_node` 与 `adjust_node` 都是 Agent 节点；`intent_extract_node` 只做结构化输出，不承载规划与权衡。
- `retrieve_candidates_node / filter_node / rerank_node / verify_node` 必须是确定性节点（禁止调用 LLM），并且可被单元测试覆盖。
- 执行类节点必须调用工具（Mock 集成），并在工具返回后更新 `current_step`，最终由总结节点汇总执行结果。
- 首版默认工具调用成功；失败注入与恢复策略在后续通过 `adjust_node` 承接。

## 仓库结构（推荐）

### 设计理由

保留 `1.py` 作为最小可运行的组装脚本，但将主要逻辑下沉到 package 中，保证测试可以稳定导入模块。

### 推荐目录

- `closedloop/`
  - `__init__.py`
  - `config.py`（环境变量加载、类型化配置）
  - `contracts/`
    - `state.py`（LangGraph 状态 dataclasses / pydantic models）
    - `itinerary.py`
  - `llm/`
    - `providers.py`（DeepSeek/Qwen 适配器）
    - `prompts.py`
  - `graph/`
    - `build.py`（图构建）
    - `nodes/`（每个节点一个文件）
    - `policies.py`（路由、重试/回退规则）
  - `tools/`
    - `booking_mock.py`
    - `queue_mock.py`
    - `notify_mock.py`
  - `utils/`
    - `json.py`（安全解析/修复 JSON 的工具）
    - `time.py`

### 测试结构

- `tests/`
  - `test_graph_happy_path.py`
  - `test_graph_clarify_path.py`
  - `test_graph_failure_recovery.py`
  - `test_provider_fallback.py`
  - `test_contract_validation.py`

## TDD 里程碑（建议顺序）

1. **先做契约**：定义 state + itinerary 的 schema，并完成校验。
2. **图可编译**：构建能够编译与运行的图（节点先用 stub）。
3. **Happy Path**：一次请求 → 行程单 → 确认 → 执行两个 Mock 步骤。
4. **澄清路径**：缺失约束触发提问，回答后回到规划。
5. **端到端演示**：在“默认成功”假设下稳定完成完整流程并输出总结。

## 验收清单

- 图可以端到端运行，且不发生真实网络调用（仅 mocks）。
- 行程单满足 Schema 校验，且时间盒为 4–6 小时。
- 任何执行节点在用户确认前不得运行。
- 首版不包含 fallback/恢复分支，先保证主流程稳定跑通。
