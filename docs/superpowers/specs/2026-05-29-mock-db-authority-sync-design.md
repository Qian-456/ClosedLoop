# Mock DB 单一权威源设计

## Summary

- 目标：将 `backend/src/mock_db` 设为唯一静态权威数据源，移除 `mock_data/base` 的业务意义，`mock_data/runtime` 继续作为执行态副本。
- 方案：调整配置默认主源到 `backend/src/mock_db`，删除 `mock_data/base` 兼容层相关设计与目录依赖，让读取与 seed 都直接围绕权威源工作。

## Current State

### 1. 项目内存在两套静态 Mock JSON 目录

- `backend/src/mock_db`
  - 当前开发过程中用户经常直接打开并修改这里的 JSON 文件。
- `mock_data/base`
  - 当前配置层默认将其视为 `MOCK_DB_REPO_DIR`，但用户并不以它为主要维护入口。
- 问题：
  - 两套目录同时存在，但没有统一的“谁是权威源”约定。
  - 用户修改 `backend/src/mock_db` 后，业务读取结果未必立即反映这些改动。

### 2. 当前读取主链路默认指向 `mock_data/base`

- `backend/src/closedloop/core/config.py`
  - `MOCK_DB_REPO_DIR` 默认值是 `mock_data/base`
- `backend/src/closedloop/utils/mock_db.py`
  - `load_mock_data()` 读取 `MOCK_DB_REPO_DIR`
- `backend/src/closedloop/graph/plan_subgraph/retrieve.py`
  - 规划召回通过 `load_mock_data()` 读取餐厅、活动、礼物数据
- 问题：
  - 虽然用户主要编辑的是 `backend/src/mock_db`，但规划读取却默认来自另一套目录。
  - 这会造成“我改了数据，运行结果却没变”的错觉。
  - `mock_data/base` 还会让目录职责变得多余且难以理解。

### 3. runtime 设计本身是合理的，不应在本次改动中推翻

- `backend/src/closedloop/execution/mock_executor.py`
  - 执行链路通过 `_resolve_repo_dir()` 选择写入目录
  - `runtime` 目录用于执行期库存/预约扣减
  - 当 `runtime` 缺少对应 JSON 时，会从 `MOCK_DB_REPO_DIR` seed
- 结论：
- `runtime` 本质上是“可变副本”，不是权威静态源。
- 本次不改变 `runtime` 的职责，只改变它的 seed 来源语义。

## Decisions

- 唯一权威静态数据源固定为 `backend/src/mock_db`。
- `mock_data/base` 退出业务链路，并在本次改动中直接删除。
- `mock_data/runtime` 保持执行态副本职责不变。
- 不再引入 `base` 同步机制，也不保留兼容读取。
- 严禁任何副本目录反向覆盖权威源。

## Proposed Changes

### 1. 配置层正式切换权威源目录

- 文件：`backend/src/closedloop/core/config.py`
- 文件：`backend/.env.example`
- 文件：`backend/.env`

#### What

- 将 `DataSettings.MOCK_DB_REPO_DIR` 默认值从 `mock_data/base` 改为 `backend/src/mock_db`。
- 保持 `MOCK_DB_RW_DIR` 默认值为 `mock_data/runtime`。
- 在 `.env.example` 和 `.env` 中补充说明：
  - `MOCK_DB_REPO_DIR` 代表唯一权威静态数据源
  - `MOCK_DB_RW_DIR` 代表执行态副本目录

#### Why

- 让“代码实际读取哪里”与“用户主要维护哪里”完全一致。
- 避免开发时继续出现两套静态目录语义不清的问题。

#### How

- `config.py` 中直接修改默认值。
- `.env.example` 与 `.env` 明确补齐 `MOCK_DB_REPO_DIR` 和 `MOCK_DB_RW_DIR`。
- 如果用户未显式配置环境变量，系统也默认读取 `backend/src/mock_db`。

### 2. 生成脚本继续输出到权威源目录

- 文件：`backend/src/scripts/mock_data/generator.py`

#### What

- 保持生成脚本写入 `config.data.MOCK_DB_REPO_DIR`。
- 因为主源目录已切换，该脚本默认会直接生成到 `backend/src/mock_db`。

#### Why

- 这满足“用户改的就是系统主读的”。
- 同时避免生成脚本继续把新数据写到旧 `base` 目录，导致目录角色再次反转。

#### How

- 不需要新增复杂逻辑，只需保证配置默认值切换后测试仍然成立。
- 本次不再引入任何 `base` 同步逻辑。

### 3. runtime seed 自动继承新的权威源

- 文件：`backend/src/closedloop/execution/mock_executor.py`

#### What

- 不修改 `runtime` 的职责。
- 保持 `runtime` 缺文件时从 `MOCK_DB_REPO_DIR` seed。

#### Why

- 一旦 `MOCK_DB_REPO_DIR` 指向 `backend/src/mock_db`，执行器自然会从新的权威源复制。
- 这样可以最小代价完成行为对齐，不破坏现有执行链路。

#### How

- 原则上不需要大改执行器逻辑。
- 只需要通过测试确认：
  - `runtime` 仍然按原行为工作
  - seed 来源已经从语义上切到 `backend/src/mock_db`

## Data Flow

### 静态读取链路

1. 用户维护 `backend/src/mock_db/*.json`
2. 规划/检索链路通过 `load_mock_data()` 读取 `MOCK_DB_REPO_DIR`
3. 因 `MOCK_DB_REPO_DIR` 已改为 `backend/src/mock_db`，规划直接消费权威源

### 执行写入链路

1. 服务启动
2. 执行器运行时解析 `MOCK_DB_REPO_DIR` 与 `MOCK_DB_RW_DIR`
3. `runtime` 不存在文件时，从 `backend/src/mock_db` seed
4. 执行期库存和预约变化只写入 `runtime`
5. 权威静态源不因执行态修改而被污染

## Error Handling

### 1. 权威源文件缺失

- 如果四个核心 JSON 中任一缺失：
  - 记录错误日志
  - 默认阻止服务启动
- 原因：
  - 权威源缺失是配置或仓库状态错误，应该尽早暴露，而不是带病运行。

### 2. 旧 `base` 目录残留

- 若仓库中仍有 `mock_data/base` 目录残留：
  - 本次改动中应删除目录或至少删除其中 JSON 文件
  - 文档中不再将其列为有效数据入口
- 原因：
  - 避免继续制造“还有第二静态源”的误解。

## Testing Plan

### 1. 配置测试

- 新增测试：`MOCK_DB_REPO_DIR` 默认值指向 `backend/src/mock_db`
- 新增测试：`MOCK_DB_RW_DIR` 默认值仍指向 `mock_data/runtime`

### 2. 执行器回归测试

- `runtime` 缺失文件时，仍能正确 seed
- seed 来源应视为 `backend/src/mock_db`
- `runtime` 变化不影响权威源

### 3. 生成脚本回归测试

- 生成脚本输出目录应为新的 `MOCK_DB_REPO_DIR`
- 已有 mock 数据生成逻辑、schema 校验逻辑保持通过

### 4. 目录清理回归测试

- 若仓库测试或脚本仍硬编码 `mock_data/base`，应在本次改动中修正
- 文档、注释、契约说明中不再把 `mock_data/base` 描述为静态数据源

## Non-Goals

- 不引入保存即同步或文件监听实时同步。
- 不保留 `mock_data/base` 作为兼容目录。
- 不让执行态 `runtime` 反向回写静态权威源。
- 不重构规划、过滤、排序等业务逻辑。

## Acceptance Criteria

- 默认情况下，业务读取的静态 Mock 数据源为 `backend/src/mock_db`
- `mock_data/base` 不再出现在业务代码主链路中，并从仓库中删除
- `runtime` 继续作为执行态副本，并从新的权威源 seed
- 当用户只修改 `backend/src/mock_db` 时，规划与执行 seed 都直接体现这些改动
