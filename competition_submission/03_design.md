# 设计文档：ClosedLoop 执行型本地生活 Agent

## TL;DR

ClosedLoop 是一个执行型本地生活 Agent：用户一句话 → 生成 4–6 小时行程（玩→吃→后续）→ 用户确认 → 生成待支付执行命令 → 输入 Mock 支付密码 `111111` → 付款后 Mock commit → 关键失败进入补齐（fixup）继续把事情做完。  
设计目标不是“最炫”，而是**响应快、稳定可复现、能落地**（单工具 ≤ 3s，规划 ≤ 30s，端到端 ≤ 2min；失败可恢复且状态不污染）。

## 背景（S）

本赛题要求在周末 4–6 小时窗口内完成“规划 → 确认 → Mock 执行”的闭环，并满足严格时延预算与稳定验收（可复现、失败可恢复）。

## 难点（C）

- 规划侧：端到端 LLM 难稳定满足强时空/预算约束，且多轮工具补算易超时，输出不确定。
- 执行侧：确认执行后先生成待支付命令，付款前不占用/扣减资源；Mock commit 时仍可能触发无座、无库存，必须支持失败兜底与低打扰补齐（fixup）以保证闭环成功率。
- 工程侧：在严格时延预算下，还要做到超时/降级/可恢复错误，且保证状态不污染、结果可复现。

## 关键问题（Q）

如何在严格时延预算下，把“多约束规划 + Mock 执行 + 失败自愈”做成稳定、可复现、可快速验收的闭环？

## 方案（A：Planning 策略）

- **Planning 策略（确定性骨架）**：确定性模块负责候选召回/过滤/排序与时空预算校验，LLM 只做语义约束抽取与解释协商（细节与工程证据见 02_tools.md）。
- 单一入口 + 轻量补齐：首次规划/改约束统一走 `plan_trip`；执行失败优先静默等价替换，必须打扰时进入 `fixup_agent` 给 1–2 个选项继续推进。
- 可复现工程化：付款前只做可用性检查与命令生成；输入 Mock 支付密码 `111111` 后才提交 Mock commit，避免付款前副作用污染（工程证据详见 02_tools.md）。

## 真实架构（两服务 + 内部调用 + 可观测）

<svg
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 1040 520"
  role="img"
  aria-label="ClosedLoop真实架构图（两服务+可选搜索服务+Mock DB）"
  style="max-width: 100%; height: 320px; display: block; margin: 10px 0 12px;"
>
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
  <text x="50" y="322" class="text muted">执行期：mock_executor（命令生成/Mock 支付/commit）</text>

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
  <text x="50" y="468" class="text">运行时数据（付款后写入）：库存 / 容量 Mock commit（用于稳定复现演示）</text>

  <path d="M210 62 L265 62 L265 120" class="arrow" />
  <text x="278" y="84" class="label">HTTP</text>

  <path d="M500 200 L530 200" class="arrow" />
  <text x="468" y="188" class="label">内部 HTTP</text>

  <path d="M500 308 L530 308" class="arrow-dashed" />
  <text x="438" y="298" class="label">可选调用</text>

  <path d="M260 360 L260 392" class="arrow" />
  <text x="276" y="382" class="label">付款后 commit</text>

  <path d="M950 200 L980 200 L980 441 L950 441" class="arrow" />
  <text x="986" y="322" class="label">规划期读取</text>
</svg>

说明：Main(8000) 负责对话路由与工具编排；Plan(8001) 负责确定性规划产出 itinerary + candidates；Search(8002) 为可选“先搜再换”；Mock DB 分静态读（规划期）与付款后写（Mock commit）。

## 工具调用链路（用户动作闭环）

- 规划：`plan_trip` → itinerary + candidates（候选池用于后续搜索/替换）。
- 修改/多看/替换：改约束仍走 `plan_trip`；想多看走 `generate_alternative_plans`；指定替换走 `search_candidates → adjust_plan_item`。
- 确认执行：`transfer_to_execute → execute_itinerary → 生成待支付执行命令 → 输入 111111 模拟付款 → mock_executor commit`；失败进入 `fixup_agent`，选候选/搜索后走 `adjust_and_execute_plan_item`。

## 异常覆盖（3类）

### 1) 执行失败（无座/无票/库存不足）

- 失败分层与低打扰推进：若该 step 未被用户指定/锁定（`user_touched=false`，适用于活动/餐厅/礼物），且备选不会导致超预算/超时或明显偏好受损（`requires_confirmation=false`），则静默替换并继续执行；否则进入 `confirmation.status=needs_fixup`，由 fixup\_agent 给 1–2 个选项并继续推进（本版本主要支持 equivalent_only；strict/completion_first 暂未在全链路启用）。
- 备选自动替换（等价优先）：命令生成期对 combo/package 做可用性检查；失败时优先使用规划阶段为每个 step 预生成的 2 个 `backup_candidates` 进行替换（默认策略 `replacement_policy=equivalent_only`）。
- 工程兜底：付款前不写运行时数据；Mock 支付密码校验通过后才进入 commit，若提交期一致性不满足则返回可重试错误码。

### 2) 用户修改导致冲突（替换后超窗/超预算）

- 替换走确定性修复：优先最小改动（吃 buffer/压缩可压缩项目），避免静默破坏体验。
- 若替换后仍出现超窗/超预算，当前版本不会静默强行写入不可行方案，而是将该情况暴露为冲突场景，由 Agent 向用户解释需要重新调整。诸如“保留但延长”“撤销本次替换”“自动生成多种冲突解法”等能力，当前作为后续增强方向。

### 3) 无可行方案（0 候选 / 规划失败）

- 当硬约束过强导致无法产出方案，系统返回可恢复错误，并引导用户放宽最小必要约束（预算、距离、窗口、偏好等）。
- 当规划子服务不可用/超时（≤3s），主服务返回 `TOOL_TIMEOUT`，不中断对话，可重试或改用再规划。

## 取舍说明（补充）

- 相比纯 LLM 端到端：确定性骨架兜底可行性与稳定性，避免多轮补算导致等待变长与输出不稳。
- 相比过细微服务拆分：仅保留主链路必要的服务边界，减少接口契约与排障成本，优先保证可验收。
- 工程证据（失败码/验收动作/实现索引/付款门控一致性）统一收敛在 02_tools.md，design 只保留闭环叙事口径。
