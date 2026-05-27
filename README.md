# ClosedLoop

ClosedLoop 是一个执行型本地生活 Agent：用户一句话需求 → 生成可执行行程（4–6 小时）→ 用户确认 → 自动执行（Mock）→ 失败 fallback / replan。

## 核心能力

- 约束提取：从自然语言中提取人群/预算/时段/偏好等结构化约束
- 候选召回与过滤：基于本地 Mock DB 进行召回，并进行硬性规则过滤
- 排序与规划：三维度打分排序 + 路线/餐次组合规划，产出多套方案供确认
- Mock 执行：确认后模拟预约/排队/下单等动作（不做真实本地生活平台调用）

## 架构概览

- 后端：Python + FastAPI
- 编排：LangChain + LangGraph（Graph 是唯一执行入口）
- 数据：仓库内 `mock_db/`（本地生活拟真数据）
- 执行：全部为 Mock（不做真实本地生活平台调用）

## Handoff 架构

当前代码以 LangGraph 流水线稳定跑通“约束提取 → 召回/过滤/排序 → 规划 → 产出多套方案”。下一步演进方向是 handoff 架构：把输出从“自然语言结果”升级为“结构化交接物（handoff packet）”，并拆分为 Plan → Tune/Confirm → Execute 多窗口闭环。

- 设计记录：`docs/14_handoff_architecture.md`

## API 概览

- `GET /health`：健康检查
- `POST /invoke`：输入一句话需求，返回 Graph 运行后的完整 state（兼容旧 JSON 调用）
- `POST /invoke/stream`：输入一句话需求，返回 `text/event-stream`，持续推送产品级事件（见下方事件契约）

## Docker 一键启动

1. 配置后端环境变量：复制 `backend/.env.example` 为 `backend/.env` 并填写 Key

```bash
cp backend/.env.example backend/.env
```

### 本地开发与运行 (微服务解耦模式)

为了方便调试，目前将底层基础设施通过 Docker 部署，主业务流程通过本地 CLI 运行。

**1. 启动底层依赖与微服务**

```bash
docker compose up -d --build
```

> 此命令会在后台启动 `etcd`、`minio`、`milvus-standalone` 以及拆分出的独立规划服务 `plan_sub_backend`。

**2. 运行主业务流**
等待 Docker 容器启动完成后，在您的本地 Python 环境中执行：

```bash
python backend/src/cli_main.py
```

> 本地直接运行主后端时，`backend/.env` 中的 `PLAN_SUB_API_URL` 建议配置为 `http://localhost:8001/plan` 或 `http://127.0.0.1:8001/plan`。只有当主后端本身也运行在 Docker 网络中时，才使用 `http://plan_sub_backend:8001/plan`。

### 生产全量部署 (包含 ELK 日志收集)

如果需要启动全套服务（包含日志中心），您可以叠加使用 elk 的 compose 文件：

```bash
docker compose -f docker-compose.yml -f docker/elk/docker-compose.elk.yml up -d --build
```

访问：

- 前端：`http://localhost:8080`
- 健康检查：`http://localhost:8080/health`
- （可选直连后端）`http://localhost:8000/health`
- （可选）Kibana：`http://localhost:5601`

## 本地开发

### 后端

在 `backend/src` 目录下启动：

```bash
python main.py
```

默认监听 `http://localhost:8000`。

### 前端

在 `frontend` 目录下启动：

```bash
npm ci
npm run dev
```

前端开发时会通过 Vite proxy 转发 `/invoke`、`/invoke/stream`、`/health` 到后端（默认 `http://127.0.0.1:8000`）。

### `/invoke/stream` 事件契约

- `message`：聊天区文本片段（用于逐步展示回答文本）
- `bubble`：流程/阶段气泡（用于状态栏或 pipeline UI）
- `result`：结构化结果增量（用于推荐方案面板、约束确认等）
- `done`：请求结束
- `error`：请求失败（包含错误信息与可恢复标记）

说明：

- 前端应使用 `fetch + ReadableStream` 读取 `POST /invoke/stream`，因为请求体需要携带 `user_input` 与 `thread_id`。
- `result` 事件里的 `itinerary` 是前端“推荐方案”面板的数据源（优先读取 `state.itinerary`）。

## 给前端同学的必读 5 条

1. `thread_id` 必传并持久化：它是后端 LangGraph 的会话标识，用于多轮对话与多会话隔离。
2. 事件分层消费：聊天区消费 `message`；流程区消费 `bubble`；结果区（推荐方案面板）消费 `result`。
3. 聊天区只展示摘要：规划工具返回后，Agent 只会输出 1–2 行摘要，并提示“详细方案看【推荐方案】面板”，前端不要在聊天区复述完整时间轴。
4. 推荐方案面板数据源对齐 `itinerary`：后端会保证 `itinerary` 的形状尽量稳定（必要时包装为 `{ plans: [...] }`）。
5. 契约改动以代码为准：字段与事件的最终定义以 `backend/src/main.py` 的序列化与 SSE 归一化为准。

## 分支约定

- `main`：稳定主分支（用于演示与比赛提交）
- `dev_agent`：Agent/编排/工具链相关的迭代分支（从 main 拉出）

## 环境变量

后端环境变量模板位于 `backend/.env.example`，其中关键项：

- `DEEPSEEK_API_KEY`：Primary LLM
- `DASHSCOPE_API_KEY`：Fallback LLM

日志/调试相关：

- `LOG_ELK_ENABLED`：是否输出结构化日志（JSONL）到 `LOG_ELK_JSON_PATH`
- `LOG_ELK_JSON_PATH`：结构化日志路径（默认 `backend/src/logs/elk.jsonl`）
- `FILTER_LOG_DETAILED_DEBUG`：是否输出过滤阶段的明细 drop 事件（用于排查误杀/漏杀）
- `LOG_PLANNER_STATS`：是否输出规划阶段的统计日志（pattern 维度剪枝计数、候选池去重前后、展示层选 3 套前后计数）
- `PLANNER_LOG_DETAILED_DEBUG`：预留开关（当前仅实现统计汇总，不输出逐条组合明细）

如果你启用了 ELK，请确保后端开启结构化日志输出（否则 Kibana 没数据可查）：

```bash
LOG_ELK_ENABLED=true
```

当你遇到“为什么只生成了 1-2 套方案”的问题，推荐先打开：

```bash
LOG_PLANNER_STATS=true
```

然后观察日志中的：

- `phase=planner_dfs_stats`：每个 pattern 的 step\_pool\_sizes、合法叶子数、剪枝计数（能直接判断是不是 gift/下午茶候选不足）
- `phase=planner_candidate_pool_stats`：candidate\_pool 去重前后与补齐后的数量（能直接判断是不是“抽样+去重”导致只剩 1-2 套）

## ELK（可选）

ELK 的 Logstash 会读取 `backend/src/logs/elk.jsonl` 并写入 Elasticsearch，索引名为 `closedloop-YYYY.MM.dd`（见 `docker/elk/logstash.conf`）。

Kibana 使用建议：

\*\*- 进入 Kibana → 创建 Index Patterm：`closedloop-*`

- 时间字段选择 `@timestamp`\*\*
- 常用检索关键字：
  - `phase=filter_node` / `phase=rerank_node` / `phase=planner_node`
  - `phase=planner_dfs_stats` / `phase=planner_candidate_pool_stats`

## 测试

后端（unittest）：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

前端（vitest）：

```bash
npm test -- --run
```
