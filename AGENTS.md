# AGENTS.md

## 项目描述（定位）

- ClosedLoop 是一个执行型本地生活 Agent：  
  用户一句话需求 → 生成可执行行程（4–6 小时）→ 用户确认 → 自动执行（Mock）→ 失败 fallback / replan。

- 本项目强调：
  - Execution（把事情做完）
  - Engineering（工程规范）
  - Workflow（流程可控）

---

## 技术栈（基线）

- Language: Python
- LLM Orchestration: LangChain + LangGraph
- LLM Providers: DeepSeek（Primary）→ Tongyi/Qwen（Fallback）
- Config: pydantic-settings
- Logging: loguru
- Tests: unittest
- Observability: LangSmith（当前）→ Prometheus（规划）

---

## 前端开发（优先基准）

- 前端目标是 Mobile-first 的 Web SPA「后端调用台 + 用户体验壳子」，不做重型完整 App。
- 开始任何前端实现前，必须先阅读：
  - `docs/frontend_mobile_spa_baseline.md`
  - `.trae/documents/frontend_mobile_spa_baseline.md`（历史草案/同步参考）
- 演示推荐使用 `/demo`（手机壳）+ `iframe` 加载 `/app`（真实页面）的结构，避免真实 UI 与演示外壳互相污染。
- 前端以当前后端真实接口为准：MVP 通过 `POST /invoke` 打通“输入→方案→调整”。

---

# 🔥 Infrastructure Contract（基础设施约束）

## Config（必须）

```python
from closedloop.core.config import get_config

config = get_config()
```

### ❌ 禁止

```python
os.getenv(...)
os.environ[...]
```

---

## Logger（必须）

```python
from closedloop.core.logger import LoggerManager, logger

LoggerManager.setup(config)

logger.info(f"phase=planning | input={user_input}")
```

### ❌ 禁止

```python
print(...)
```

---

## LLM（唯一入口）

```python
from closedloop.core.llm import build_agent

agent = build_agent() # 内置了 ChatDeepSeek(Primary) 与 ChatTongyi(Fallback)，并统一配置了 timeout=15.0
```

---

## ❗ 强制规则

- LLM 必须通过 build_agent
- 配置必须通过 get_config
- 日志必须使用 logger
- 禁止绕过 core 层

---

# 🔥 Workflow Contract（最重要）

## 当前实现（/invoke 真实图）

当前后端 `build_graph()` 实际包含节点：

```text
extract_constraints
→ retrieve_candidates_node
→ filter_node
→ rerank_node
→ planner_node
```

说明：

- 当前版本已能稳定跑通“输入 → 结构化约束 → 召回/过滤/排序 → 生成多套方案”。
- `verify_node / adjust_node / execute_mock` 属于后续增强能力（见下方规划），前端与文档需明确标注为“未实现”，避免契约幻觉。

## 规划（未实现，后续扩展）

在返回用户可见结果（用户卡片/行程/确认信息）前，后续版本计划严格遵循：

```text
intent_extract_node        # LLM structured output（包含忌口/限制归一化记录）
→ retrieve_candidates_node # MockDB召回
→ filter_node              # 规则过滤（硬性过滤剔除）
→ rerank_node              # 三维度单品打分 + 商业提权 + 时段分流（确定性）
→ planner_agent_node       # Planner Agent（基于 DFS + 剪枝 + 语义降级的路线规划）
→ verify_node              # 代码校验（非 Agent，按时段/耗时等硬约束评分校验）
→ adjust_node              # Planner Agent（强化版：更多记忆/上下文，用于局部修正）
→ execute_mock             # Mock预约/排队/下单/发消息
```

---

## ❗ 强制规则

- ❌ 禁止跳过 extract_constraints
- ❌ 禁止直接生成 itinerary
- ❌ 禁止单 prompt 完成所有逻辑
- ❌ 禁止绕过 Graph

---

## 状态要求

```python
from typing_extensions import TypedDict
from typing import NotRequired

class ClosedLoopState(TypedDict):
    user_input: str
    constraints: NotRequired[dict]
    candidates: NotRequired[dict]
    itinerary: NotRequired[dict]
    confirmation: NotRequired[dict]
    current_step: NotRequired[str]
```

- 状态必须显式存储
- ❌ 禁止只存在于 prompt

---

# 🔥 Code Generation Contract（AI必须遵守）

## 0️⃣ 注释语言（必须）

- 代码注释默认使用中文（包括 Docstring）。
- 仅在专有名词、缩写、协议名、库名等场景保留英文。

---

## 1️⃣ LLM 使用

```python
agent = build_agent()
```

---

## 2️⃣ Config

```python
config = get_config()
```

---

## 3️⃣ Logger与路径规范

```python
LoggerManager.setup(config)

logger.info(f"phase=xxx | input={input}")
```

- 路径要求：读写文件或目录（如日志、Mock DB、环境配置）必须基于 `os.path.abspath(os.path.dirname(__file__))` 构建绝对路径，禁止使用相对工作目录的路径。

---

## 4️⃣ Graph Node 模板（必须）

```python
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.core.llm import build_agent
from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.graph.prompts.extract import EXTRACT_CONSTRAINTS_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage

def extract_constraints(state: ClosedLoopState) -> ClosedLoopState:
    config = get_config()
    LoggerManager.setup(config)

    logger.info(f"phase=extract_constraints | input={state['user_input']}")

    agent = build_agent(response_format=Constraints)

    try:
        response = agent.invoke({
            "messages": [
                SystemMessage(content=EXTRACT_CONSTRAINTS_SYSTEM_PROMPT),
                HumanMessage(content=state['user_input'])
            ]
        })

        parsed_output = response
        if isinstance(response, dict) and "structured_response" in response:
            parsed_output = response["structured_response"]

        if hasattr(parsed_output, "model_dump"):
            state["constraints"] = parsed_output.model_dump()
        elif hasattr(parsed_output, "dict"):
            state["constraints"] = parsed_output.dict()
        elif isinstance(parsed_output, dict):
            state["constraints"] = parsed_output
        else:
            state["constraints"] = {}

        logger.info(f"phase=extract_constraints | output={state['constraints']}")
    except Exception as e:
        logger.error(f"phase=extract_constraints | error={e}")
        state["constraints"] = {}

    return state
```

---

## ❗ AI 自检

- [ ] 使用 build_agent
- [ ] 使用 get_config
- [ ] 使用 logger
- [ ] 使用 f-string 日志
- [ ] 没有 print
- [ ] 没有 os.getenv
- [ ] 遵循 Graph 流程

---

# 📂 项目结构（真实实现）

```text
docs/            ⭐ 项目相关文档
  mock_data_design.md  ⭐ Mock 数据的设计与生成机制说明

mock_db/         ⭐ 本地生活 Mock 数据库（由生成脚本按 Schema 生成）
  restaurants.json
  activities.json
  add_ons.json
  reservations.json

backend/
  .env           ⭐ 本地环境变量配置（不提交到Git）
  .env.example   ⭐ 环境变量配置模板
  src/
    logs/          ⭐ 运行时日志输出目录
    tests/         ⭐ 测试代码目录（包含单元测试等）

    closedloop/
      core/          ⭐ 基础设施（必须使用）
      contracts/
      graph/
      tools/
      utils/
```

---

## ❗ 强制规则

- Graph 是唯一执行入口
- ❌ 禁止绕过 graph 调用 LLM
- ❌ tools 不得依赖 graph

---

# 🔍 可观测性

## Logs

必须包含：

- phase
- input
- result
- error

---

## Tracing

- 每个节点必须可追踪
- fallback 必须记录

---

# 🧪 测试约束

必须包含：

- happy path
- clarify path
- contract 校验

---

# 🗺️ 数据与空间约束 (Mock DB)

本项目使用高度拟真的本地生活 Mock 数据（详见 `docs/mock_data_design.md`），AI 在处理检索、过滤和规划时必须遵守以下物理与业务约束：

- POI 顶层字段为扁平结构：`id/name/category/sub_category/district/address/latitude/longitude/business_hours/indoor/review_keywords`（子项 combos/packages/gifts 保留）。
- 顶层 POI 画像字段为正式契约：`suitable_groups`、`experience_tag`、`romantic_score_derived`、`photo_score_derived`、`onsite_walking_level_estimated`、`noise_level_estimated`；其中 Activity 还必须带 `age_range`。
- Restaurant 亲子字段为正式契约：`kid_menu_status`、`stroller_friendly_status`、`child_facility_tags`、`child_friendly_score_derived`。
- Gift Shop 特殊字段为正式契约：`gift_type`、`delivery_to_restaurant`、`surprise_score_derived`。
- POI 固定配额总量 88：Restaurant 32、Activity 40、Gift Shop 16。
- 坐标系：直角坐标系 (x, y)，单位为 km。原点 (0,0) 默认代表用户住宅区。
- 商圈聚类：店铺分布呈现“核心商圈密集，向外围稀疏”的高斯聚类特征。
- 距离与时间：必须基于欧几里得距离 D = sqrt(Δx² + Δy²) 结合交通工具配速（及固定损耗）计算通勤时间。
- 时间弹性约束：排布行程时必须考虑 `duration_mins` 和 `duration_std_dev`（浮动标准差），不能将行程排得严丝合缝。
- 时段与常识过滤：必须识别并剔除“噪音”数据，并严格遵守 `suitable_time_slots` 和 `start_time` 约束。

---

# 🏁 比赛约束

- 必须实现：
  - 规划 → 确认 → 执行
- 所有执行为 Mock
- 禁止真实网络调用

---

# 🚨 最重要规则（最高优先级）

AI 写代码必须：

1. 使用 build_agent
2. 使用 get_config
3. 使用 logger
4. 使用 f-string 日志
5. 不使用 print
6. 不使用 os.getenv
7. 严格遵循 Graph workflow
8. 优先参考 core/ + closedloop/
