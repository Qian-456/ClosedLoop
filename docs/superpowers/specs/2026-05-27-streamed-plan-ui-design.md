# 前端流式事件分层与 Plan 展示设计

## Summary

- 目标：为 ClosedLoop 前端建立一套稳定的流式 UI 分层，让聊天文案、过程状态、最终方案展示彼此解耦，并为后续 Plan 组件扩展预留空间。
- 用户已确认的产品方向：
  - 过程层采用“轻量状态栏”，不展示详细时间线。
  - 结果层采用“只显示最终结果”，不做渐进式方案卡片刷新。
- 方案：在当前 SSE 主链路之上增加一层产品级事件协议，将前端界面拆为 `messages`、`status bar`、`plan panel` 三个职责区，并把前端状态管理拆成“会话数据”和“流式 UI 状态”两层。

## Current State

### 1. 当前流式主链路仍以完整 state 快照为中心

- 后端 `backend/src/main.py`
  - 当前提供 `POST /invoke/stream`
  - 基于 SSE 输出 `state / done / error`
  - 图流式调用仍使用 `stream_mode="values"`
- 前端 `frontend/src/features/itinerary/api/invoke.ts`
  - 当前手写 SSE 解析器
  - 只消费 `state / done / error`
- 这意味着当前前端消费的是“后端完整状态快照”，而不是面向 UI 的产品事件。

### 2. 聊天视图已经是主路径，但结果展示仍偏消息化

- 前端首页主链路已经围绕聊天视图组织。
- `ChatView` 当前默认只渲染 `human / ai` 消息，隐藏 `tool / system`。
- 计划结果类型、抽屉组件、选择器已存在，但仍未形成稳定的“结果面板主入口”。
- 当前 UI 仍更像“聊天驱动 + 状态覆盖”，而不是“聊天区 + 结果区”的明确双区模型。

### 3. 当前状态管理仍偏整块覆盖

- 现有 store 更接近“收到一个后端 state，就整体同步到前端状态”。
- 这种方式在当前简单 SSE 下可用，但不适合继续承载：
  - 顶部轻量状态栏
  - 最终结果独立面板
  - 空结果态
  - 局部降级提示
  - 未来的 `custom / tools` 扩展

## Decisions

- `messages` 只负责用户可见的自然语言文案，不展示 tool 原始输入输出或内部日志。
- 过程层只采用“轻量状态栏”，用一句当前状态文案描述系统正在做什么。
- 结果层只在最终完成后一次性展示 plan，不做中间候选或渐进式结果刷新。
- 前端不直接绑定底层 LangGraph 原始流协议，而是消费一层稳定的产品级事件协议。
- 前端状态管理拆成两层：
  - `session`：会话资产，保存消息和最终结果
  - `streamUi`：单次请求生命周期内的临时 UI 状态
- `NO_FEASIBLE_PLAN` 视为业务空结果，而不是技术错误。
- 首版允许预留 `process` 扩展事件，但默认不在 UI 中展示。

## Proposed Changes

### 1. 定义产品级流式事件协议

- 目标：把底层 `state / done / error` 或未来的 `messages / updates / custom` 统一映射成前端可长期稳定消费的 UI 事件。

#### 事件类型

```ts
type StreamEvent =
  | {
      type: "message";
      data: {
        role: "assistant";
        text: string;
      };
    }
  | {
      type: "status";
      data: {
        phase:
          | "understanding"
          | "retrieving"
          | "filtering"
          | "planning"
          | "verifying"
          | "finalizing";
        text: string;
      };
    }
  | {
      type: "result";
      data: {
        sessionId: string;
        plans: ItineraryPlanVariant[];
        recommendedPlanId?: string;
        confirmation?: Confirmation;
      };
    }
  | {
      type: "error";
      data: {
        code: string;
        message: string;
        recoverable: boolean;
      };
    }
  | {
      type: "done";
      data: {
        success: boolean;
      };
    };
```

#### 设计原则

- `message`
  - 只保留用户应该读到的解释文案
- `status`
  - 只保留当前一句进度文案，不累积历史时间线
- `result`
  - 作为 PlanPanel 的唯一正式数据源
- `error`
  - 只包含产品级错误，不暴露内部 traceback
- `done`
  - 只表示本次流结束

### 2. 后端增加“产品事件适配层”

- 文件：`backend/src/main.py`

#### What

- 在现有 SSE 输出逻辑上，增加一层“从图状态到产品事件”的转换。
- 后端对前端输出不再只是一整块 state，而是按 UI 语义输出 `message / status / result / error / done`。

#### Why

- 避免前端直接依赖底层 LangGraph 或完整 state 结构。
- 保持首版在当前 SSE 模式下即可落地，同时为未来 `custom / updates` 升级留接口。

#### How

- 后端适配层需要同时支持两种底层流接入方式：
  - 过渡方案：`workflow_app.astream(..., stream_mode="values")`
  - 目标方案：`workflow_app.astream(..., stream_mode=["messages", "updates", "custom"])`
- 两种方案都遵循同一个原则：
  - 只执行一次 graph
  - 只打开一个流
  - 在流式过程中实时归一化为产品事件
  - 不做“等整次执行结束后再统一过滤”
- 过渡方案的映射方式：
  - 对每次 state snapshot 做提取与映射
  - 用户可见文案 -> `message`
  - 当前阶段 -> `status`
  - 最终 itinerary / plans / confirmation -> `result`
  - 异常 -> `error`
  - 流结束 -> `done`
- 目标方案的映射方式：
  - `messages` -> 聊天 token / 聊天文案
  - `updates` -> `status` 与 `result`
  - `custom` -> `process` 扩展事件或补充状态
  - `error` / 流结束 -> `error` / `done`
- 推荐采用“按 mode 分流，再映射为 UI 事件”的 adapter 结构，而不是把 LangGraph 原始事件直接暴露给前端组件。
- `status.text` 必须使用产品文案，而不是节点名或工具名。

#### Adapter 原则

- adapter 的职责是把“运行时事件”翻译成“界面事件”。
- 一帧底层事件可以产出 0 到多个 UI 事件。
- `messages` 与 `updates` 不应混用职责：
  - `messages` 负责“AI 正在说什么”
  - `updates` 负责“系统状态变成了什么”
- `custom` 只作为过程扩展通道，不能替代最终结果数据源。

#### 推荐演进路径

- 第一阶段：
  - 保留现有 SSE 主链路
  - 使用 `values` 方案快速落地 `message / status / result / error / done`
- 第二阶段：
  - 底层切换到 `messages + updates + custom`
  - 保持前端消费的产品事件协议不变
- 这样可以在不推翻前端 UI 结构的前提下，逐步获得真正的 token 流与状态增量流。

#### 推荐状态文案

- `understanding`: 正在理解你的需求
- `retrieving`: 正在召回候选地点
- `filtering`: 正在筛选营业时间和距离
- `planning`: 正在生成行程方案
- `verifying`: 正在检查时间与预算冲突
- `finalizing`: 正在整理推荐结果

### 3. 前端页面重构为三层职责布局

- 文件：`frontend/src/features/itinerary/ui/ChatView.tsx`
- 文件：`frontend/src/pages/HomePage.tsx`
- 文件：新增 `frontend/src/features/itinerary/ui/StatusBar.tsx`
- 文件：新增或重组 `frontend/src/features/itinerary/ui/PlanPanel.tsx`

#### What

- 把当前主页面明确拆成三个区块：
  - `ChatMessageList`
  - `StatusBar`
  - `PlanPanel`

#### Why

- 聊天区适合承载自然语言解释，不适合承载复杂结构化方案。
- 结果面板需要逐步承载详情、调整、确认执行等交互，应该脱离聊天气泡。

#### How

- `StatusBar` 位于聊天区上方或紧邻头部，只显示单句当前状态。
- `PlanPanel` 在结果未到达前保持空态，不显示中间候选。
- 收到 `result` 事件后一次性渲染方案卡片与后续操作入口。
- 聊天区继续只展示 `human / assistant`。

### 4. 前端 store 拆成 session 与 streamUi 两层

- 文件：`frontend/src/features/itinerary/store/useItineraryStore.ts`

#### What

- 从“整块后端 state 覆盖”演进为“事件驱动更新”。
- 拆分为会话资产和临时流式 UI 状态两类数据。

#### 建议结构

```ts
type SessionState = {
  sessionId: string;
  messages: ChatMessage[];
  planResult: PlanResult | null;
  confirmation: Confirmation | null;
};

type StreamUiState = {
  isStreaming: boolean;
  currentStatus: StatusEvent["data"] | null;
  lastError: ErrorEvent["data"] | null;
};

type ItineraryPageState = {
  session: SessionState;
  streamUi: StreamUiState;
};
```

#### Why

- `messages` 与 `planResult` 属于用户会话资产，应长期保存。
- `currentStatus` 与 `lastError` 只在本次流式请求期间有效。
- 分层后每个组件只订阅自己的数据域，避免互相污染。

#### How

- 用户发消息时：
  - 立即把用户消息写入 `session.messages`
  - 设置 `streamUi.isStreaming = true`
  - 初始化 `streamUi.currentStatus`
  - 清空 `streamUi.lastError`
- 收到 `message`：
  - 追加到 `session.messages`
- 收到 `status`：
  - 覆盖 `streamUi.currentStatus`
- 收到 `result`：
  - 写入 `session.planResult`
  - 若存在确认信息则更新 `session.confirmation`
  - 清空 `streamUi.currentStatus`
- 收到 `error`：
  - 更新 `streamUi.lastError`
  - 清空 `streamUi.currentStatus`
- 收到 `done`：
  - 设置 `streamUi.isStreaming = false`

### 5. PlanPanel 首版只承载最终结果、空结果与降级提示

- 文件：新增或重组 `frontend/src/features/itinerary/ui/PlanPanel.tsx`

#### What

- 首版 `PlanPanel` 先保持轻量，只承载三种结果态：
  - 成功结果
  - 空结果
  - 局部降级提示

#### Why

- 先建立稳定结果面板，再逐步扩展详情、切换、局部调整等交互。
- 避免初版把结果面板做成过重的多态容器。

#### How

- 成功结果至少展示：
  - 推荐方案标题
  - 总时长
  - 总预算
  - 推荐理由
  - 步骤摘要
  - 查看详情入口
- 空结果态使用 `EmptyResultCard`
  - 说明当前没生成出合适方案
  - 展示简短原因摘要
  - 提供建议调整方向
- 局部降级态
  - 允许仍然展示可用方案
  - 通过轻提示说明当前结果基于降级路径生成

### 6. 错误与空结果分流处理

#### What

- 把失败场景明确拆成三类：
  - 技术错误
  - 业务无结果
  - 局部降级

#### Why

- `NO_FEASIBLE_PLAN` 是合理业务反馈，不应与接口炸掉混为一谈。
- 分流后 UI 才能表现出产品级差异。

#### How

```ts
type ErrorEvent = {
  type: "error";
  data: {
    code:
      | "NETWORK_ERROR"
      | "TIMEOUT"
      | "INVALID_RESPONSE"
      | "NO_FEASIBLE_PLAN"
      | "PARTIAL_DEGRADED";
    message: string;
    recoverable: boolean;
  };
};
```

- `NETWORK_ERROR / TIMEOUT / INVALID_RESPONSE`
  - 进入技术错误展示
- `NO_FEASIBLE_PLAN`
  - 进入 `PlanPanel` 空结果态
- `PARTIAL_DEGRADED`
  - 保留最终方案，同时增加轻提示

### 7. 预留 process 扩展事件，但首版不强依赖

#### What

- 预留一个非主路径过程事件，用于未来对接 `custom / tools / node` 生命周期。

#### Why

- 保持当前首版 UI 简洁，但不封死后续扩展。

#### How

```ts
type ProcessEvent = {
  type: "process";
  data: {
    kind: "tool" | "custom" | "node";
    name: string;
    status: "start" | "end" | "error";
    summary?: string;
  };
};
```

- 首版前端默认忽略该事件，或仅在开发模式打印。
- 后续若要加入调试面板或可展开过程区，可直接消费该事件。

## Testing Plan

### 1. 后端事件映射测试

- 文件：`backend/src/tests/test_main.py`
- 覆盖：
  - `values` 过渡方案下，state snapshot 能正确映射为 `status`
  - `values` 过渡方案下，最终结果能正确映射为 `result`
  - `messages + updates + custom` 目标方案下，不同 mode 能正确映射到统一 UI 事件
  - 异常能映射为 `error`
  - 流结束会输出 `done`

### 2. 前端流式解析测试

- 文件：`frontend/src/features/itinerary/api/__tests__/invoke.stream.test.ts`
- 覆盖：
  - 可正确解析 `message / status / result / error / done`
  - 在 token 连续到达时能稳定合并 `message`
  - 在 `status` 与 `result` 交错到达时仍能保持 UI 一致性
  - 非法事件可被忽略或安全报错

### 3. 前端 store 测试

- 文件：`frontend/src/features/itinerary/store/__tests__/useItineraryStore.stream.test.ts`
- 覆盖：
  - `message` 只追加聊天内容
  - `status` 只更新临时 UI 状态
  - `result` 会写入 `planResult`
  - 新请求开始时旧结果暂时保留，直到新结果到达才替换
  - `error` 不会污染会话资产

### 4. 组件测试

- 文件：新增 `StatusBar` 与 `PlanPanel` 相关测试
- 覆盖：
  - 流式进行中显示状态栏
  - 结果到达后状态栏隐藏
  - 无结果时显示空结果卡片
  - 局部降级时显示轻提示

## Non-Goals

- 本次设计不直接把 LangGraph 原始 `tools` 事件暴露到聊天区。
- 本次设计不实现时间线式过程面板。
- 本次设计不实现渐进式方案骨架刷新。
- 本次设计不强制首版切换到底层 `messages / updates / custom` 多流模式。
- 本次设计不在首页一次性引入完整的方案编辑器或执行控制台。

## Acceptance Criteria

- 聊天区只展示自然语言消息，不展示 tool 原始输入输出。
- 流式进行中，页面可稳定显示单句当前状态。
- 最终方案只在完成后一次性展示在独立结果区。
- `NO_FEASIBLE_PLAN` 会进入空结果态，而不是技术报错弹窗。
- 前端 store 已明确拆分 `session` 与 `streamUi`，不再依赖整块后端 state 覆盖。
- 后端与前端之间存在稳定的产品级事件协议，未来可兼容 `custom / updates / tools` 演进。
