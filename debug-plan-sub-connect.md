# [OPEN] plan-sub-connect

## 症状

- 主服务调用 `8001/plan` 时出现 `Connection refused` 与 `timed out`
- 日志中同时出现 `localhost`、`127.0.0.1` 与 `plan_sub_backend`

## 初始假设

1. `plan_sub_main.py` 实际未启动，或启动后很快异常退出。
2. `PLAN_SUB_API_URL` 在不同环境源中不一致，导致主服务轮流访问了错误地址。
3. `plan_sub_main.py` 启动阶段被阻塞，例如向量重建或其他 lifespan 初始化过久，端口尚未就绪。
4. 服务监听地址或端口与调用地址不匹配，例如只监听容器网络却从宿主机访问。
5. 热重载/多进程下读取了不同 `.env` 或旧配置缓存，导致日志表现出多个 URL 混用。

## 下一步

- 核对配置来源
- 检查两个服务入口与启动方式
- 搜集运行日志证据

## 运行时证据

- `backend/.env` 中 `PLAN_SUB_API_URL=http://localhost:8001/plan`，但 Docker Compose 为 `backend` 容器注入了 `PLAN_SUB_API_URL=http://plan_sub_backend:8001/plan`。
- `plan_sub_api.py` 存在多地址回退：`plan_sub_backend`、`localhost`、`127.0.0.1` 会依次尝试。
- 当前 `8000/8001` 端口监听进程为 Docker Desktop / WSL 端口转发，不是宿主机直接跑的 Python 进程。
- `closedloop-plan_sub_backend-1` 与 `closedloop-backend-1` 容器当前均为 `Up` 状态，`/health` 可正常访问。
- `plan_sub_backend` 容器日志显示启动阶段已完成 `Application startup complete`，不是长期未启动。
- 从 `backend` 容器内部直连 `http://plan_sub_backend:8001/plan`，一次真实规划请求耗时约 `19.57s`，显著大于 `plan_trip` 当前 `3.0s` 超时配置。

## 当前判定

1. `localhost:8001` / `127.0.0.1:8001` 在 Docker 的 `backend` 容器内指向容器自身，因此连接拒绝是预期现象，不是子服务坏了。
2. 真正可用的地址是 `http://plan_sub_backend:8001/plan`。
3. 主要失败原因不是“连不上”，而是 `plan_trip` 的子图 HTTP 超时太短；在真实规划耗时约 20 秒时，`3.0s` 必然超时。
4. 多地址回退在 Docker 场景下会放大噪声，让日志同时出现 timeout 与 refused，掩盖真实根因。

## 本次修复

- 新增显式配置 `PLAN_SUB_NETWORK_MODE=local|docker`，默认 `local`。
- `plan_sub_api.py` 的候选地址生成改为按模式收敛：
  - `local`：显式配置 + `localhost` + `127.0.0.1`
  - `docker`：显式配置 + `plan_sub_backend`
- `search_tool.py` 复用同一套候选地址生成逻辑，保证 `/plan` 与 `/search` 规则一致。
- `plan_tool.py` 与 `adjust_tool.py` 在调用 `request_plan_sub_json()` 时显式传入网络模式。
- `backend/.env`、`backend/.env.example`、`docker-compose.yml`、`README.md` 已同步更新配置说明。

## 验证结果

- 新增并通过显式网络模式测试：
  - `test_plan_sub_api.py`
  - `test_search_tool.py`
- 回归通过：
  - `test_plan_tool.py`
- 本地执行命令：
  - `python -m unittest backend.src.tests.test_plan_sub_api backend.src.tests.test_search_tool backend.src.tests.test_plan_tool`
- 结果：全部通过。
