import itertools

def get_top_k_combinations(queues: dict, pattern_steps: list[str], max_variants: int = 20) -> list[list[dict]]:
    """
    给定各个类型的候选队列和行程的步骤结构，生成最多 max_variants 个组合（多套方案）。
    返回的是候选条目的组合列表。
    """
    step_pools = []
    # 我们为每个步骤提取出它的备选池（比如取 top 3）
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
            valid_combinations.append(combo)
            if len(valid_combinations) >= max_variants:
                break
                
    return valid_combinations

def filter_and_score_combinations(
    combinations: list[list[dict]],
    budget: float,
    required_duration_mins: float
) -> list[dict]:
    """
    过滤超出预算和时间误差过大的组合，并计算平均分和成本，按平均分降序排列。
    """
    valid_plans_info = []
    for combo in combinations:
        cost_without_gift = 0.0
        cost_with_gift = 0.0
        total_duration_minutes = 0
        total_score = 0
        
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
        
        # 过滤逻辑
        if cost_without_gift > budget:
            continue
        if cost_with_gift > budget * 1.2:
            continue
        if abs(total_duration_minutes - required_duration_mins) > 30:
            continue
            
        average_score = total_score / len(combo) if combo else 0
        valid_plans_info.append({
            "combo": combo,
            "average_score": average_score,
            "total_cost": cost_with_gift,
            "total_duration_minutes": total_duration_minutes
        })
        
    # 按照平均分降序排序
    valid_plans_info.sort(key=lambda x: x["average_score"], reverse=True)
    return valid_plans_info