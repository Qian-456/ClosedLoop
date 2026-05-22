# Backend：流程与能力（Workflow）

## Purpose

这份文档回答：后端要实现哪些流程（状态机 + 关键能力），以及每一步的输入输出是什么。

---

## 当前实现（已落地）

### Pre-User-Card Pipeline（内部流水线）

后端当前 `build_graph()` 实际节点顺序为：

```text
extract_constraints
  → retrieve_candidates_node
  → filter_node
  → rerank_node
  → planner_node
```

说明：

- 当前版本已能在一次 `/invoke` 调用中返回：`constraints + candidates + itinerary`。
- `verify_node / adjust_node / execute_mock` 属于后续规划能力（见文末“规划稿”），目前不在图中。

### Core State（真实返回结构）

`POST /invoke` 的返回体为：

```json
{
  "status": "success",
  "state": {
    "user_input": "...",
    "constraints": {
      "group_type": "family",
      "budget": 350,
      "dietary_restrictions": ["辣"],
      "preferred_distance": "2km-5km",
      "time_period": "13:00-18:00",
      "duration_hours": 5.0,
      "activity_preferences": ["亲子", "少走路"],
      "adult_count": 2,
      "child_count": 1,
      "child_ages": [6]
    },
    "candidates": {
      "nearby_restaurants": [],
      "nearby_activities": [],
      "nearby_gifts": [],
      "ranked_breakfast_combos": [],
      "ranked_lunch_combos": [],
      "ranked_afternoon_tea_combos": [],
      "ranked_dinner_combos": [],
      "ranked_late_night_combos": [],
      "ranked_packages": [],
      "ranked_gifts": [],
      "processed_steps": ["retrieve_candidates_node", "filter_node", "rerank_node"]
    },
    "itinerary": {
      "status": "ok",
      "missing_types": [],
      "plans": [
        {
          "plan_id": "plan_1",
          "title": "...",
          "total_duration_minutes": 240,
          "total_cost": 199,
          "average_score": 0.8,
          "selected_item_ids": ["..."],
          "steps": [
            {
              "order_id": "1",
              "duration_minutes": 60,
              "note": "...",
              "item": {
                "id": "...",
                "name": "...",
                "type": "restaurant|activity|gift_shop|commute",
                "location": "某某路 123 号",
                "distance_km": 1.2,
                "cost": 50
              }
            }
          ]
        }
      ]
    }
  }
}
```

字段定义来源：

- `constraints`：`backend/src/closedloop/contracts/state.py::Constraints`
- `candidates`：`backend/src/closedloop/contracts/state.py::Candidates`
- `itinerary`：`backend/src/closedloop/contracts/itinerary.py::ItineraryPlan`

---

## 规划稿（未实现，后续迭代方向）

以下内容用于指导后续“确认 → 局部调整 → 模拟执行”的扩展；当前版本不要把它当成可用契约。

### 规划版 Pre-User-Card Pipeline（内部流水线）

```
intent_extract_node       # LLM structured output / 包含忌口限制归一化处理
  → retrieve_candidates_node # MockDB召回
  → filter_node              # 规则过滤（确定性剔除）
  → rerank_node              # 三维度单品打分 + 商业提权 + 按时段分流排序
  → planner_agent_node       # Planner Agent（DFS+剪枝+语义降级，显式处理通勤）
  → verify_node              # 代码校验（非 Agent，Eval阶段化校验硬性约束）
  → adjust_node              # Planner Agent（强化版：更多记忆/上下文，用于局部修正）
```

确认后才进入 Mock 执行：预约/排队/下单/发消息。

## 规划版 Core State（Plan State）

### Plan State（核心）

```json
{
  "constraints": {
    "group_type": "family",
    "adult_count": 2,
    "child_count": 1,
    "child_ages": [5],
    "dietary_restrictions": ["辣"],
    "preferred_distance": "2km-5km",
    "budget": 200,
    "time_period": "13:00-18:00",
    "duration_hours": 5
  },
  "timeline": [
    {
      "slot_id": "t1",
      "type": "activity",
      "candidates": ["a1","a2","a3"],
      "selected": "a1",
      "duration": {"min": 1, "max": 2},
      "location": {"lat": 0, "lng": 0}
    },
    {
      "slot_id": "t2",
      "type": "restaurant",
      "candidates": ["r1","r2","r3"],
      "selected": "r1",
      "duration": {"min": 1, "max": 1.5},
      "location": {"lat": 0, "lng": 0}
    }
  ],
  "catalog": {
    "activities": {
      "a1": {"id": "a1", "name": "Indoor Park", "tags": ["family"], "price_level": 2},
      "a2": {"id": "a2", "name": "Art Museum", "tags": ["friends"], "price_level": 2},
      "a3": {"id": "a3", "name": "Citywalk", "tags": ["friends"], "price_level": 1}
    },
    "restaurants": {
      "r1": {
        "id": "r1",
        "name": "Restaurant A",
        "cuisine": "light",
        "location": {"lat": 0, "lng": 0},
        "bundles": [
          {"bundle_id": "r1_b1", "title": "2-3 people set", "price": 169},
          {"bundle_id": "r1_b2", "title": "Family set", "price": 199},
          {"bundle_id": "r1_b3", "title": "Kids-friendly set", "price": 149}
        ]
      },
      "r2": {"id": "r2", "name": "Restaurant B", "bundles": []},
      "r3": {"id": "r3", "name": "Restaurant C", "bundles": []}
    }
  },
  "extras": [
    {"id": "e1", "type": "dessert", "optional": true}
  ],
  "total_duration": 5,
  "estimated_cost": 180,
  "status": "PLANNING"
}
```

### Constraints（约束）

```json
{
  "group_type": "family | friends",
  "adult_count": 2,
  "child_count": 1,
  "child_ages": [5],
  "dietary_restrictions": ["辣", "海鲜"],
  "preferred_distance": "<2km | 2km-5km | >5km",
  "budget": 200,
  "time_period": "13:00-18:00",
  "duration_hours": 5
}
```

### Interaction History（轻量）

```json
{
  "actions": [
    {"type": "replace", "target": "restaurant", "from": "r1", "to": "r2"}
  ]
}
```

## Tool Design（Mock API）

### Constraint Intake（先问清楚再规划）

- 输入句子可能不完整，Agent 需要补齐关键约束（人数、忌口、儿童年龄等）
- 可实现为：前端在生成 plan 前先走一轮 “questions → answers”，或由 Agent 一次性问完

### Candidate Search

```python
search_restaurants(constraints) -> List[Restaurant]
search_activities(constraints) -> List[Activity]
```

在 LangGraph 中，这部分对应 `retrieve_candidates_node`（并在其后由 `filter_rank_node` 做确定性的规则过滤、rerank 与商业调权）。

### Plan Validation（关键）

```python
validate_plan(plan, constraints) -> {
  "valid": bool,
  "violations": [...],
  "suggestions": [...]
}
```

### Feasibility Check

```python
check_feasibility(plan) -> {
  "time_ok": bool,
  "distance_ok": bool
}
```

### Execute（Mock）

```python
execute_plan(plan) -> {
  "results": [
    {"type": "activity", "status": "success"},
    {"type": "restaurant", "status": "failed"}
  ]
}
```

## Agent Responsibilities

### 边界

- 函数：校验 / 计算 / 数据
- Agent：选择 / 权衡 / 调整 / 解释（planner_agent_node + adjust_node）

### Agent Interface（最小集合）

```python
agent.plan(constraints, candidates) -> plan
agent.replan(plan, violations) -> new_plan
agent.replan_partial(plan, action) -> new_plan
agent.fallback(plan, failure_info) -> new_plan
agent.choose(candidates, context) -> selected
```

### Agent Input（必须带 state）

```python
agent_input = {
  "plan": plan_state,
  "constraints": constraints,
  "history": interaction_history
}
```

## Workflow（状态机）

```text
INIT
 ↓
INTENT_EXTRACT
 ↓
RETRIEVE + FILTER_RANK
 ↓
PLAN (PLANNER_AGENT)
 ↓
VERIFY
 ├─ ❌ → REPLAN
 └─ ✔
 ↓
WAIT_CONFIRM
 ↓
WAIT_ORDER_CONFIRM
 ↓
EXECUTE
 ├─ ❌ → FALLBACK → VALIDATE
 └─ ✔
 ↓
DONE
```

## Must Implement（后端能力与工程实现）

- **execute_plan**（闭环执行；可注入失败）
- **validate_plan → replan**（校验失败能重规划）
- **fallback / 语义降级**（基于语义邻近性的餐次降级，如正餐互转，夜宵转晚餐；以及某一步失败后能替换并继续）
- **replace**（局部替换：例如餐厅换一个）
- **chat**（自然语言修改：解析为结构化 action，再 replan_partial）
- **DFS+剪枝规划**（放弃全量笛卡尔积，采用 DFS 回溯与时耗/预算剪枝结合的方案，支持多 Pattern 降级）
- **Eval 阶段化持久化**（记录输入输出快照与评分，支持多版本基准对比与硬性时间段约束检查）
- **choose_bundle**（餐厅/团购套餐选择：每家 3 个推荐套餐，基于有机得分+商业调权）

## Error Handling（最小可用策略）

- Validate 阶段失败：优先 replan，保持用户约束不变
- Execute 阶段失败：先 fallback（同类替换），再 validate，必要时缩减 extras
- 任何时候保留可解释性：返回 violations/suggestions 与最终选择理由（用于 UI 展示）

## Checklist

- 任意输入都能得到一个可校验的 plan（即便是“降级 plan”）
- Validate 不通过时能自动修复并产出新 plan
- Execute 某一步失败时能自动替换并继续（至少覆盖 restaurant 满位）
- Replace/Chat 都能走同一条“结构化 action → partial replan”管线
