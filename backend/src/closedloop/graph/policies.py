import re
from typing import TypedDict, Optional

class Pattern(TypedDict):
    id: str
    group: str
    duration_range: tuple[float, float]
    steps: list[str]
    desc: str
    start_time_pref: list[str]

PATTERNS: list[Pattern] = []
_groups = ["family_kids", "family_mild", "friends"]

for g in _groups:
    # --- Short (3.5 - 4.5) ---
    # 2-3 steps + gift
    # Lunch starts
    PATTERNS.append({
        "id": f"{g.upper()}-S-L1", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["restaurant:lunch", "activity", "gift_shop"],
        "desc": "午餐+主活动+惊喜", "start_time_pref": ["lunch"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-S-L2", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["activity", "restaurant:lunch", "gift_shop"],
        "desc": "主活动+午餐+惊喜", "start_time_pref": ["lunch"]
    })
    # Afternoon starts
    PATTERNS.append({
        "id": f"{g.upper()}-S-A1", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["activity", "restaurant:afternoon_tea", "gift_shop"],
        "desc": "主活动+下午茶+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-S-A2", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["activity", "activity_light", "gift_shop"],
        "desc": "主活动+轻活动+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    # Dinner starts
    PATTERNS.append({
        "id": f"{g.upper()}-S-D1", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["activity", "restaurant:dinner", "gift_shop"],
        "desc": "主活动+晚餐+惊喜", "start_time_pref": ["dinner"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-S-D2", "group": g, "duration_range": [3.5, 4.5],
        "steps": ["restaurant:dinner", "activity_light", "gift_shop"],
        "desc": "晚餐+轻活动+惊喜", "start_time_pref": ["dinner"]
    })

    # --- Medium (4.5 - 5.5) ---
    # 3-4 steps + gift
    # Lunch starts
    if g == "family_kids":
        PATTERNS.append({
            "id": f"{g.upper()}-M-L1", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["activity_light", "restaurant:lunch", "activity_light", "gift_shop"],
            "desc": "轻活动+午餐+轻活动+惊喜", "start_time_pref": ["lunch"]
        })
        PATTERNS.append({
            "id": f"{g.upper()}-M-L2", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["activity_light", "restaurant:lunch", "gift_shop", "activity_light"],
            "desc": "轻活动+午餐+惊喜+轻活动", "start_time_pref": ["lunch"]
        })
        PATTERNS.append({
            "id": f"{g.upper()}-M-L3", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["activity", "restaurant:lunch", "gift_shop", "activity_light"],
            "desc": "主活动+午餐+惊喜+轻活动", "start_time_pref": ["lunch"]
        })
        PATTERNS.append({
            "id": f"{g.upper()}-M-L4", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["activity", "restaurant:lunch", "activity_light", "gift_shop"],
            "desc": "主活动+午餐+轻活动+惊喜", "start_time_pref": ["lunch"]
        })
    else:
        PATTERNS.append({
            "id": f"{g.upper()}-M-L1", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["restaurant:lunch", "activity", "activity_light", "gift_shop"],
            "desc": "午餐+主活动+轻活动+惊喜", "start_time_pref": ["lunch"]
        })
        PATTERNS.append({
            "id": f"{g.upper()}-M-L2", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["activity_light", "restaurant:lunch", "activity", "gift_shop"],
            "desc": "轻活动+午餐+主活动+惊喜", "start_time_pref": ["lunch"]
        })
        PATTERNS.append({
            "id": f"{g.upper()}-M-L3", "group": g, "duration_range": [4.5, 5.5],
            "steps": ["restaurant:lunch", "activity", "restaurant:afternoon_tea", "gift_shop"],
            "desc": "午餐+主活动+下午茶+惊喜", "start_time_pref": ["lunch"]
        })
    # Afternoon starts
    PATTERNS.append({
        "id": f"{g.upper()}-M-A1", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["activity", "restaurant:afternoon_tea", "activity_light", "gift_shop"],
        "desc": "主活动+下午茶+轻活动+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-M-A2", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["activity", "activity", "gift_shop"],
        "desc": "双主活动+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-M-A3", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["activity", "restaurant:dinner", "activity_light", "gift_shop"],
        "desc": "主活动+晚餐+轻活动+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-M-A4", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["activity", "restaurant:afternoon_tea", "activity", "gift_shop"],
        "desc": "主活动+下午茶+主活动+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    # Dinner starts
    PATTERNS.append({
        "id": f"{g.upper()}-M-D1", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["activity", "restaurant:dinner", "activity_light", "gift_shop"],
        "desc": "主活动+晚餐+轻活动+惊喜", "start_time_pref": ["dinner"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-M-D2", "group": g, "duration_range": [4.5, 5.5],
        "steps": ["restaurant:dinner", "activity", "activity_light", "gift_shop"],
        "desc": "晚餐+主活动+轻活动+惊喜", "start_time_pref": ["dinner"]
    })

    # --- Long (5.5 - 6.5) ---
    # 4-5 steps + gift
    # Lunch starts
    PATTERNS.append({
        "id": f"{g.upper()}-L-L1", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["restaurant:lunch", "activity", "restaurant:afternoon_tea", "activity_light", "gift_shop"],
        "desc": "午餐+主活动+下午茶+轻活动+惊喜", "start_time_pref": ["lunch"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-L2", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["activity_light", "restaurant:lunch", "activity", "restaurant:afternoon_tea", "gift_shop"],
        "desc": "轻活动+午餐+主活动+下午茶+惊喜", "start_time_pref": ["lunch"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-L3", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["restaurant:lunch", "activity", "activity", "gift_shop"],
        "desc": "午餐+双主活动+惊喜", "start_time_pref": ["lunch"]
    })
    # Afternoon starts
    PATTERNS.append({
        "id": f"{g.upper()}-L-A1", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["activity", "restaurant:afternoon_tea", "activity_light", "restaurant:dinner", "gift_shop"],
        "desc": "主活动+下午茶+轻活动+晚餐+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-A2", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["activity", "activity", "restaurant:dinner", "gift_shop"],
        "desc": "双主活动+晚餐+惊喜", "start_time_pref": ["afternoon_tea"]
    })
    # Dinner starts
    PATTERNS.append({
        "id": f"{g.upper()}-L-D1", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["restaurant:afternoon_tea", "activity", "restaurant:dinner", "gift_shop"],
        "desc": "下午茶+主活动+晚餐+惊喜", "start_time_pref": ["dinner"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-D2", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["activity_light", "restaurant:afternoon_tea", "activity_light", "restaurant:dinner", "gift_shop"],
        "desc": "轻活动+下午茶+轻活动+晚餐+惊喜", "start_time_pref": ["dinner"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-D3", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["restaurant:afternoon_tea", "activity_light", "activity_light", "restaurant:dinner", "gift_shop"],
        "desc": "下午茶+轻活动+轻活动+晚餐+惊喜", "start_time_pref": ["dinner"]
    })
    PATTERNS.append({
        "id": f"{g.upper()}-L-D4", "group": g, "duration_range": [5.5, 6.5],
        "steps": ["activity_light", "restaurant:afternoon_tea", "activity", "restaurant:dinner", "gift_shop"],
        "desc": "轻活动+下午茶+主活动+晚餐+惊喜", "start_time_pref": ["dinner"]
    })


def parse_time_period(time_period: str) -> tuple[float, float]:
    """
    解析时间段字符串，返回 (start_time_hours, duration_hours)。
    兼容两种格式：
    - 新语义：'HH:MM'（目标开始时间）
    - 旧语义：'HH:MM-HH:MM'（起止时间段）
    例如 "13:00-18:00" 返回 (13.0, 5.0)。
    """
    match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", time_period)
    if match:
        start_h = int(match.group(1)) + int(match.group(2)) / 60.0
        end_h = int(match.group(3)) + int(match.group(4)) / 60.0
        
        # 跨天处理
        if end_h < start_h:
            end_h += 24.0
            
        return start_h, end_h - start_h

    match_start = re.search(r"(\d{1,2}):(\d{2})", time_period or "")
    if match_start:
        start_h = int(match_start.group(1)) + int(match_start.group(2)) / 60.0
        return start_h, 6.0

    # 理论上不会走到这里，作为容错返回默认值
    return 14.0, 6.0


def parse_target_start_time(time_period: str) -> float:
    if not isinstance(time_period, str):
        return 14.0
    s = time_period.strip()
    if "-" in s:
        s = s.split("-", 1)[0].strip()
    match = re.search(r"(\d{1,2}):(\d{2})", s)
    if not match:
        return 14.0
    return int(match.group(1)) + int(match.group(2)) / 60.0


def get_time_of_day(start_time_hours: float) -> str:
    """根据开始时间归类时段：breakfast, lunch, afternoon_tea, dinner, late_night"""
    if start_time_hours < 10.5:
        return "breakfast"
    elif start_time_hours < 13.0:
        return "lunch"
    elif start_time_hours < 17.0:
        return "afternoon_tea"
    elif start_time_hours < 20.0:
        return "dinner"
    else:
        return "late_night"


def match_patterns(
    group_type: str, 
    child_profiles: list[tuple[str, int]], 
    start_time_hours: float, 
    duration_hours_range: tuple[float, float] | float
) -> list[Pattern]:
    """
    根据人群分类、开始时间和持续时间，匹配所有合适的 Pattern 列表。
    """
    # 1. 确定 group_category
    group_category = "friends"
    if group_type == "family":
        child_ages = [age for _, age in (child_profiles or []) if isinstance(age, int)]
        if child_ages and max(child_ages) >= 10:
            group_category = "family_teens"
        elif child_ages and max(child_ages) <= 3:
            group_category = "family_mild"
        else:
            group_category = "family_kids"
            
    # 2. 确定 time_of_day
    time_of_day = get_time_of_day(start_time_hours)
    
    # 3. 筛选候选
    if isinstance(duration_hours_range, (int, float)):
        duration_hours_range = (float(duration_hours_range), float(duration_hours_range))
    is_range = abs(duration_hours_range[0] - duration_hours_range[1]) > 1e-9
    duration_mid = (duration_hours_range[0] + duration_hours_range[1]) / 2.0

    candidates = []
    for p in PATTERNS:
        # Compatibility fallback if group_category isn't directly matched
        # (Since we just generated family_kids, family_mild, friends explicitly, we map teens to kids if missing)
        p_group = p["group"]
        if p_group != group_category:
            if group_category == "family_teens" and p_group == "family_kids":
                pass # Allow fallback
            else:
                continue
        
        # 超过4个小时的方案都要有吃饭约束：如果预期下限 > 4.0，剔除无吃饭的 pattern
        has_restaurant = any(step.startswith("restaurant:") for step in p["steps"])
        if duration_hours_range[0] > 4.0 and not has_restaurant:
            continue
        
        min_d, max_d = p["duration_range"]
        # 容差范围
        p_min = min_d - 0.5
        p_max = max_d + 0.5
        if duration_hours_range[0] <= p_max and duration_hours_range[1] >= p_min:
            candidates.append(p)
            
    # 如果没有找到匹配时长的，放宽时长限制
    if not candidates:
        for p in PATTERNS:
            p_group = p["group"]
            if p_group == group_category or (group_category == "family_teens" and p_group == "family_kids"):
                candidates.append(p)
                
    if not candidates:
        # Fallback to a safe default
        return [PATTERNS[0]]
        
    # 4. 优先匹配 time_of_day，但保留所有候选进行降级
    for p in candidates:
        p["_is_preferred_time"] = time_of_day in p["start_time_pref"]
        p["_duration_diff"] = abs((p["duration_range"][0] + p["duration_range"][1]) / 2 - duration_mid)
        
    candidates.sort(key=lambda p: (not p["_is_preferred_time"], p["_duration_diff"]))
    
    # 清理临时字段
    for p in candidates:
        p.pop("_is_preferred_time", None)
        p.pop("_duration_diff", None)
        
    return candidates
