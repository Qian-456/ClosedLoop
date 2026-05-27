# Plan Sub 服务网络模式显式化设计

## Summary

- 目标：在不修改 `plan_trip` 当前 `3s` 超时约束的前提下，让 `PLAN_SUB_API_URL` 在宿主机本地运行与 Docker 运行两种场景下的行为更明确、日志更可判读。
- 方案：新增显式配置 `PLAN_SUB_NETWORK_MODE=local|docker`，默认 `local`；代码严格按模式生成候选地址，不再在 Docker 场景下回退到 `localhost/127.0.0.1`。

## Current State

### 1. 地址回退策略没有显式环境语义

- `backend/src/closedloop/graph/tools/plan_sub_api.py`
  - 当前始终混合尝试：
    - 显式配置地址
    - `http://plan_sub_backend:8001`
    - `http://localhost:8001`
    - `http://127.0.0.1:8001`
- `backend/src/closedloop/graph/tools/search_tool.py`
  - 搜索链路也有相同风格的候选地址回退
- 问题：
  - Docker 内 `localhost/127.0.0.1` 指向当前容器自身，不是 `plan_sub_backend`
  - 宿主机本地运行时 `plan_sub_backend` 又通常不可解析
  - 同一轮请求日志会出现多种失败类型，掩盖真实问题

### 2. 配置来源虽正确，但行为仍不够明确

- `docker-compose.yml`
  - 已为 `backend` 服务注入 `PLAN_SUB_API_URL=http://plan_sub_backend:8001/plan`
- `backend/.env.example`
  - 默认示例仍以本地 `localhost` 为主
- 问题：
  - 即便显式配置已经正确，代码依然会继续尝试不适用于当前环境的地址
  - 用户看到 `Connection refused` 时，容易误判为服务未启动，而不是“错误回退地址必然失败”

### 3. 当前约束是不调整超时

- 用户明确要求保留比赛约束，不修改 `plan_trip` 当前 `3s` 超时。
- 因此本次改动只处理“环境配置明确化”和“地址候选收敛”，不处理请求耗时本身。

## Decisions

- 新增显式环境变量 `PLAN_SUB_NETWORK_MODE`。
- 允许值固定为：
  - `local`
  - `docker`
- 默认值为 `local`，兼容本地 `python main.py` / `cli_main.py` 的开发方式。
- Docker 运行时由 `docker-compose.yml` 显式覆盖为 `docker`。
- 候选地址生成严格遵循模式，不再混用两套网络语义。
- `/plan` 与 `/search` 两条链路必须使用一致的候选规则。

## Proposed Changes

### 1. 配置层新增网络模式字段

- 文件：`backend/src/closedloop/core/config.py`
- 文件：`backend/.env.example`
- 文件：`backend/.env`

#### What

- 在 `AppConfig` 中新增 `PLAN_SUB_NETWORK_MODE` 字段。
- 类型使用字面量枚举：`"local" | "docker"`。
- 默认值设为 `local`。

#### Why

- 让“运行环境语义”成为正式配置，而不是隐式推断。
- 避免把地址本身当作环境识别信号，导致行为模糊。

#### How

- `config.py` 中新增字段定义。
- `.env.example` 中加入注释：
  - 本地直跑主后端时使用 `local`
  - Docker Compose 内部服务调用时使用 `docker`
- 当前本地 `.env` 也同步新增该字段，默认写成 `local`。

### 2. 规划子服务请求按模式生成候选地址

- 文件：`backend/src/closedloop/graph/tools/plan_sub_api.py`

#### What

- 调整 `build_plan_sub_candidate_urls(...)`，增加网络模式参数。
- `local` 模式下仅允许本地语义地址：
  - 显式配置地址
  - `http://localhost:8001`
  - `http://127.0.0.1:8001`
- `docker` 模式下仅允许 Docker 语义地址：
  - 显式配置地址
  - `http://plan_sub_backend:8001`

#### Why

- Docker 中再尝试 `localhost/127.0.0.1` 只会制造误导性日志。
- 本地环境再尝试 `plan_sub_backend` 通常也没有意义。

#### How

- 保留显式配置地址为第一优先级。
- 根据 `PLAN_SUB_NETWORK_MODE` 追加对应环境的默认候选。
- 候选去重，避免重复请求同一地址。
- 日志中保留当前尝试地址，必要时可额外输出 `network_mode`。

### 3. 搜索链路使用同一套模式规则

- 文件：`backend/src/closedloop/graph/tools/search_tool.py`

#### What

- 搜索地址候选逻辑改为复用与 `plan_sub_api.py` 同样的网络模式语义。

#### Why

- `/plan` 和 `/search` 如果使用不同环境判断规则，会导致排查非常割裂。
- 用户看到 `/plan` 是 Docker 语义、`/search` 又回到本地语义，会误以为存在多个独立问题。

#### How

- 从 `PLAN_SUB_API_URL` 统一推导基础地址。
- 使用同样的 `PLAN_SUB_NETWORK_MODE` 控制候选集合。
- 将 `/plan` 转换为 `/search` 时保持规则一致。

### 4. Docker Compose 明确覆盖网络模式

- 文件：`docker-compose.yml`

#### What

- 在 `backend` 服务环境变量中显式加入：
  - `PLAN_SUB_NETWORK_MODE=docker`

#### Why

- 让容器运行方式从启动入口层面就自解释。
- 避免容器内部沿用 `.env` 中的本地默认值。

#### How

- `backend` 服务通过 compose 环境变量覆盖 `.env` 默认值。
- `plan_sub_backend` 本身无需依赖该字段，但允许同步设置以保持环境一致性。

### 5. 文档与模板说明显式分场景

- 文件：`README.md`
- 文件：`backend/.env.example`

#### What

- 将配置说明拆成两类：
  - 宿主机运行主后端
  - Docker Compose 运行主后端

#### Why

- 让用户在看文档时先选运行方式，再抄对应配置。
- 降低“拿着本地地址去跑容器”“拿着容器服务名去跑本地”的概率。

#### How

- 在 README 的运行章节中补充一个小型配置矩阵。
- 明确说明：
  - `local` 对应 `localhost/127.0.0.1`
  - `docker` 对应 `plan_sub_backend`

## Testing Plan

### 1. `plan_sub_api.py`

- 测试 `local` 模式候选地址：
  - 包含显式配置地址
  - 包含 `localhost`
  - 包含 `127.0.0.1`
  - 不包含 `plan_sub_backend`
- 测试 `docker` 模式候选地址：
  - 包含显式配置地址
  - 包含 `plan_sub_backend`
  - 不包含 `localhost`
  - 不包含 `127.0.0.1`
- 测试去重逻辑：
  - 当显式配置本身就是默认候选之一时，不应重复

### 2. `search_tool.py`

- 测试 `/search` 候选地址在 `local` / `docker` 两种模式下与 `/plan` 规则一致。
- 测试显式配置为 `/plan` 路径时能正确转换为 `/search`。

### 3. 回归

- 现有 `plan_sub_api` 和 `search_tool` 相关测试应继续通过。
- `.env.example` 与 Docker Compose 的示例语义保持一致。

## Non-Goals

- 不修改 `plan_trip` 当前 `3s` 超时。
- 不调整 `plan_sub_backend` 的规划执行耗时。
- 不引入 `auto` 模式。
- 不重构整体微服务拓扑。

## Acceptance Criteria

- 当 `PLAN_SUB_NETWORK_MODE=local` 时，请求候选地址只体现本地语义，不再尝试 `plan_sub_backend`。
- 当 `PLAN_SUB_NETWORK_MODE=docker` 时，请求候选地址只体现 Docker 语义，不再尝试 `localhost/127.0.0.1`。
- `/plan` 与 `/search` 两条链路使用一致的模式规则。
- README、`.env.example`、`.env`、`docker-compose.yml` 中的配置说明彼此一致。
