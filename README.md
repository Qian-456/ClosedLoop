# ClosedLoop

ClosedLoop 是一个执行型本地生活 Agent：用户一句话需求 → 生成可执行行程（4–6 小时）→ 用户确认 → 自动执行（Mock）→ 失败 fallback / replan。

## 核心能力

- 约束提取：从自然语言中提取人群/预算/时段/偏好等结构化约束
- 候选召回与过滤：基于本地 Mock DB 进行召回，并进行硬性规则过滤
- 排序与规划：三维度打分排序 + 路线/餐次组合规划，产出多套方案供确认
- Mock 执行：确认后模拟预约/排队/下单等动作，并通过 SSE 推送执行事件流

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
- `POST /invoke`：输入一句话需求，返回 Graph 运行后的 state（包含候选与方案）
- `POST /execute/start`：启动 Mock 执行，返回 execution_id
- `GET /execute/events/{execution_id}`：SSE 事件流

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

前端开发时会通过 Vite proxy 转发 `/invoke`、`/health`、`/execute/*` 到后端（默认 `http://127.0.0.1:8000`）。

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

- `phase=planner_dfs_stats`：每个 pattern 的 step_pool_sizes、合法叶子数、剪枝计数（能直接判断是不是 gift/下午茶候选不足）
- `phase=planner_candidate_pool_stats`：candidate_pool 去重前后与补齐后的数量（能直接判断是不是“抽样+去重”导致只剩 1-2 套）

## ELK（可选）

ELK 的 Logstash 会读取 `backend/src/logs/elk.jsonl` 并写入 Elasticsearch，索引名为 `closedloop-YYYY.MM.dd`（见 `docker/elk/logstash.conf`）。

Kibana 使用建议：

**- 进入 Kibana → 创建 Index Patterm：`closedloop-*`
- 时间字段选择 `@timestamp`**
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
