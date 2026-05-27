# 搜索链路容错与索引退化保留设计

## Summary

- 目标：同时修复搜索链路中两个高频问题：
  - `PLAN_SUB_API_URL` 在宿主机 / Docker 两种运行方式下容易失配，导致 `/search` 请求报 `Name or service not known`
  - `search_indexer` 在 embedding 超时后直接跳过条目，导致索引内容不完整，进一步造成“搜不到”或“搜不全”
- 方案：采用“自动容错”策略，在搜索工具层增加多地址回退，在索引层保留无 dense embedding 的文本/BM25 可搜能力。

## Current State

### 1. 搜索服务地址存在环境耦合

- `backend/src/closedloop/core/config.py`
  - 默认 `PLAN_SUB_API_URL` 为 `http://plan_sub_backend:8001/plan`
  - 这只适合 Docker 内部网络，不适合宿主机直接运行后端
- `backend/.env.example`
  - 示例值是 `http://localhost:8001/plan`
  - 与代码默认值是两套语义，容易让实际运行环境混乱
- `backend/src/closedloop/graph/tools/search_tool.py`
  - 当前只尝试单个 `PLAN_SUB_API_URL.replace("/plan", "/search")`
  - 一旦该地址 DNS/连接失败，就直接进入 fallback

### 2. 索引构建在 embedding 超时时会丢条目

- `backend/src/closedloop/graph/plan_subgraph/search_indexer.py`
  - 批次 embedding 超时后会补零向量
  - 零向量条目在后续 `skip_failed_embedding` 逻辑中被直接跳过
  - 结果是：很多 item 根本不进入集合
- 这会导致：
  - hybrid search 的 dense 部分缺失
  - 就算 sparse/BM25 理论可用，实际条目也可能根本没有入库

### 3. 本地 fallback 的稳定性依赖进程内缓存

- `search_tool.py` 的 fallback 使用 `SearchIndexer.get_instance().category_docs`
- 该缓存是进程内内存，不保证与 `plan_sub_backend` 所在进程共享
- 当主后端与 plan_sub 分开运行时，fallback 可能拿不到数据，进一步放大“搜不到”现象

## Decisions

- 保留 `PLAN_SUB_API_URL` 作为首选显式配置，但不再只信任单地址。
- 搜索请求失败时，按候选地址顺序自动尝试，优先修通 `/search` 主路径。
- embedding 超时不再导致条目被整条跳过；至少保留文本可搜能力。
- 查询 embedding 超时时，不阻塞稀疏检索；允许走 sparse-only / BM25 路径。
- 进程内 `category_docs` fallback 继续保留，但降级为最后兜底，而不是主要成功路径。

## Proposed Changes

### 1. 搜索地址自动回退

- 文件：`backend/src/closedloop/graph/tools/search_tool.py`

#### What

- 增加一个内部地址解析/候选生成逻辑，例如：
  - 显式配置地址（如果存在）
  - `http://plan_sub_backend:8001/search`
  - `http://localhost:8001/search`
  - `http://127.0.0.1:8001/search`
- 顺序尝试，命中即返回

#### Why

- 避免把“Docker 服务名”错误地拿到宿主机环境里使用
- 避免把“localhost”错误地拿到容器网络里使用

#### How

- 从 `PLAN_SUB_API_URL` 统一转换出 `/search` 路径
- 去重候选 URL，避免重复请求
- 按顺序用 `httpx.Client` 尝试
- 日志细分为：
  - `search_api_attempt`
  - `search_api_dns_failed`
  - `search_api_connect_failed`
  - `search_api_http_failed`
  - `search_api_success`
- 所有候选都失败后，再进入本地 fallback

### 2. 索引退化保留：embedding 失败也保留条目

- 文件：`backend/src/closedloop/graph/plan_subgraph/search_indexer.py`

#### What

- 调整 `build_index()`，使 embedding 超时/失败的条目仍然保留文本索引数据
- 不再因为 dense vector 缺失而直接 `skip_failed_embedding`

#### Why

- 当前最大的可用性问题不是“语义检索质量略差”，而是“条目完全搜不到”
- 先保可搜，再保语义质量

#### How

- 建集合时继续保留 `text`、`sparse_vector` 与 BM25 function
- 对 dense embedding 失败的条目，不再跳过，而是插入一个安全兜底 dense 向量
  - 推荐使用极小非零向量而不是全零，避免 COSINE/底层实现异常
- 将日志从 `skip_failed_embedding` 调整为类似：
  - `dense_embedding_fallback_used`
- 这样条目仍然能参与 sparse/BM25 检索，dense 权重自然退化

### 3. 查询阶段允许 sparse-only 退化

- 文件：`backend/src/closedloop/graph/plan_subgraph/search_indexer.py`

#### What

- 当 query embedding 超时或失败时，仍然返回基于 sparse/BM25 的结果，而不是让 dense 问题拖垮整个 hybrid 搜索

#### Why

- 现在 `_safe_embed()` 已经会返回极小值向量，但日志语义和行为仍然偏“勉强 hybrid”
- 需要把这种情况明确设计成可接受的退化路径

#### How

- 保留 `_safe_embed()` 的超时兜底
- 明确在日志中标识：
  - `query_embedding_timeout`
  - `query_sparse_fallback_active`
- 若底层 hybrid_search 对 dummy 向量表现不稳定，可改为显式走 sparse-only 请求路径

### 4. fallback 职责重新定位

- 文件：`backend/src/closedloop/graph/tools/search_tool.py`

#### What

- 保留当前基于 `category_docs` 的关键词 fallback，但视为“最后一道兜底”

#### Why

- 该逻辑依赖进程内缓存，跨服务时不稳定
- 不适合作为主路径成功策略

#### How

- 只有在所有远程 `/search` 候选地址都失败后才启用
- 若 fallback 命中为空，在错误信息里明确区分：
  - “远程搜索不可达”
  - “本地缓存为空或未命中”

### 5. 配置与文档对齐

- 文件：`backend/.env.example`
- 文件：`docs/20_frontend_integration.md`
- 文件：`README.md`（如需要）

#### What

- 明确说明：
  - 宿主机直接运行后端时，用 `localhost/127.0.0.1`
  - Docker 内部服务间通信时，用 `plan_sub_backend`

#### Why

- 现在默认值、示例值、实际运行方式容易混淆

#### How

- 在 `.env.example` 中补清晰注释
- 文档中明确“本机运行”和“Docker 运行”两种配置示例

## Testing Plan

### 1. `search_tool.py`

- 测试候选地址回退：
  - 第一地址 DNS 失败，第二地址成功
  - 所有地址都失败时进入 fallback
- 测试日志/行为：
  - 成功时不进入 fallback
  - 全失败时才进入 fallback

### 2. `search_indexer.py`

- 测试 embedding 批次超时后，条目仍会被保留入索引
- 测试 query embedding 超时后，搜索仍返回结果
- 测试不再出现“有效条目全被 skip”的行为

### 3. 回归

- 现有 search / plan 相关测试不应被破坏
- Docker 和本地两种模式的文档示例均能对应到正确地址语义

## Non-Goals

- 不在本次改动中重构整个 plan_sub 服务架构
- 不移除现有 Milvus + hybrid search 设计
- 不引入新的外部基础设施

## Acceptance Criteria

- 在宿主机运行后端时，即使 `PLAN_SUB_API_URL` 配成 Docker 服务名，搜索仍能自动尝试本机候选地址
- 在 Docker 内运行后端时，即使本机地址不可用，搜索仍能回退到容器内服务地址
- embedding 超时不再导致大量条目直接丢失
- 搜索链路在最差情况下仍能返回可接受的文本/BM25 结果，而不是大量“搜不到”
