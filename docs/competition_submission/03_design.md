# 设计文档（≤2页）：ClosedLoop 执行型本地生活 Agent（真实链路口径）

## TL;DR

ClosedLoop 是一个执行型本地生活 Agent：用户一句话 → 生成 4–6 小时行程（玩→吃→后续）→ 用户确认 → Mock 执行预约/排队/库存扣减 → 遇到关键失败进入补齐（fixup）继续把事情做完。\
设计目标不是“最炫”，而是**响应快、稳定可复现、能验收、能落地**。

## 赛题约束摘要

- 场景：周末短时 4–6 小时；两类人群：亲子 / 朋友聚会
- 要求：不仅推荐，还要“查座位/排队（Mock）+ 转为可执行动作（Mock）”
- 性能：方案生成 ≤ 30 秒；工具响应 ≤ 3 秒；端到端 ≤ 2 分钟
- 异常覆盖：至少 3 类（执行失败/冲突/无可行方案等）

## 真实架构（两服务 + 内部调用 + 可观测）

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 520" role="img" aria-label="ClosedLoop真实架构图（两服务+可选搜索服务+Mock DB）" style="max-width: 100%; height: auto; display: block; margin: 10px 0 12px;">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L9,3 L0,6 Z" fill="#111827" />
    </marker>
    <style>
      .box { fill: #ffffff; stroke: #111827; stroke-width: 2; rx: 14; }
      .box-dashed { fill: #ffffff; stroke: #111827; stroke-width: 2; stroke-dasharray: 7 6; rx: 14; }
      .title { font: 700 18px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
      .text { font: 13px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
      .muted { fill: #374151; }
      .arrow { stroke: #111827; stroke-width: 2.5; fill: none; marker-end: url(#arrow); }
      .arrow-dashed { stroke: #111827; stroke-width: 2.5; fill: none; stroke-dasharray: 6 6; marker-end: url(#arrow); }
      .label { font: 12px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
    </style>
  </defs>

  <rect x="30" y="30" width="180" height="64" class="box" />
  <text x="50" y="58" class="title">用户/前端</text>
  <text x="50" y="80" class="text muted">HTTP / SSE</text>

  <rect x="30" y="120" width="470" height="240" class="box" />
  <text x="50" y="150" class="title">Main 服务（8000）</text>
  <text x="50" y="174" class="text">对话状态与路由：plan_agent / execute_agent / fixup_agent</text>
  <text x="50" y="198" class="text">工具编排（真实工具名）：</text>
  <text x="70" y="222" class="text">• plan_trip / generate_alternative_plans</text>
  <text x="70" y="244" class="text">• search_candidates / adjust_plan_item</text>
  <text x="70" y="266" class="text">• transfer_to_execute</text>
  <text x="70" y="288" class="text">• execute_itinerary / adjust_and_execute_plan_item</text>
  <text x="50" y="322" class="text muted">执行期：mock_executor（扣库存/扣容量/排队事件/回滚）</text>

  <rect x="530" y="120" width="420" height="140" class="box" />
  <text x="550" y="150" class="title">Plan 子服务（8001）</text>
  <text x="550" y="176" class="text">重检索 / 过滤 / 排序 / 组合规划（确定性骨架）</text>
  <text x="550" y="200" class="text">输出：itinerary + candidates（候选池）</text>

  <rect x="530" y="280" width="420" height="92" class="box-dashed" />
  <text x="550" y="310" class="title">Search 子服务（8002，可选）</text>
  <text x="550" y="336" class="text">输入：候选池 + 用户关键词</text>
  <text x="550" y="358" class="text">输出：top_k 命中结果（失败可恢复）</text>

  <rect x="30" y="392" width="920" height="98" class="box" />
  <text x="50" y="422" class="title">Mock DB</text>
  <text x="50" y="446" class="text">静态数据（规划期读取）：餐厅 / 活动 / 礼物 / 预约</text>
  <text x="50" y="468" class="text">运行时数据（执行期写入）：库存 / 容量扣减与回滚（用于稳定复现演示）</text>

  <path d="M210 62 L30 62" stroke="transparent" />
  <path d="M210 62 L265 62 L265 140 L30 140" stroke="transparent" />

  <path d="M210 62 L265 62 L265 120" class="arrow" />
  <text x="278" y="84" class="label">HTTP</text>

  <path d="M500 200 L530 200" class="arrow" />
  <text x="468" y="188" class="label">内部 HTTP</text>

  <path d="M500 308 L530 308" class="arrow-dashed" />
  <text x="438" y="298" class="label">可选调用</text>

  <path d="M260 360 L260 392" class="arrow" />
  <text x="276" y="382" class="label">执行期写入/回滚</text>

  <path d="M740 260 L740 392" class="arrow" />
  <text x="756" y="322" class="label">规划期读取</text>
</svg>

若 Markdown 渲染器不支持内嵌 SVG，可直接打开同目录的 `03_design.html` 查看离线版（图与样式都已内嵌）。

说明：

- 两服务拆分用于模块化与可观测性：规划子服务可单独监控、限流与扩容，避免规划重负载影响主对话体验。
- 内部 HTTP 仅用于本地/容器内模块通信，所有“下单/预约/排队”均为 Mock。

## 工具调用链路（用户动作闭环）

```text
一句话需求
  ↓（plan_agent：语义理解+参数归一化）
plan_trip（≤3s）→ Main(8000) 内部 HTTP → Plan(8001) → 返回 itinerary + candidates
  ↓
用户确认 / 想改
  - 改约束/改结构：仍走 plan_trip（同一入口，体验一致）
  - 只想多看：generate_alternative_plans
  - 指定替换：search_candidates → adjust_plan_item
  ↓
确认执行
  ↓（execute_agent）
transfer_to_execute → execute_itinerary → mock_executor（库存/容量扣减+事件）
  ↓
若失败需要补齐
  ↓（fixup_agent）
候选1/2 或 search → adjust_and_execute_plan_item（替换+重试执行）
```

设计原则：

- 确定性模块负责“可行性与稳定性”（时空约束、预算、回滚、一致性校验）；LLM 负责“理解、解释、协商与低打扰交互”。
- 对波动强的可用性（无座/排队）不在规划期做硬过滤：规划期做风险提示与备选；执行期做硬检查并兜底，保证端到端稳定性。

## Mock 数据契约（面向可执行性）

关键语义（规划与执行共同消费）：

- `duration_mins + duration_std_dev`：规划期留 buffer，避免排得过满
- `capacity_remaining`：执行期硬检查依据；为 0 表示无座/无票
- `queue_required + wait_minutes`：拟真排队体验（规划期提示风险、执行期产生过程事件）
- `available_stock / stock`：执行期可扣减库存（活动票、礼物）

## 异常覆盖（≥3类，策略顺序）

### 1) 执行失败（无座/无票/库存不足）

- 执行期对 combo/package 做硬预订；失败时优先使用 plan 侧生成的备选进行替换。
- 若备选需要用户确认或备选不足，进入 `confirmation.status=needs_fixup`，交给 fixup\_agent 给 1–2 个选项并继续推进。
- 为保证可复现：执行前对运行时数据（runtime JSON）快照；当执行一致性校验失败（例如 Mock 扣减/Mock 支付相关一致性不满足）时，回滚运行时数据并返回可重试错误码。

### 2) 用户修改导致冲突（替换后超窗/超预算）

- 替换走确定性修复：优先最小改动（buffer/压缩），避免静默破坏体验。
- 当修复需要删减用户已确认的核心步骤或仍无法修复时，返回结构化失败信息交给 Agent 解释与协商（不做无感删项）。

### 3) 无可行方案（0 候选 / 规划失败）

- 当硬约束过强导致无法产出方案，系统返回可恢复错误，并引导用户放宽最小必要约束（预算、距离、窗口、偏好等）。
- 当规划子服务不可用/超时（≤3s），主服务返回 `TOOL_TIMEOUT`，不中断对话，可重试或改用再规划。

## 为什么不是纯 LLM 端到端（以及取舍说明，口径A）

多约束、强时空、强可执行任务（距离/时间窗/库存/排队）对稳定性要求高。纯 LLM 端到端容易出现“看起来合理但不可执行”，且多轮生成会显著拉长等待时间。\
因此系统采用“确定性规划骨架 + LLM 交互增益”的路线：在严格时延约束下优先保证稳定验收与可落地。

取舍说明（不点名技术栈）：

- 工程原则：主链路优先保证响应与稳定验收；线上演进可与平台既有能力融合（推荐侧用用户数据优化排序打分，搜索侧接入现有检索引擎）。
- 人机协同采用轻量补齐（fixup\_agent）：只在关键失败点要求用户明确选择，其余尽量自动兜底，保证闭环成功率与可复现演示。

## 验收方式（与 Demo 对齐）

- 正常链路：能完成“规划 → 选择 → 执行”闭环，并产出 execution\_summary（含每步 reserved 与 before/after 字段）。
- 故障链路：通过将某些时段容量设为 0 或删除对应时段记录，稳定触发“执行失败 → 备选替换 / needs\_fixup”，并观察系统是否继续把事情做完。
