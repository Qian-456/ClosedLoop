# README.md & AGENTS.md 大幅更新（面向前端协作）设计说明

## 目标

- 让新同学（尤其是前端同学）在不读代码的前提下，快速搞清楚：
  - 项目是什么、能做什么、不能做什么
  - 当前“真实可用”的后端契约是什么
  - 前端应该围绕哪些数据结构与流式事件来实现/迭代 UI
- 把“易踩坑/契约幻觉”的信息从口口相传改为文档强约束，减少误接/误改。

## 非目标

- 不在 README/AGENTS 中写“未来规划功能”的详细实现步骤。
- 不把 README 做成所有细节的百科全书；细节仅在“前端必需契约”范围内展开。

## 读者定位与信息分层

- README.md：面向所有人（新同学、评审、前端/后端/产品），强调“定位 + 跑起来 + 当前可用接口 + 最少必要的前端接入说明”。
- AGENTS.md：面向开发者（尤其是会改动前端/后端契约的人），强调“强制约束 + 前后端契约 + 禁区 + 口径统一”。

## 现状诊断（需要解决的问题）

- README 当前包含已不再对外开放/不建议前端接入的接口说明（例如 `/execute/*`），容易诱导前端走旧链路。
- 文档中存在与代码实现不一致的描述风险：
  - 流式协议：README 仍偏“state snapshot SSE”的旧说法，而后端现实现已输出产品级事件（message/bubble/result/done/error）。
  - 推荐方案数据源：前端应对齐 `itinerary`，后端已在序列化层做了包装与 fallback。
- 前端同学最需要的“怎么读数据/怎么消费流/哪些字段稳定”散落在不同文件里，缺乏集中说明。

## 决策（本次更新的关键口径）

### 1) README 移除 `/execute/*` 描述

- README 只保留当前对外入口：
  - `GET /health`
  - `POST /invoke`
  - `POST /invoke/stream`
- `/execute/*` 如仍在仓库中存在，视为内部测试或历史能力，不在 README 提供接入承诺。

### 2) 强化前端“推荐方案面板”口径

- 聊天区不应复述完整时间轴/逐步行程：Agent 在首次规划后只输出 1–2 行摘要，并明确提示“详细方案请看前端下方【推荐方案】面板”。
- “推荐方案面板”的数据源定义：
  - 优先读取 `state.itinerary`。
  - 若后端返回 `itinerary` 为列表，后端序列化会包装成 `{ plans: [...] }`。
  - 仅当缺失 `itinerary` 时，后端才 fallback 到 `latest_plan_result` 并同样包装成 `{ plans: [...] }`。

### 3) 明确流式事件协议为产品级事件（不等同于 LangGraph 原始 mode）

- `POST /invoke/stream` 输出 SSE 事件：
  - `message`：面向聊天 UI 的文本片段（不是逐 token 的底层流式协议承诺，但可视作“可拼接的输出片段”）。
  - `bubble`：阶段/工具进度（面向状态栏或流程气泡 UI）。
  - `result`：核心结果对象（itinerary/confirmation/constraints/current_step 的增量）。
  - `done`：请求结束。
  - `error`：请求失败。
- 前端以事件类型驱动 UI 分层：聊天区消费 message；流程区消费 bubble；结果区消费 result。

## 文档结构设计

### README.md（建议目录）

1. 项目定位（一句话 + 关键约束：执行为 Mock、禁止真实网络调用）
2. 你能得到什么（输入一句话 → 约束 → 多方案 → 推荐方案面板展示）
3. 快速开始
   - 后端
   - 前端
4. API（只写当前对外承诺）
   - health
   - invoke（返回 state）
   - invoke/stream（事件协议）
5. 给前端同学的必读 5 条
   - thread_id 必传/持久化
   - 事件协议分层（message/bubble/result）
   - 聊天摘要 vs 推荐方案面板
   - 推荐方案数据源（itinerary 优先）
   - 契约改动的唯一真相：后端序列化与 contracts
6. 分支约定（保持简短）
7. 环境变量（列关键项即可；细节留给 backend/.env.example）

### AGENTS.md（建议目录）

1. 项目定位与技术栈（保留现有简洁描述）
2. Workflow Contract（Graph 是唯一入口、状态必须显式存储、禁止绕过）
3. Infrastructure Contract（get_config/build_agent/logger 强制规则）
4. Frontend Contract（新增/强化）
   - 推荐方案面板数据源与兼容逻辑
   - invoke/stream 事件协议（字段级说明）
   - UI 口径与 Agent 文案约束（摘要输出规则、等待确认、不二次确认等）
5. 数据与空间约束（Mock DB 物理/业务约束，确保与当前实现一致）
6. 测试约束（happy path/clarify/contract）

## 变更清单（文件级）

- 更新 `README.md`
  - 删除 `/execute/*` 相关章节与说明
  - 更新 `/invoke/stream` 的事件契约描述为 message/bubble/result/done/error
  - 新增“前端必读 5 条”与“推荐方案数据源”说明
- 更新 `AGENTS.md`
  - 新增/强化 Frontend Contract（推荐方案面板 & 流式事件协议）
  - 同步与当前实现不一致的描述，避免契约幻觉

## 验收标准

- 前端同学只读 README 即可在 10 分钟内理解：
  - 接哪个接口、拿到什么事件、推荐方案展示从哪读
- 开发者只读 AGENTS.md 即可知道：
  - 哪些改动是“允许的”、哪些是“禁止的”
  - 改动契约时应该同步哪里，如何避免前端误接旧链路

