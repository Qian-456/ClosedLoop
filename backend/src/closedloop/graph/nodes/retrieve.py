from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.utils.mock_db import load_mock_data
from closedloop.core.logger import logger

def parse_time(time_str: str) -> float:
    """解析 HH:MM 为小时浮点数"""
    if not time_str:
        return 0.0
    parts = time_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) + int(parts[1]) / 60.0
    return 0.0

def hard_filter(item: dict, constraints: Constraints) -> bool:
    """第一层：DB 硬过滤"""
    # 1. 预算限制
    people_count = constraints.people_count or 1
    budget = constraints.budget
    
    if item["type"] == "restaurant":
        price = item.get("avg_price_per_person", 0)
        if price * people_count > budget * 0.7:
            return False
    elif item["type"] == "activity":
        price = item.get("price_per_person", 0)
        if price * people_count > budget * 0.7:
            return False
    elif item["type"] == "add_on":
        price = item.get("price", 0)
        if price > budget * 0.3:
            return False
            
    # 2. 距离限制 (附加服务无此限制)
    if "distance_km" in item:
        pref_dist = constraints.preferred_distance
        # 给 1km 左右的宽容度
        max_distance = 12.0
        if pref_dist == "<2km":
            max_distance = 3.0
        elif pref_dist == "2km-5km":
            max_distance = 6.0
            
        if item["distance_km"] > max_distance:
            return False
            
    # 3. 营业时间限制
    time_period = constraints.time_period
    if time_period and "-" in time_period:
        parts = time_period.split("-")
        req_start = parse_time(parts[0])
        req_end = parse_time(parts[1])
        
        open_time = parse_time(item.get("open_time", "00:00"))
        close_time = parse_time(item.get("close_time", "23:59"))
        if close_time < open_time: # 跨天，如 11:00 - 02:00
            close_time += 24.0

        if req_end <= open_time or req_start >= close_time:
            # 考虑跨天的情况，放宽条件
            if not (close_time > 24 and req_start + 24 < close_time):
                return False

    # 4. 儿童年龄限制
    if item["type"] == "activity" and constraints.group_type == "family":
        child_age = constraints.child_age
        if child_age is not None:
            min_age = item.get("min_child_age", 0)
            max_age = item.get("max_child_age", 99)
            if child_age < min_age or child_age > max_age:
                return False
                
    return True

def rule_filter(item: dict, constraints: Constraints) -> bool:
    """第二层：规则过滤"""
    tags = set(item.get("tags", []))
    avoid_tags = set(item.get("avoid_tags", []))
    
    # 1. 家庭与常识
    if constraints.group_type == "family":
        forbidden = {"酒吧", "精酿", "密室", "夜宵"}
        if tags.intersection(forbidden):
            return False
            
    # 2. 饮食限制
    if constraints.dietary_restrictions:
        # 简单映射：如果有"辣"，避开"热辣"、"火锅"、"重口味"
        # 如果有"海鲜"，避开"海鲜"
        diet_keywords = set()
        for r in constraints.dietary_restrictions:
            if "辣" in r:
                diet_keywords.update(["热辣", "重口味", "火锅"])
            if "海鲜" in r:
                diet_keywords.update(["海鲜", "日料", "刺身"])
                
        if tags.intersection(diet_keywords):
            return False
            
    # 3. 避坑标签
    if constraints.group_type == "family" and "幼儿" in avoid_tags:
        return False
        
    return True

def score_item(item: dict, constraints: Constraints) -> int:
    """第三层：打分排序"""
    score = 0
    
    # 基础评分
    score += item.get("rating", 0) * 10
    
    # 距离偏好加分
    if "distance_km" in item:
        score += max(0, 10 - item["distance_km"]) * 2
        
    # 人群匹配
    if constraints.group_type in item.get("suitable_groups", []):
        score += 15
        
    # 偏好加分
    if constraints.activity_preferences:
        tags = set(item.get("tags", []))
        for pref in constraints.activity_preferences:
            if pref in tags:
                score += 10
                
            
    return int(score)

def retrieve_candidates(state: ClosedLoopState) -> ClosedLoopState:
    """
    检索过滤节点：根据 constraints 过滤出合适的餐厅、活动和附加服务。
    """
    logger.info("phase=retrieve_candidates | input=start")
    
    constraints = state.get("constraints")
    if not constraints:
        logger.error("phase=retrieve_candidates | error=no constraints found")
        state["candidates"] = {"nearby_restaurants": [], "nearby_activities": [], "nearby_gifts": []}
        return state
        
    # 如果 constraint 已经是字典（由 typeddict 保证，但防万一），转成模型
    if isinstance(constraints, dict):
        constraints = Constraints(**constraints)

    try:
        nearby_restaurants = load_mock_data("restaurants.json")
        nearby_activities = load_mock_data("activities.json")
        nearby_gifts = load_mock_data("add_ons.json")
        
        candidates = {
            "nearby_restaurants": [],
            "nearby_activities": [],
            "nearby_gifts": []
        }
        
        for category, items in [("nearby_restaurants", nearby_restaurants), ("nearby_activities", nearby_activities), ("nearby_gifts", nearby_gifts)]:
            filtered_items = []
            for item in items:
                if not hard_filter(item, constraints):
                    continue
                if not rule_filter(item, constraints):
                    continue
                
                # 计算分数并存入
                item_copy = item.copy()
                item_copy["_score"] = score_item(item, constraints)
                filtered_items.append(item_copy)
                
            # 按分数降序排序
            filtered_items.sort(key=lambda x: x["_score"], reverse=True)
            # 移除 _score
            for item in filtered_items:
                del item["_score"]
                
            candidates[category] = filtered_items
            
        state["candidates"] = candidates
        logger.info(f"phase=retrieve_candidates | output=found {len(candidates['nearby_restaurants'])} restaurants, {len(candidates['nearby_activities'])} activities, {len(candidates['nearby_gifts'])} gifts")
    except Exception as e:
        logger.error(f"phase=retrieve_candidates | error={e}")
        state["candidates"] = {"nearby_restaurants": [], "nearby_activities": [], "nearby_gifts": []}
        
    return state
