# Frontend：页面与后端对接（Integration）

## Purpose

这份文档回答：前端如何把“输入 → 生成方案 → 展示/选择”串起来，并说明哪些能力属于后续规划（未实现），避免文档与后端真实实现不一致。

当前后端真实接口为：

- `GET /health`
- `POST /invoke`
- `POST /invoke/stream`

后端代码入口见：`backend/src/main.py`。

搜索候选召回依赖独立的 `plan_sub_backend` 服务；若主后端运行在宿主机，`PLAN_SUB_API_URL` 应优先配置为 `http://localhost:8001/plan` 或 `http://127.0.0.1:8001/plan`。若主后端本身也运行在 Docker 网络内，才使用 `http://plan_sub_backend:8001/plan`。当前后端已增加多地址自动回退，用于降低本机 / Docker 混跑时的 DNS 配置错误影响。

---

## 当前实现：最小对接方式（推荐先跑通）

### 1) JSON 兼容模式：一次调用拿到完整 state

前端调用：

```text
POST /invoke
{ "user_input": "..." }
```

后端返回：

- `state.user_input`
- `state.constraints`：结构化约束（字段定义见 `backend/src/closedloop/contracts/state.py::Constraints`）
- `state.candidates`：候选与排序结果（可用于 Debug Panel；体积较大，UI 默认不需要全部渲染）
- `state.itinerary`：规划结果（字段定义见 `backend/src/closedloop/contracts/itinerary.py::ItineraryPlan`）

### 2) SSE 流式模式：按状态快照持续更新

前端调用：

```text
POST /invoke/stream
Content-Type: application/json
{ "user_input": "...", "thread_id": "..." }
```

后端返回 `text/event-stream`，事件类型为：

- `state`：中间态快照，`data.state` 是当前完整可序列化 state
- `done`：最终态快照，`data.state` 是最终完整 state
- `error`：异常结束，`data.message` 是错误信息

说明：

- 当前流式是 Graph/状态级 SSE，不是 token 级流。
- 前端推荐使用 `fetch + ReadableStream` 解析 SSE；不使用浏览器原生 `EventSource`，因为请求需要携带 `POST` body。
- 实时聊天主链路建议优先走 `/invoke/stream`，`/invoke` 作为兼容与调试入口保留。

### 3) 当前 LangGraph 节点流水线（真实）

后端当前 build_graph 实际包含：

```text
extract_constraints → retrieve_candidates_node → filter_node → rerank_node → planner_node
```

说明：

- 当前版本尚未接入 `verify_node / adjust_node / execute_mock`，因此前端也不应依赖“执行日志”“局部 action”等接口。
- “约束确认 Sheet”如果允许用户修改：需要把修改后的约束重新组织成自然语言，再次调用 `/invoke`（因为当前没有 `parse`/`generate` 分离接口）。

---

## UI Layout（建议：移动端 SPA，多页但轻量）

```text
首页输入 → 约束确认（Sheet） → 生成中 → 三方案 → 方案详情（可选） →（未来）局部调整/模拟执行
```

## Interaction Model（事件流）

### 0) 输入与生成（当前可落地）

- 用户输入一句话需求
- 前端优先调用 `/invoke/stream`
- 前端渲染：
  - 流式 `messages`（用于聊天气泡）
  - `constraints`（用于确认）
  - `itinerary.plans`（用于三方案与详情）
  - （可选）Debug Panel：展示 `candidates` 的统计信息与 `itinerary.status/missing_types`

---

## 未来规划（未实现）：局部替换 / 自然语言修改 / 执行闭环

下面内容属于规划方向，用于指导后续拆接口与前端交互升级；当前版本请不要按该契约实现 UI，以免与后端不一致。

## Data Contract（最小字段）

### Plan View Model（规划稿，未实现）

```json
{
  "plan_id": "p1",
  "status": "WAIT_CONFIRM",
  "timeline": [
    {
      "slot_id": "t1",
      "type": "activity",
      "selected": {"id": "a1", "name": "Indoor Park"},
      "candidates": [{"id": "a1"}, {"id": "a2"}],
      "start_time": "14:00",
      "duration_hours": 2,
      "location": {"lat": 0, "lng": 0}
    }
  ],
  "restaurants": {
    "r1": {
      "id": "r1",
      "name": "Restaurant A",
      "bundles": [
        {"bundle_id": "r1_b1", "title": "2-3 people set", "price": 169},
        {"bundle_id": "r1_b2", "title": "Family set", "price": 199},
        {"bundle_id": "r1_b3", "title": "Kids-friendly set", "price": 149}
      ]
    }
  },
  "extras": [{"id": "e1", "type": "dessert", "optional": true, "enabled": false}],
  "estimated_cost": 180,
  "messages": [
    {"type": "info", "text": "Ready to execute"},
    {"type": "warning", "text": "Restaurant budget is near limit"}
  ],
  "execution_log": [
    {"step": "activity_booking", "status": "success", "message": "Booked"},
    {"step": "restaurant_booking", "status": "failed", "message": "No slots left"}
  ],
  "map": {
    "markers": [{"lat": 0, "lng": 0, "label": "t1"}],
    "route": [{"lat": 0, "lng": 0}, {"lat": 0, "lng": 0}]
  }
}
```

### Action（前端触发后端）

```json
{
  "type": "intake_answer | replace | chat | toggle_extra | set_duration | choose_bundle | share",
  "payload": {}
}
```

## Integration Option A（推荐）：单体 Streamlit 调用函数

- UI 直接调用后端模块函数：plan() / apply_action() / execute()
- 优点：最少工程量，最适合 demo 与答辩
- 约束：后续拆服务时再把这些函数包成 API

## Integration Option B（可选）：HTTP API（便于前后端分离）

### Endpoints（建议）

- POST `/plan`：输入 constraints/文本，返回 Plan View Model
- POST `/plan/action`：输入 plan_id + action，返回更新后的 Plan View Model
- POST `/plan/execute`：输入 plan_id，返回 execution log + 最终 Plan View Model

### Error Contract（建议统一）

```json
{
  "error": {
    "code": "VALIDATION_FAILED | TOOL_TIMEOUT | EXECUTION_FAILED",
    "message": "human readable",
    "detail": {}
  }
}
```

## Checklist

- Replace/Chat 都走同一条 action 管线，UI 逻辑不分叉
- UI 能展示：plan 状态、校验提示、执行日志、替换结果
- 地图更新与卡片更新基于同一份 Plan View Model
