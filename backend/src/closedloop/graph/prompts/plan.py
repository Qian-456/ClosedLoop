PLAN_ITINERARY_SYSTEM_PROMPT = """
你是一个本地生活行程规划助手。你的任务是：根据输入的 constraints 与 candidates，生成 1~3 套不同“时间组合”的行程方案。

强约束：
1) 只能从 candidates 中选择条目，禁止编造不存在的 id。
2) 每一套方案都必须至少包含：
   - 1 个 activity
   - 1 个 restaurant
   - 1 个 gift_shop
3) 每一步必须提供：
   - order_id（从 1 开始的整数，顺序递增）
   - item（包含 id/name/type/location/distance_km）
   - duration_minutes（正整数）
   - note（简短说明）
4) selected_item_ids 必须与 steps 的顺序一致。
5) total_duration_minutes 必须等于该方案 steps 的 duration_minutes 之和。
6) 对于 gift_shop：
   - candidates 里的 lead_time_minutes 表示至少需要提前多少分钟下单/预约
   - duration_minutes 表示“交付/收礼/整理”的预留时间，优先使用 candidates 的 handoff_minutes（默认 15 分钟），不要当作逛店时长

输出要求：
- 使用结构化输出，只输出符合 schema 的字段。
- 必须让输出能被严格解析为 JSON：只输出一个 JSON 对象，不要输出解释文字，不要使用 Markdown 代码块（不要输出 ```）。
- 顶层字段必须为：plans / status / missing_types。
- status 只能取以下值之一：ok / insufficient_candidates / fallback_deterministic（禁止输出 success 等其它值）。
- plans 中每个方案必须包含字段：
  - plan_id：字符串，例如 "plan_1"（禁止输出数字 1/2/3）
  - title：字符串，必填
  - steps：步骤列表
  - selected_item_ids：字符串列表，且与 steps 顺序一致
  - total_duration_minutes：整数，且等于 steps[*].duration_minutes 之和
- 生成 1~3 套方案（plans），它们在总时长/步数上应当有所区别（例如 240 分钟 / 360 分钟；或 3 步 / 4-5 步）。
- 如果任何一种必需类型的 candidates 为空，输出：
  - status="insufficient_candidates"
  - missing_types 列出缺失类型
  - plans 为空列表
""".strip()


def _as_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except Exception:
            return None
    return None


def build_plan_itinerary_system_prompt(constraints: dict | None) -> str:
    if not isinstance(constraints, dict) or not constraints:
        return PLAN_ITINERARY_SYSTEM_PROMPT

    budget = _as_number(constraints.get("budget"))
    duration_hours = _as_number(constraints.get("duration_hours"))
    time_period = constraints.get("time_period")
    preferred_distance = constraints.get("preferred_distance")
    dietary = constraints.get("dietary_restrictions")
    group_type = constraints.get("group_type")
    adult_count = constraints.get("adult_count")
    child_count = constraints.get("child_count")
    child_ages = constraints.get("child_ages")
    activity_prefs = constraints.get("activity_preferences")

    lines: list[str] = ["【约束卡片（来自 constraints）】"]
    lines.append("- 优先级：预算不超 > 时间尽量用满 > 距离偏好 > 其他偏好")

    if isinstance(time_period, str) and time_period:
        lines.append(f"- 时间窗：{time_period}")
    if duration_hours is not None and duration_hours > 0:
        target_minutes = int(round(duration_hours * 60))
        preferred_low = int(round(target_minutes * 0.9))
        lines.append(f"- 目标总时长：{target_minutes} 分钟；优先区间：{preferred_low}-{target_minutes} 分钟")

    if budget is not None and budget > 0:
        budget_limit = int(round(budget))
        budget_low = int(round(budget_limit * 0.8))
        lines.append(f"- 预算上限：{budget_limit}；优先区间：{budget_low}-{budget_limit}（不得超过）")

    if isinstance(preferred_distance, str) and preferred_distance:
        lines.append(f"- 距离偏好：{preferred_distance}")

    if isinstance(dietary, list) and dietary:
        dietary_text = "、".join([str(x) for x in dietary if isinstance(x, (str, int, float)) and str(x)])
        if dietary_text:
            lines.append(f"- 忌口/限制：{dietary_text}")

    person_parts: list[str] = []
    if isinstance(group_type, str) and group_type:
        person_parts.append(f"人群={group_type}")
    
    count_str = ""
    if isinstance(adult_count, int):
        count_str += f"{adult_count}大"
    if isinstance(child_count, int) and child_count > 0:
        count_str += f"{child_count}小"
    if isinstance(child_ages, list) and child_ages:
        ages_str = "、".join(str(age) for age in child_ages)
        count_str += f"({ages_str}岁)"
    
    if count_str:
        person_parts.append(f"人数={count_str}")

    if person_parts:
        lines.append("- " + "；".join(person_parts))

    if isinstance(activity_prefs, list) and activity_prefs:
        prefs_text = "、".join([str(x) for x in activity_prefs if isinstance(x, (str, int, float)) and str(x)])
        if prefs_text:
            lines.append(f"- 活动偏好：{prefs_text}")

    lines.append("- 优化目标：在不违反上述约束的前提下，尽量让 total_duration_minutes 接近目标总时长，并在不超预算前提下尽量靠近预算上限。")
    lines.append(
        "- 标题要求：title 必须与该方案 total_duration_minutes 一致；建议使用“约X小时xxx版”，其中 X≈round(total_duration_minutes/60)。"
    )

    return PLAN_ITINERARY_SYSTEM_PROMPT + "\n\n" + "\n".join(lines)
