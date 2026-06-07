# 设计文档：ClosedLoop 执行型本地生活 Agent

## TL;DR

ClosedLoop 是一个执行型本地生活 Agent：用户一句话 → 生成 4–6 小时行程（玩→吃→后续）→ 用户确认 → 生成待支付执行命令前先做一致性校验与必要补齐（fixup）→ 校验通过后生成待支付执行命令 → 输入 Mock 支付密码 `111111` → 付款后 Mock commit。  
设计目标不是“最炫”，而是**响应快、稳定可复现、能落地**（单工具 ≤ 3s，规划 ≤ 30s，端到端 ≤ 2min；失败可恢复且状态不污染）。

## 背景（S）

本赛题要求在周末 4–6 小时窗口内完成“规划 → 确认 → Mock 执行”的闭环，并满足严格时延预算与稳定验收（可复现、失败可恢复）。

## 难点（C）

- 规划侧：端到端 LLM 难稳定满足强时空/预算约束，且多轮工具补算易超时，输出不确定。
- 执行侧：确认执行后不会立刻让用户付款，而是先做执行前一致性校验与必要补齐（fixup）；只有在库存、座位与备选问题处理完成后，才生成待支付命令。这样可以避免用户先付款、后补齐，进而减少退款或二次支付。
- 工程侧：在严格时延预算下，还要做到超时/降级/可恢复错误，且保证状态不污染、结果可复现。

## 关键问题（Q）

如何在严格时延预算下，把“多约束规划 + Mock 执行 + 失败自愈”做成稳定、可复现、可快速验收的闭环？

## 方案（A：Planning 策略）

- **Planning 策略（确定性骨架）**：确定性模块负责候选召回/过滤/排序与时空预算校验，LLM 只做语义约束抽取与解释协商（细节与工程证据见 02_tools.md）。
- 单一入口 + 轻量补齐：首次规划/改约束统一走 `plan_trip`；执行失败优先静默等价替换，必须打扰时进入 `fixup_agent` 给 1–2 个选项继续推进。
- 可复现工程化：付款前只做可用性检查与命令生成；输入 Mock 支付密码 `111111` 后才提交 Mock commit，避免付款前副作用污染（工程证据详见 02_tools.md）。

## 真实架构图

<svg
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 980 410"
  role="img"
  aria-label="ClosedLoop真实架构图：execute_agent 直接进入 pending_payment，fixup 为异常回路"
  style="max-width: 100%; height: 330px; display: block; margin: 8px 0 12px;"
>
  <defs>
    <marker id="arrow-flow-v4" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L9,3 L0,6 Z" fill="#111827" />
    </marker>
    <style>
      .b4 { fill: #fff; stroke: #111827; stroke-width: 2; rx: 12; }
      .s4 { fill: #f9fafb; stroke: #111827; stroke-width: 2; rx: 12; }
      .d4 { fill: #fff; stroke: #111827; stroke-width: 2; }
      .t4 { font: 700 15px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
      .x4 { font: 11px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
      .h4 { font: 700 13px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
      .m4 { fill: #374151; }
      .a4 { stroke: #111827; stroke-width: 2.2; fill: none; marker-end: url(#arrow-flow-v4); }
      .q4 { stroke: #111827; stroke-width: 1.8; fill: none; stroke-dasharray: 5 5; marker-end: url(#arrow-flow-v4); }
      .g4 { stroke: #9ca3af; stroke-width: 1.3; stroke-dasharray: 6 6; }
      .l4 { font: 10px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial; fill: #111827; }
    </style>
  </defs>

  <text x="34" y="28" class="h4">规划阶段</text>
  <line x1="30" y1="42" x2="945" y2="42" class="g4" />
  <text x="34" y="210" class="h4">执行阶段</text>
  <line x1="30" y1="224" x2="945" y2="224" class="g4" />

  <rect x="40" y="68" width="145" height="58" class="b4" />
  <text x="58" y="92" class="t4">用户输入需求</text>
  <text x="58" y="114" class="x4 m4">玩 / 吃 / 后续 / 约束</text>

  <rect x="220" y="56" width="200" height="82" class="b4" />
  <text x="240" y="82" class="t4">plan_agent</text>
  <text x="240" y="106" class="x4">plan_trip / alternatives</text>
  <text x="240" y="126" class="x4">search / adjust plan item</text>

  <rect x="460" y="62" width="200" height="58" class="s4" />
  <text x="480" y="88" class="t4">Plan 子服务 8001</text>
  <text x="480" y="110" class="x4 m4">retrieve / filter / rerank / planner</text>

  <rect x="460" y="146" width="200" height="52" class="s4" />
  <text x="480" y="168" class="t4">Search 子服务 8002</text>
  <text x="480" y="188" class="x4 m4">候选检索 / search / fixup</text>

  <rect x="705" y="64" width="205" height="70" class="b4" />
  <text x="725" y="90" class="t4">itinerary + candidates</text>
  <text x="725" y="114" class="x4">推荐方案 + 候选池</text>
  <text x="725" y="130" class="x4 m4">确认后进入执行</text>

  <rect x="40" y="282" width="145" height="58" class="b4" />
  <text x="58" y="306" class="t4">用户确认方案</text>
  <text x="58" y="328" class="x4 m4">transfer_to_execute</text>

  <rect x="220" y="272" width="200" height="76" class="b4" />
  <text x="240" y="298" class="t4">execute_agent</text>
  <text x="240" y="322" class="x4">execute_itinerary</text>
  <text x="240" y="340" class="x4 m4">execute_itinerary / check core</text>

  <polygon points="520,260 610,310 520,360 430,310" class="d4" />
  <text x="477" y="306" class="t4">需要 fixup?</text>
  <text x="490" y="328" class="x4 m4">库存 / 座位 / 备选</text>

  <rect x="670" y="238" width="200" height="76" class="s4" />
  <text x="690" y="264" class="t4">fixup_agent</text>
  <text x="690" y="288" class="x4">search_candidates</text>
  <text x="690" y="306" class="x4">adjust_and_execute_plan_item</text>

  <rect x="670" y="340" width="160" height="56" class="b4" />
  <text x="690" y="364" class="t4">pending_payment</text>
  <text x="690" y="386" class="x4 m4">待支付执行命令</text>

  <rect x="855" y="340" width="82" height="56" class="b4" />
  <text x="872" y="364" class="t4">Mock</text>
  <text x="872" y="386" class="x4 m4">commit</text>

  <path d="M185 97 L220 97" class="a4" />
  <path d="M420 91 L460 91" class="a4" />
  <path d="M660 91 L705 91" class="a4" />
  <path d="M320 138 L320 172 L460 172" class="q4" />
  <text x="332" y="162" class="l4">search / adjust</text>
  <path d="M660 172 L705 126" class="q4" />
  <path d="M808 134 L808 212 L112 212 L112 282" class="a4" />
  <text x="690" y="204" class="l4">用户确认后进入执行</text>

  <path d="M185 311 L220 311" class="a4" />
  <path d="M420 310 L430 310" class="a4" />
  <path d="M610 310 L670 368" class="a4" />
  <text x="612" y="352" class="l4">否，直接付款</text>
  <path d="M520 260 L520 226 L770 226 L770 238" class="a4" />
  <text x="560" y="218" class="l4">是，进入补齐</text>
  <path d="M770 238 L770 198 L660 172" class="q4" />
  <text x="782" y="210" class="l4">可搜索候选</text>
  <path d="M670 276 L640 276 L640 238 L320 238 L320 272" class="a4" />
  <text x="432" y="232" class="l4">补齐后复用 execute_itinerary 校验</text>
  <path d="M830 368 L855 368" class="a4" />
  <text x="838" y="358" class="l4">支付后</text>
</svg>


说明：这里保留最关键的一张架构图，并把 `plan / search / adjust / execute / fixup` 放进同一条闭环链路。上半部分是规划阶段：`plan_agent` 负责 `plan_trip / generate_alternative_plans / search_candidates / adjust_plan_item`，并可调用 Plan 子服务与可选 Search 子服务，最终产出 `itinerary + candidates`。下半部分是执行阶段：用户确认后进入 `execute_agent`；如果执行前检查与一致性校验直接通过，`execute_itinerary` 会生成共享的 `pending_payment`；如果发现库存、座位或备选问题，则进入 `fixup_agent`，通过 `search_candidates / adjust_and_execute_plan_item` 补齐，并在工具层复用 `execute_itinerary` 的确定性校验，通过后进入同一个 `pending_payment`，最后才是用户支付与 Mock commit。

## 工具调用链路（用户动作闭环）

- 规划：`plan_trip` → itinerary + candidates（候选池用于后续搜索/替换）。
- 修改/多看/替换：改约束仍走 `plan_trip`；想多看走 `generate_alternative_plans`；指定替换走 `search_candidates → adjust_plan_item`。
- 确认执行：`transfer_to_execute → execute_itinerary`；若执行前发现库存/座位/一致性问题，则先进入 `fixup_agent`，由用户选候选或搜索后走 `adjust_and_execute_plan_item`；只有补齐完成且一致性校验通过后，才会生成待支付执行命令并在输入 `111111` 后进入 `mock_executor commit`。

## 异常覆盖（3类）

### 1) 执行失败（无座/无票/库存不足）

- 失败分层与低打扰推进：若该 step 未被用户指定/锁定（`user_touched=false`，适用于活动/餐厅/礼物），且备选不会导致超预算/超时或明显偏好受损（`requires_confirmation=false`），则静默替换并继续执行；否则进入 `confirmation.status=needs_fixup`，由 fixup\_agent 给 1–2 个选项并继续推进（本版本主要支持 equivalent_only；strict/completion_first 暂未在全链路启用）。
- 备选自动替换（等价优先）：在准备生成待支付执行单时，会先检查 combo/package 还能不能下单；如果发现不可用，就优先使用规划阶段为每个 step 预生成的 2 个 `backup_candidates` 做等价替换（默认策略 `replacement_policy=equivalent_only`）。
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
