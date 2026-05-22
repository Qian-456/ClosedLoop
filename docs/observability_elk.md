# ELK 本地可观测性（filter_node 过滤原因）

## 1. 开启结构化日志

在 `backend/.env` 中设置：

```
LOG_ELK_ENABLED=true
LOG_ELK_LEVEL=DEBUG
LOG_ELK_JSON_PATH=logs/elk.jsonl
FILTER_LOG_DETAILED_DEBUG=true
```

说明：
- `elk.jsonl` 为 loguru `serialize=true` 输出，每行一条 JSON 记录
- `event=filter_drop` 为逐条过滤明细（DEBUG）
- `event=filter_counts` 为过滤前/后/差值（INFO）

## 2. 启动后端 + ELK

在仓库根目录执行：

```
docker compose -f docker-compose.yml -f docker/elk/docker-compose.elk.yml up --build
```

- Elasticsearch：http://localhost:9200
- Kibana：http://localhost:5601

## 3. Kibana 里如何看比例

### 3.1 看“过滤原因占比”

在 Discover 里先确认能搜到：
- `event:"filter_drop"`
- `phase:"filter_node"`

然后在可视化里做饼图/柱状图：
- 维度：`reason_code`
- 指标：`Count`
- 可选分组：`category` / `subject`

### 3.2 看“整体过滤掉多少 vs 保留多少”

用 `event:"filter_counts"`：
- `dropped_count` 表示过滤掉的数量
- `after_count` 表示保留的数量

你可以用 Lens 的公式做一个二选一饼图（同一时间窗口内）：
- 过滤掉：`sum(dropped_count)`
- 保留：`sum(after_count)`

## 4. 快速定位“命中了什么词/字段/元素”

当 `reason_code="family_forbidden_terms"` 等需要细粒度命中信息时，使用这些字段检索：
- `reason_detail.matched_term`
- `reason_detail.matched_field`
- `reason_detail.matched_element_type`
- `reason_detail.matched_element_id`
