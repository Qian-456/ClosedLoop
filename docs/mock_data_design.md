# Mock DB 数据设计（摘要）

本项目使用本地 Mock DB 来模拟“本地生活”数据源，供 `retrieve/filter/rerank/planner` 工作流使用，保证无真实网络调用也能稳定演示完整闭环。

## 1. 数据文件

默认基线数据位于仓库根目录 `mock_db/`。同时支持将“可编辑字段库”外置到 `local_mock_db/catalog/`（默认会被 git 忽略），你只需要维护 catalog，然后运行生成脚本即可把改动同步到 `mock_db/`：

```text
mock_db/
  restaurants.json
  activities.json
  add_ons.json
  reservations.json

local_mock_db/
  catalog/ # 可编辑字段库（name/category/tags/套餐等）
```

## 1.1 顶层 POI 字段（统一）

三类 POI（restaurant/activity/gift_shop）的顶层字段统一为扁平结构（不再在 JSON 中存 `location`；活动不再使用 `operating_hours`）：

- `id`: 唯一 ID（如 restaurant_001 / activity_001 / gift_shop_001）
- `name`: 展示名称
- `category`: `restaurant | activity | gift_shop`
- `sub_category`: 品类细分（如 粤菜/火锅/桌游/密室/鲜花/蛋糕…）
- `district`: 虚构商圈（沿用 hub 名称，用于商圈过滤与聚类）
- `address`: 地址展示
- `latitude/longitude`: 直角坐标系 (x, y)，单位 km（用于距离计算与路径规划）
- `business_hours`: 营业时间（如 10:00-22:00）
- `indoor`: 是否室内（用于天气过滤）
- `review_keywords`: “可计算的体验语义信息”（用于推导推荐理由/过滤排序特征）
- `suitable_groups`: 适合人群标签（英文标准值，如 `solo/couple/family/friends/business/teen`）
- `experience_tag`: 从评论/标签中提取的中文体验标签列表（供 LLM 文案使用）
- `romantic_score_derived`: 派生浪漫度评分对象 `{score, confidence, source}`
- `photo_score_derived`: 派生拍照友好度评分对象 `{score, confidence, source}`
- `onsite_walking_level_estimated`: 派生现场步行强度评分对象 `{score, confidence, source}`
- `noise_level_estimated`: 派生噪音等级评分对象 `{score, confidence, source}`
- `age_range`: 仅 Activity 使用，值为 `["3-6", "7-10", "11-17", "adult"]` 的一个或多个
- `kid_menu_status`: 仅 Restaurant 使用，儿童餐/儿童菜单状态，值为 `explicit|possible|none|unknown`
- `stroller_friendly_status`: 仅 Restaurant 使用，推车友好度状态，值为 `yes|likely|no|unknown`
- `child_facility_tags`: 仅 Restaurant 使用，亲子设施标签列表（如 儿童座椅/亲子卫生间/商场内/少走路/室内）
- `child_friendly_score_derived`: 仅 Restaurant 使用，派生亲子友好度评分对象 `{score, confidence, source}`
- `gift_type`: 仅 Gift Shop 使用，枚举值 `flower|cake|toy|snack|blind_box|coffee`
- `delivery_to_restaurant`: 仅 Gift Shop 使用，是否支持“送到餐厅制造惊喜”（Mock 执行层使用）
- `surprise_score_derived`: 仅 Gift Shop 使用，派生惊喜度评分对象 `{score, confidence, source}`

子项结构仍保留：

- restaurant.combos[]
- activity.packages[]
- gift_shop.gifts[]

时间规划口径约定（不新增字段名）：

- `duration_minutes_default ≈ duration_mins`
- `duration_minutes_range ≈ [duration_mins - duration_std_dev, duration_mins + duration_std_dev]`

## 1.2 派生画像字段

为了让 LLM 后续更稳定地产出推荐理由、文案总结与解释信息，三类顶层 POI 额外维护一组“可解释的派生画像字段”。

- `suitable_groups`
  - 规则型英文标签，用于人群适配与 rerank
- `experience_tag`
  - 中文体验标签列表，用于 copywriting / 推荐理由生成
- `romantic_score_derived`
- `photo_score_derived`
- `onsite_walking_level_estimated`
- `noise_level_estimated`

上述 4 个评分字段统一结构为：

```json
{
  "score": 3.8,
  "confidence": 0.84,
  "source": {
    "sub_category": "景观餐厅",
    "matched_review_keywords": ["适合约会", "适合拍照"],
    "rule": "photo_from_sub_category_and_keywords"
  }
}
```

其中：

- `score`: 0-5
- `confidence`: 0-1
- `source`: 记录由 `sub_category + review_keywords` 哪条规则推导而来，便于调试与解释

## 2. 坐标系与距离

- 坐标系：直角坐标系 (x, y)，单位为 km。
- 原点 (0,0)：默认代表用户住宅区/家。
- 商圈分布：更符合真实城市的“商圈聚类”，而不是强行围绕原点均匀散布。
- 距离：使用欧几里得距离计算：

```text
D = sqrt((x2-x1)^2 + (y2-y1)^2)
```

## 2.1 数据规模与分布（固定配额）

POI 总量固定 88：

- Restaurant：32
- Activity：40
- Gift Shop：16

用于拟真覆盖的主要分布（通过 tags + review_keywords 体现）：

- Restaurant（32）：少辣/家庭基础(10)、情侣约会/拍照(7)、朋友聚会/热闹(7)、亲子儿童友好(4)、单人轻量用餐(4)
- Activity（40）：单人安静放松(6)、情侣约会/拍照(7)、亲子3-6岁(6)、亲子7-10岁(5)、青少年11-17岁(5)、朋友聚会/热闹(7)、通用兜底(4)
- Gift Shop（16）：情侣氛围类(5)、生日/朋友聚会类(4)、亲子儿童类(4)、通用文创类(3)

## 3. 通勤时间与成本（规划必须纳入）

规划时必须把“行程间通勤步骤”的时间与成本计入总时长与总花费（不能只算吃喝玩本身的 duration/cost）。

默认分段规则：

- 小于 2km：步行（5km/h，偏置 2min），成本 0 元
- 2–5km：出租车（30km/h，偏置 5min），成本 起步价 10 元 + 超出 3km 部分 2 元/km
- 大于 5km：自己开车（40km/h，偏置 10min），成本暂不计（0 元）

时间公式：

```text
time_mins = D / speed_km_per_min + bias_mins
```

## 4. 时间弹性与常识过滤

- 行程排布必须考虑 `duration_mins` 与 `duration_std_dev` 的弹性，避免把时间排得严丝合缝。
- 必须遵守 `suitable_time_slots`、`start_time/end_time` 等时段约束。
- 必须识别并剔除“常识不合理/噪音”数据（例如家庭聚会不应推荐单人套餐）。

## 5. 预约与余量（reservations.json）

`mock_db/reservations.json` 用于描述“需要预约/买票”的条目在不同时间段的可用余量（剩余名额/座位），为后续 execute_mock 或前端预约展示提供数据支撑。

### 5.1 对齐粒度

- 活动：按 `package_id`（对应 `activities.json` 内 `packages[]`）
- 餐饮：按 `combo_id`（对应 `restaurants.json` 内 `combos[]`）
- 仅当条目 `requires_booking=true` 时，才会在 `reservations.json` 中出现对应记录。

### 5.2 字段结构

每条记录结构：

- `target_type`: `"combo" | "package"`
- `target_id`: `combo_id` 或 `package_id`
- `time_slots`: 按时间段拆分的余量列表
  - `start_time`: `"HH:MM"`
  - `end_time`: `"HH:MM"`
  - `capacity_total`: 总名额/座位
  - `capacity_remaining`: 剩余名额/座位（0 表示满员）
  - `queue_required`: 是否需要排队
  - `wait_minutes`: 预计排队等待分钟数

### 5.3 语义约束

- 必须满足 `0 <= capacity_remaining <= capacity_total`
- 当 `capacity_remaining == 0` 时通常 `queue_required=true` 且 `wait_minutes` 更高，用于拟真“满员/排队”的常见体验
