# 聊天流 ProcessBubble 设计

## 背景

当前前端将过程态主要展示在页面顶部的 `StatusBar`，这与聊天型产品体验不一致。  
用户希望：

- 过程状态出现在聊天流内部，而不是顶部横条。
- 过程状态由工具调用驱动，而不是混成普通 `AIMessage` 文案。
- 当正常的 `AIMessage` 还没有加载出来时，先显示默认过程态：`正在理解用户需求`。
- 本轮完成后，过程气泡保留，支持回看。

## 目标

- 用单个 `ProcessBubble` 替代顶部 `StatusBar` 作为主过程展示。
- `ProcessBubble` 插入在“当前轮用户消息”之后、“最终 AI 自然语言回复”之前。
- `ProcessBubble` 内容优先由工具调用驱动更新。
- 若本轮尚无可见 `AIMessage`，则默认显示 `正在理解用户需求`。
- 过程细节可展开查看，完成后保留以供回看。

## 非目标

- 本次不重做 `PlanPanel` 的整体布局。
- 本次不将所有工具做成完全不同的大卡片组件，仅先支持统一气泡 + 差异化摘要。
- 本次不改后端整体流协议，只复用现有 `message / status / process / result / done`。

## 用户体验

一轮典型交互形态如下：

```text
用户：今天下午一家三口出去玩
过程气泡：正在理解用户需求
过程气泡：正在规划方案
AI：我已经为你整理好一套亲子友好的下午行程
PlanPanel：方案卡片
```

说明：

- 聊天流里只保留一个过程气泡，不连续插入多条。
- 过程气泡内部状态会动态更新。
- 完成后变成“已完成规划”或对应完成态，但仍留在聊天流中。

## 事件来源与优先级

### 1. 主来源

过程气泡优先使用以下来源更新：

- 后端 `process` 事件
- 后端 `status` 事件
- `AIMessage` 中的工具调用线索
- `ToolMessage` 转换出的工具过程信息

### 2. 优先级

优先级从高到低：

1. `process`
2. `status`
3. `AIMessage.tool_calls`
4. 默认占位文案

默认占位规则：

- 当用户刚发出消息，且本轮还没有可见 `AIMessage`，也没有明确的 `process/status` 时：
  - 显示 `正在理解用户需求`

## 数据设计

### 前端消息流新增过程气泡模型

在前端会话态中新增可回看的过程气泡数据，不再把它只放在页面级临时顶栏中。

建议结构：

```ts
type ProcessBubbleRecord = {
  id: string
  sessionId: string
  relatedUserMessageId?: string
  phase:
    | "bootstrap"
    | "search_candidates"
    | "plan_trip"
    | "generate_alternative_plans"
    | "adjust_plan_item"
    | "transfer_to_execute"
    | "confirm_trip"
    | "done"
    | "error"
  text: string
  expanded: boolean
  status: "running" | "success" | "failed"
  processItems: InvokeStreamProcessEvent["data"][]
}
```

会话层建议增加：

```ts
type Session = {
  ...
  processHistory?: ProcessBubbleRecord[]
}
```

当前轮次同时保留：

```ts
currentProcessBubble: ProcessBubbleRecord | null
```

## UI 结构

### ChatView

当前主展示顺序调整为：

1. 用户消息
2. 当前轮 `ProcessBubble`
3. AI 自然语言消息
4. `PlanPanel`

顶部 `StatusBar` 从主路径移除，不再作为核心展示组件。

### ProcessBubble

职责：

- 显示本轮当前阶段
- 显示工具摘要
- 支持展开查看工具细节
- 完成后保留为历史过程项

折叠态：

- 只显示一句当前文案，例如：
  - `正在理解用户需求`
  - `正在召回候选地点`
  - `正在规划方案`
  - `已完成规划`

展开态：

- 展示工具执行条目列表
- 每条包含：
  - 工具名
  - 成功/失败状态
  - 简要摘要

## 工具阶段与展示文案映射

说明：

- `phase` 字段不再使用抽象的 `retrieving / planning / finalizing`。
- `phase` 应直接对齐当前 `tools` 和 `current_step` 的真实取值。
- 面向用户展示的中文文案继续通过映射得到，避免把内部工具名直接暴露给用户。

建议优先按工具名映射：

- `search_candidates` -> `正在召回候选地点`
- `plan_trip` -> `正在规划方案`
- `generate_alternative_plans` -> `正在生成更多方案`
- `adjust_plan_item` -> `正在调整方案`
- `transfer_to_execute` -> `正在切换到执行确认`
- `confirm_trip` -> `正在整理执行结果`

补充说明：

- `execute_itinerary` 工具内部最终写入的 `current_step` 实际是 `confirm_trip`，因此前端过程气泡优先以 `confirm_trip` 作为执行阶段标识，而不是再单独定义 `execute_itinerary` phase。
- 如果后端未来新增工具，只需要扩充 `phase` 枚举和文案映射，不需要改动聊天流布局。

无工具时的兜底：

- 默认 `正在理解用户需求`

完成态：

- 正常完成 -> `已完成规划`
- 失败 -> `处理失败，请稍后重试`

## 状态流转

### 开始发送

- 用户发送消息
- 立即创建当前轮 `ProcessBubble`
- 初始状态：
  - `phase=bootstrap`
  - `text=正在理解用户需求`
  - `status=running`

### 流式处理中

- 收到 `status` 事件：
  - 更新当前气泡主文案
- 收到 `process` 事件：
  - 追加到 `processItems`
  - 若工具名有更明确映射，则同步更新主文案
- 收到普通 `message`：
  - 仍按现有逻辑写入 AI 自然语言消息
  - 不覆盖过程气泡

### 完成

- 收到 `result`：
  - 更新 `Session.itinerary`
- 收到 `done(success=true)`：
  - 将当前气泡置为完成态
  - 文案更新为 `已完成规划`
  - 追加到 `processHistory`
  - 保留在聊天流中可回看

### 失败

- 收到 `error`：
  - 当前气泡变为失败态
  - 文案更新为 `处理失败，请稍后重试`
  - 保留失败记录供回看

## 具体改动文件

### `frontend/src/features/itinerary/store/useItineraryStore.ts`

- 新增 `currentProcessBubble`
- 新增 `processHistory`
- 新增开始、更新、完成过程气泡的 store 行为
- 将当前顶部栏展开状态迁移到过程气泡内

### `frontend/src/features/itinerary/ui/ChatView.tsx`

- 移除顶部 `StatusBar` 主展示
- 在消息流中插入 `ProcessBubble`
- 保证顺序为“用户消息 -> 过程气泡 -> AI消息”

### `frontend/src/features/itinerary/ui/ProcessBubble.tsx`

- 新增聊天流过程气泡组件
- 支持折叠/展开
- 支持运行中、成功、失败三态

### `frontend/src/features/itinerary/ui/StatusBar.tsx`

- 退役出主路径
- 若保留，仅作为备用组件或后续删除

### `frontend/src/features/itinerary/model/types.ts`

- 增加 `ProcessBubbleRecord` 类型
- 扩展 `Session` 与流式过程类型定义

## 验收标准

- 用户发送消息后，即使还没有 `AIMessage`，聊天区也能立即看到 `正在理解用户需求`
- 工具开始执行后，过程气泡文案会更新成对应阶段
- 工具细节不会再作为普通 AI 文本出现在聊天区
- 最终 AI 正常回复出现时，过程气泡仍然保留
- `PlanPanel` 正常显示最终方案
- 历史会话重新打开时，可以回看这一轮过程气泡

## 测试要求

### store

- 创建当前轮过程气泡
- `status` 更新过程文案
- `process` 追加工具细节
- `done` 后转为完成态并保留
- `error` 后转为失败态并保留

### UI

- `ChatView` 顺序正确
- 无 AI 回复时显示默认过程气泡
- 有 AI 回复后仍不覆盖过程气泡
- 展开后能看到工具细节

### 集成

- 真实 `/invoke/stream` 下：
  - 默认显示 `正在理解用户需求`
  - `search_candidates` 时显示 `正在召回候选地点`
  - `plan_trip` 时显示 `正在规划方案`
  - `generate_alternative_plans` 时显示 `正在生成更多方案`
  - `adjust_plan_item` 时显示 `正在调整方案`
  - `confirm_trip` 时显示 `正在整理执行结果`
  - 完成后显示 `已完成规划`
  - 最终方案卡片可见
