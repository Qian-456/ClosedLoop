# Frontend 基准：Mobile-first「后端调用台 + 用户体验壳子」+ 演示壳（/demo）

## 0. 结论（先拍板）

你现在不应该做完整前端大工程，而应该做一个 Mobile-first 的 Web SPA「后端调用台 + 用户体验壳子」。

表面上像「本地生活助手 App」，实际核心是把：

```text
用户输入 → 约束确认 → 方案生成 → 方案选择 → 局部调整 →（后续）模拟执行
```

这些操作串起来，稳定调用你的后端。

---

## 1. 推荐结构：真实 App 与演示壳分离

推荐路由结构：

```text
/app     真实移动端页面，不带手机外壳
/demo    演示页，带 iPhone 手机框，内部 iframe 加载 /app
```

好处：

```text
开发真实 App 时不需要反复处理“手机壳”
演示/录屏时直接打开 /demo，就自动套手机框
iframe 内滚动天然生效，鼠标滚轮在屏幕区域里会直接滚动
真实 App 与演示外壳完全隔离，不互相污染
```

---

## 2. /demo：Phone Demo Shell（iframe 方案，推荐）

页面职责：

- `/demo`：只负责“手机框 + iframe”
- `/app/*`：只负责真实业务 UI（按移动端页面写）

示例实现（React + Tailwind）：

```tsx
export default function PhoneDemoPage() {
  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-8">
      <div className="relative w-[430px] h-[900px] rounded-[64px] bg-neutral-950 p-[12px] shadow-2xl">
        <div className="absolute left-[-4px] top-[170px] h-16 w-1 rounded-l bg-neutral-800" />
        <div className="absolute right-[-4px] top-[260px] h-24 w-1 rounded-r bg-neutral-800" />

        <div className="relative h-full w-full overflow-hidden rounded-[52px] bg-white">
          <div className="pointer-events-none absolute left-1/2 top-[18px] z-20 h-[36px] w-[126px] -translate-x-1/2 rounded-full bg-black" />

          <iframe
            src="/app"
            title="local-life-agent-preview"
            className="h-full w-full border-0"
          />
        </div>
      </div>
    </div>
  );
}
```

---

## 3. Router：/demo 与 /app 并存

示例（只示意路由层级）：

```tsx
import { createBrowserRouter } from "react-router";
import PhoneDemoPage from "./pages/PhoneDemoPage";
import AppHomePage from "./pages/AppHomePage";
import ConfirmPage from "./pages/ConfirmPage";
import GeneratingPage from "./pages/GeneratingPage";
import PlansPage from "./pages/PlansPage";
import PlanDetailPage from "./pages/PlanDetailPage";

export const router = createBrowserRouter([
  { path: "/demo", element: <PhoneDemoPage /> },
  { path: "/app", element: <AppHomePage /> },
  { path: "/app/confirm", element: <ConfirmPage /> },
  { path: "/app/generating", element: <GeneratingPage /> },
  { path: "/app/plans", element: <PlansPage /> },
  { path: "/app/plans/:planId", element: <PlanDetailPage /> },
]);
```

建议使用方式：

```text
开发：/app
演示：/demo
```

---

## 4. 真实 App 页面布局建议（避免被底部栏挡住）

移动端页面的基础壳子建议统一：

```tsx
export default function AppHomePage() {
  return <main className="min-h-screen bg-[#F8F8F7] px-5 pt-20 pb-8">{/* ... */}</main>;
}
```

长页面（例如方案详情）建议底部留更大的 padding：

```tsx
export default function PlanDetailPage() {
  return <main className="min-h-screen bg-[#F8F8F7] px-5 pt-16 pb-40">{/* ... */}</main>;
}
```

底部固定操作栏示例：

```tsx
<div className="fixed bottom-0 left-0 right-0 z-30 mx-auto max-w-[430px] rounded-t-[28px] bg-white/90 px-5 pb-6 pt-4 shadow-2xl backdrop-blur">
  <button className="h-14 w-full rounded-full bg-blue-600 text-lg font-semibold text-white">
    选择这套方案
  </button>

  <div className="mt-3 grid grid-cols-3 gap-3">
    <button className="rounded-full bg-slate-100 py-3">降预算</button>
    <button className="rounded-full bg-slate-100 py-3">更亲子</button>
    <button className="rounded-full bg-slate-100 py-3">少走路</button>
  </div>
</div>
```

---

## 5. 备选：不用 iframe 的 PhoneFrame（不推荐）

也可以用组件包裹的方式做手机框，但会把真实 App 和外壳耦合在一起，不利于后续部署、截图、录屏与排查问题。

---

## 6. 推荐技术栈（以当前项目可落地为准）

- React + TypeScript + Vite
- Tailwind CSS
- UI 组件：shadcn/ui（可选但推荐，统一质感与交互）
- 路由：React Router
- 请求/后端状态：TanStack Query
- 前端局部状态：Zustand（只存 UI/会话/当前选中，不存后端缓存数据）
- 表单与校验：React Hook Form + Zod
- 图标：lucide-react
- Mock：MSW（后端不稳定时用于并行推进）
- 类型同步：OpenAPI TypeScript（等后端稳定暴露 OpenAPI 后再接入）

说明：本仓库后端当前已提供 `POST /invoke` 与 `GET /health`，因此 MVP 先以 `invoke` 打通闭环；“6 个标准接口”作为后续演进目标。

---

## 7. 交互链路与状态机（比堆页面更稳）

链路：

```text
首页输入需求
  ↓
约束确认（底部 Sheet）
  ↓
生成中（展示 pipeline）
  ↓
三方案对比
  ↓
方案详情
  ↓
局部调整（再次调用后端）
```

建议状态机（可按你实际 UI 扩展）：

```ts
export type AppStage =
  | "idle"
  | "parsing"
  | "confirming"
  | "generating"
  | "plans_ready"
  | "selected"
  | "adjusting"
  | "executing"
  | "done"
  | "error";
```

说明：

- 当前后端只有 `/invoke`，因此 `adjusting/executing` 更适合作为前端的“规划态/占位态”；真正的“按 plan_id 局部调整/执行”需要等后端拆分接口后再落地。

---

## 8. 路由（先做最小 5 页就够）

```text
/
/generating/:sessionId
/plans/:sessionId
/plan/:planId
/plan/:planId/adjust
```

说明：

- `/plan/:planId/adjust` 当前可先作为占位页面：把用户的“修改意图”转成自然语言补充到 `user_input`，重新调用 `/invoke` 获取新方案。

---

## 9. 后端契约（以当前实现为准）

### 1) Health

- `GET /health`

### 2) Invoke（MVP 唯一执行入口）

- `POST /invoke`
- Request:

```json
{ "user_input": "..." }
```

- Response（后端当前返回 `state`，其中包含核心数据；字段名以 `backend/src/closedloop/contracts/*` 为准）：

```json
{
  "status": "success",
  "state": {
    "user_input": "...",
    "constraints": {
      "group_type": "family",
      "budget": 350,
      "dietary_restrictions": ["辣"],
      "preferred_distance": "2km-5km",
      "time_period": "13:00-18:00",
      "duration_hours": 5.0,
      "activity_preferences": ["亲子", "少走路", "带点小惊喜"],
      "adult_count": 2,
      "child_count": 1,
      "child_ages": [6]
    },
    "candidates": {
      "nearby_restaurants": [],
      "nearby_activities": [],
      "nearby_gifts": [],
      "ranked_breakfast_combos": [],
      "ranked_lunch_combos": [],
      "ranked_afternoon_tea_combos": [],
      "ranked_dinner_combos": [],
      "ranked_late_night_combos": [],
      "ranked_packages": [],
      "ranked_gifts": [],
      "processed_steps": ["retrieve_candidates_node", "filter_node", "rerank_node"]
    },
    "itinerary": {
      "status": "ok",
      "missing_types": [],
      "plans": [
        {
          "plan_id": "plan_1",
          "title": "...",
          "total_duration_minutes": 240,
          "total_cost": 199,
          "average_score": 0.8,
          "selected_item_ids": ["..."],
          "steps": [
            {
              "order_id": "1",
              "duration_minutes": 60,
              "note": "...",
              "item": {
                "id": "...",
                "name": "...",
                "type": "restaurant|activity|gift_shop|commute",
                "location": "某某路 123 号",
                "distance_km": 1.2,
                "cost": 50
              }
            }
          ]
        }
      ]
    }
  }
}
```

前端约定：

- 不依赖后端“会话持久化”，前端用 `sessionId` 仅做路由与本地 store key。
- 方案 id：后端当前是 `plan_1/plan_2/plan_3`，前端路由直接使用该 id。
- 如果 `itinerary.status != ok` 或 `plans` 为空：进入 error 状态并提示可重试。
- 注意：当前后端只有 `/invoke`，无法“前端传入 constraints 让后端只做 generate”。若前端允许用户在确认 Sheet 修改约束，需要把修改后的约束重新组织成自然语言，再次调用 `/invoke`。

---

## 10. 未来演进（规划，未实现）

后续等后端拆分工作流/引入会话与 action 管线后再落地：

```text
POST /api/itinerary/parse
POST /api/itinerary/generate
GET  /api/itinerary/sessions/{session_id}
POST /api/itinerary/plans/{plan_id}/select
POST /api/itinerary/plans/{plan_id}/adjust
POST /api/itinerary/plans/{plan_id}/execute
```

当前阶段：全部通过 `POST /invoke` 串起“解析+召回+规划”。

---

## 11. Debug Panel（建议隐藏入口）

为了演示“工程 pipeline”，建议加隐藏 Debug Panel（默认折叠）：

```text
候选餐厅数 / 候选活动数 / 候选礼品数
rerank 后各时段套餐数（breakfast/lunch/afternoon_tea/dinner/late_night）
pattern 匹配数量 / 过滤后可用方案数 / 最终 topK 方案数
itinerary.status 与 missing_types（候选不足时用于解释）
```

---

## 12. 推荐目录结构（MVP 轻量）

不要一开始搞太重，优先按业务 feature 分：

```text
src/
  app/
    router.tsx
    providers.tsx
    queryClient.ts
    main.tsx

  pages/
    HomePage.tsx
    GeneratingPage.tsx
    PlansPage.tsx
    PlanDetailPage.tsx
    AdjustPage.tsx
    PhoneDemoPage.tsx

  features/
    itinerary/
      api/
      model/
      store/
      components/

  shared/
    ui/
    lib/
```

---

## 13. 运行方式

### 本地（推荐）

- 后端：`python backend/src/main.py`（默认 `127.0.0.1:8000`）
- 前端：`cd frontend && npm run dev`（默认 `127.0.0.1:5173`）

说明：前端通过 Vite proxy 直连后端 `127.0.0.1:8000`，因此本地不依赖 CORS。
