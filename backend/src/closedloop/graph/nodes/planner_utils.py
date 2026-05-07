import itertools
import math
import heapq

def get_coords(item: dict) -> tuple[float, float]:
    """提取经纬度作为 (x, y) 坐标，单位 km"""
    loc = item.get("location", {})
    if isinstance(loc, dict):
        x = loc.get("longitude", 0.0)
        y = loc.get("latitude", 0.0)
        return (x, y)
    return (0.0, 0.0)

def calculate_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """计算两点间的欧氏距离（km）"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def calculate_commute_info(dist_km: float) -> tuple[float, float, str]:
    """
    根据距离计算通勤时间（分钟）、成本（元）以及推荐的交通方式。
    返回: (时间分钟, 成本元, 交通方式)
    """
    if dist_km < 2.0:
        # 步行: 5km/h, 偏置 2分钟, 0元
        speed_km_h = 5.0
        bias_min = 2.0
        cost = 0.0
        mode = "walking"
    elif dist_km <= 5.0:
        # 出租车: 30km/h, 偏置 5分钟, 起步价10元 + 超出3km部分2元/km
        speed_km_h = 30.0
        bias_min = 5.0
        cost = 10.0 + max(0, dist_km - 3.0) * 2.0
        mode = "taxi"
    else:
        # 自己开车: 40km/h, 偏置 10分钟, 默认成本 0元（暂不考虑油费/停车费）
        speed_km_h = 40.0
        bias_min = 10.0
        cost = 0.0
        mode = "driving"
        
    time_min = (dist_km / speed_km_h) * 60.0 + bias_min
    return time_min, cost, mode

def get_top_k_combinations(queues: dict, pattern: dict) -> list[dict]:
    """
    给定各个类型的候选队列和单个 Pattern，生成所有的组合（限制单步 Top 10，但不截断总数）。
    返回的是包含 Pattern 信息的字典列表。
    """
    pattern_steps = pattern.get("steps", [])
    step_pools = []
    # 我们为每个步骤提取出它的备选池（比如取 top 10）
    TOP_K_PER_STEP = 10
    
    for step_type in pattern_steps:
        pool = []
        if step_type == "activity":
            pool = queues.get("activity", [])[:TOP_K_PER_STEP]
        elif step_type == "gift_shop":
            pool = queues.get("gift_shop", [])[:TOP_K_PER_STEP]
        elif step_type.startswith("restaurant:"):
            meal_category = step_type.split(":")[1]
            if meal_category in queues and queues[meal_category]:
                pool = queues[meal_category][:TOP_K_PER_STEP]
            else:
                # 降级寻找
                fallbacks = ["dinner", "lunch", "late_night", "breakfast", "afternoon_tea"]
                for f in fallbacks:
                    if f in queues and queues[f]:
                        pool = queues[f][:TOP_K_PER_STEP]
                        break
                        
        if not pool:
            # 任何一步如果拿不到候选，则无法生成完整的方案
            return []
            
        # 记录下这一步的类别，以备后续检查重复
        for item in pool:
            item["_step_type"] = step_type
            if step_type.startswith("restaurant:"):
                # If we downgraded, we need the actual meal_category used or fallback meal_category.
                # However, to be safe, we just set it to the original requested meal category for the note.
                item["_meal_category"] = step_type.split(":")[1]
            else:
                item["_meal_category"] = None
            
        step_pools.append(pool)
        
    # 对各步骤的候选池进行笛卡尔积组合
    all_combinations = list(itertools.product(*step_pools))
    
    valid_combinations = []
    
    for combo in all_combinations:
        # 确保同一个候选条目不会在同一个方案中出现多次（例如两次活动不能是同一个地点）
        item_ids = []
        is_valid = True
        for item in combo:
            item_id = item.get("combo_id") or item.get("package_id") or item.get("gift_id", "unknown")
            if item_id in item_ids:
                is_valid = False
                break
            item_ids.append(item_id)
            
        if is_valid:
            valid_combinations.append({
                "pattern": pattern,
                "combo": combo
            })
                
    return valid_combinations

def filter_and_score_combinations(
    combinations_with_pattern: list[dict],
    budget: float,
    required_duration_mins: float,
    top_k: int = 20
) -> list[dict]:
    """
    过滤超出预算和时间误差过大的组合，并计算多维度打分，按综合得分降序排列。
    包含：空间与通勤、时间节奏、预算贴合度、场景主题连贯性等维度。
    """
    valid_plans_info = []
    for item_dict in combinations_with_pattern:
        pattern = item_dict["pattern"]
        combo = item_dict["combo"]
        
        cost_without_gift = 0.0
        cost_with_gift = 0.0
        total_duration_minutes = 0
        total_score = 0
        
        # 空间与通勤计算
        total_commute_distance = 0.0
        total_commute_time = 0.0
        total_commute_cost = 0.0
        current_pos = (0.0, 0.0) # 起点为家 (0,0)
        
        commutes_info = [] # 记录每一步的通勤明细
        
        for selected_item in combo:
            step_type = selected_item["_step_type"]
            meal_category = selected_item.get("_meal_category")
            
            price = selected_item.get("price", 0.0)
            score = selected_item.get("score", 0)
            
            if step_type == "activity":
                duration_mins = selected_item.get("duration_mins", 90)
            elif step_type == "gift_shop":
                duration_mins = 30
            elif step_type.startswith("restaurant:"):
                duration_mins = selected_item.get("duration_mins", 60) if meal_category != "afternoon_tea" else selected_item.get("duration_mins", 45)
            else:
                duration_mins = 60
                
            total_duration_minutes += duration_mins
            total_score += score
            
            if step_type == "gift_shop":
                cost_with_gift += price
            else:
                cost_without_gift += price
                cost_with_gift += price

            # 计算从上一位置到当前位置的通勤距离和时间、成本
            next_pos = get_coords(selected_item)
            dist = calculate_distance(current_pos, next_pos)
            time_min, cost_val, mode = calculate_commute_info(dist)
            
            commutes_info.append({
                "time": time_min,
                "cost": cost_val,
                "mode": mode,
                "distance": dist
            })
            
            total_commute_distance += dist
            total_commute_time += time_min
            total_commute_cost += cost_val
            
            current_pos = next_pos
        
        # 加上最后回家的距离和时间、成本
        dist_home = calculate_distance(current_pos, (0.0, 0.0))
        time_min_home, cost_val_home, mode_home = calculate_commute_info(dist_home)
        
        commutes_info.append({
            "time": time_min_home,
            "cost": cost_val_home,
            "mode": mode_home,
            "distance": dist_home
        })
        
        total_commute_distance += dist_home
        total_commute_time += time_min_home
        total_commute_cost += cost_val_home

        # 把总通勤时间加入到行程总时间里
        total_duration_minutes += int(total_commute_time)
        
        # 把总通勤成本加入到行程花费中
        cost_without_gift += total_commute_cost
        cost_with_gift += total_commute_cost
        
        # 过滤逻辑 (增加了一些容忍度，因为加入了通勤时间)
        if cost_without_gift > budget:
            continue
        if cost_with_gift > budget * 1.2:
            continue
        if abs(total_duration_minutes - required_duration_mins) > 45:
            continue
            
        # --- 多维度打分系统 ---
        
        # 1. 基础单品质量 (映射到 0-100)
        # rerank 中的单品有机 score 已经规范化为 0-100 分，但如果带有商业提权(commercial boost)可能会突破100
        # 为了保证行程总分体系的平衡，这里用 min(100.0) 将溢出的商业提权抹平（即商业特权只用于抢坑位，不额外加分给整个行程）
        avg_item_score = (total_score / len(combo)) if combo else 0
        base_score_100 = min(100.0, avg_item_score)
        
        # 2. 空间连贯与通勤惩罚 (理想情况总距离 < 10km，每超 1km 扣 5 分)
        spatial_score = max(0.0, 100.0 - max(0.0, total_commute_distance - 10.0) * 5.0)
        
        # 3. 时间松弛度 (越贴合 required_duration_mins 越好，每差 1 分钟扣 1.5 分)
        # required_duration_mins 是用户期望的整个行程的总耗时（例如 4 小时 = 240 分钟）
        time_diff = abs(total_duration_minutes - required_duration_mins)
        time_score = max(0.0, 100.0 - time_diff * 1.5)
        
        # 4. 预算贴合度 (理想花费在预算的 80%-90% 之间，过低或过高都扣分)
        budget_ratio = cost_with_gift / budget if budget > 0 else 0.0
        budget_score = max(0.0, 100.0 - abs(budget_ratio - 0.85) * 100.0)
        
        # 5. 场景主题连贯性 (目前给默认分，生产环境应替换为语义向量相似度)
        theme_score = 80.0
        
        # 综合加权总分
        final_score = (
            base_score_100 * 0.35 +
            spatial_score * 0.25 +
            time_score * 0.20 +
            budget_score * 0.10 +
            theme_score * 0.10
        )
        
        valid_plans_info.append({
            "pattern": pattern,
            "combo": combo,
            "commutes": commutes_info,
            # 将 average_score 字段覆写为最终加权分 final_score (方便前端兼容和 plan 记录)
            "average_score": round(final_score, 2),
            "total_cost": cost_with_gift,
            "total_duration_minutes": total_duration_minutes
        })
        
    valid_count_before_topk = len(valid_plans_info)
    
    # 获取 Top K 的方案，使用 heapq.nlargest 减少排序时间 (O(N log K) vs O(N log N))
    if top_k > 0 and len(valid_plans_info) > top_k:
        valid_plans_info = heapq.nlargest(top_k, valid_plans_info, key=lambda x: x["average_score"])
    else:
        valid_plans_info.sort(key=lambda x: x["average_score"], reverse=True)
        
    return valid_plans_info, valid_count_before_topk