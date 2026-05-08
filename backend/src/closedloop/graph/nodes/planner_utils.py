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



def generate_and_score_combinations(
    queues: dict,
    patterns: list[dict],
    budget: float,
    required_duration_mins: float,
    top_k: int = 20
) -> tuple[list[dict], int, set[str]]:
    """
    使用 DFS 回溯算法生成、剪枝并对组合进行打分。
    避免了生成无用组合，数量级提升性能。
    返回: (最终TopK方案列表, 过滤前合法方案总数, 缺失的组件类型集合)
    """
    TOP_K_PER_STEP = 10
    valid_plans_info = []
    missing_types = set()
    valid_count_before_topk = 0
    
    # 预处理所有 pattern 的 step_pools，如果有缺失直接跳过该 pattern 并记录缺失类型
    for pattern in patterns:
        pattern_steps = pattern.get("steps", [])
        step_pools = []
        is_pattern_valid = True
        
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
                    # 降级寻找 (Fallback) - 基于语义邻近性
                    # 如果原定餐次找不到，优先寻找分量/类型相似的餐次，而不是盲目遍历所有
                    fallback_map = {
                        "lunch": ["dinner"],               # 午餐没了找晚餐
                        "dinner": ["lunch", "late_night"], # 晚餐没了找午餐或夜宵
                        "breakfast": ["afternoon_tea"],    # 早餐没了找下午茶（轻食）
                        "afternoon_tea": ["breakfast"],    # 下午茶没了找早餐（轻食）
                        "late_night": ["dinner"]           # 夜宵没了找晚餐
                    }
                    
                    fallbacks = fallback_map.get(meal_category, [])
                    for f in fallbacks:
                        if f in queues and queues[f]:
                            pool = queues[f][:TOP_K_PER_STEP]
                            break
                            
            if not pool:
                is_pattern_valid = False
                if step_type == "activity" and not queues.get("activity"):
                    missing_types.add("activity")
                elif step_type == "gift_shop" and not queues.get("gift_shop"):
                    missing_types.add("gift_shop")
                elif step_type.startswith("restaurant:"):
                    has_rest = any(f in queues and queues[f] for f in ["dinner", "lunch", "late_night", "breakfast", "afternoon_tea"])
                    if not has_rest:
                        missing_types.add("restaurant")
                break
                
            # 记录下这一步的类别，以备后续检查重复
            # 为了不修改原始队列数据，我们可以做浅拷贝并更新字段，或者在这里动态注入
            formatted_pool = []
            for item in pool:
                item_copy = item.copy()
                item_copy["_step_type"] = step_type
                if step_type.startswith("restaurant:"):
                    item_copy["_meal_category"] = step_type.split(":")[1]
                else:
                    item_copy["_meal_category"] = None
                formatted_pool.append(item_copy)
            step_pools.append(formatted_pool)
            
        if not is_pattern_valid:
            continue
            
        # 开始 DFS 回溯生成组合
        def dfs(step_idx, current_combo, current_pos, cost_without_gift, cost_with_gift, 
                total_duration_minutes, total_score, total_commute_distance, commutes_info, used_item_ids):
            nonlocal valid_count_before_topk
            
            # 剪枝 1: 如果当前已经超预算（即使不加后面的项目），直接剪枝
            if cost_without_gift > budget:
                return
            if cost_with_gift > budget * 1.2:
                return
                
            # 剪枝 2: 如果时间已经超出预期上限太多，直接剪枝 (考虑剩余步骤最少时间也可以加，这里简单用上限)
            if total_duration_minutes > required_duration_mins + 45:
                return
                
            # 达到叶子节点，计算回家的通勤和最终指标
            if step_idx == len(pattern_steps):
                dist_home = calculate_distance(current_pos, (0.0, 0.0))
                time_min_home, cost_val_home, mode_home = calculate_commute_info(dist_home)
                
                final_cost_without_gift = cost_without_gift + cost_val_home
                final_cost_with_gift = cost_with_gift + cost_val_home
                final_total_duration = total_duration_minutes + int(time_min_home)
                final_total_commute_distance = total_commute_distance + dist_home
                
                if final_cost_without_gift > budget:
                    return
                if final_cost_with_gift > budget * 1.2:
                    return
                if abs(final_total_duration - required_duration_mins) > 45:
                    return
                    
                # 计算打分
                avg_item_score = (total_score / len(current_combo)) if current_combo else 0
                base_score_100 = min(100.0, avg_item_score)
                spatial_score = max(0.0, 100.0 - max(0.0, final_total_commute_distance - 10.0) * 5.0)
                time_diff = abs(final_total_duration - required_duration_mins)
                time_score = max(0.0, 100.0 - time_diff * 1.5)
                budget_ratio = final_cost_with_gift / budget if budget > 0 else 0.0
                budget_score = max(0.0, 100.0 - abs(budget_ratio - 0.85) * 100.0)
                theme_score = 80.0
                
                final_score = (
                    base_score_100 * 0.35 +
                    spatial_score * 0.25 +
                    time_score * 0.20 +
                    budget_score * 0.10 +
                    theme_score * 0.10
                )
                
                # 构建完整的通勤信息
                final_commutes_info = commutes_info.copy()
                final_commutes_info.append({
                    "time": time_min_home,
                    "cost": cost_val_home,
                    "mode": mode_home,
                    "distance": dist_home
                })
                
                valid_count_before_topk += 1
                
                valid_plans_info.append({
                    "pattern": pattern,
                    "combo": current_combo.copy(),
                    "commutes": final_commutes_info,
                    "average_score": round(final_score, 2),
                    "total_cost": final_cost_with_gift,
                    "total_duration_minutes": final_total_duration
                })
                return

            # 继续下一步
            for selected_item in step_pools[step_idx]:
                item_id = selected_item.get("combo_id") or selected_item.get("package_id") or selected_item.get("gift_id", "unknown")
                if item_id in used_item_ids:
                    continue
                    
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
                    
                next_pos = get_coords(selected_item)
                dist = calculate_distance(current_pos, next_pos)
                time_min, cost_val, mode = calculate_commute_info(dist)
                
                new_total_duration = total_duration_minutes + duration_mins + int(time_min)
                
                # 剪枝判断，尽早退出
                if new_total_duration > required_duration_mins + 45:
                    continue
                    
                new_cost_with_gift = cost_with_gift + cost_val + price
                new_cost_without_gift = cost_without_gift + cost_val
                if step_type != "gift_shop":
                    new_cost_without_gift += price
                    
                if new_cost_without_gift > budget:
                    continue
                if new_cost_with_gift > budget * 1.2:
                    continue
                    
                new_total_score = total_score + score
                new_total_commute_distance = total_commute_distance + dist
                
                current_combo.append(selected_item)
                used_item_ids.add(item_id)
                commutes_info.append({
                    "time": time_min,
                    "cost": cost_val,
                    "mode": mode,
                    "distance": dist
                })
                
                dfs(step_idx + 1, current_combo, next_pos, new_cost_without_gift, new_cost_with_gift,
                    new_total_duration, new_total_score, new_total_commute_distance, commutes_info, used_item_ids)
                    
                # 回溯
                current_combo.pop()
                used_item_ids.remove(item_id)
                commutes_info.pop()
                
        # 从起始点(0.0, 0.0) 开始 DFS
        dfs(0, [], (0.0, 0.0), 0.0, 0.0, 0, 0, 0.0, [], set())
        
    # 获取 Top K 的方案
    if top_k > 0 and len(valid_plans_info) > top_k:
        valid_plans_info = heapq.nlargest(top_k, valid_plans_info, key=lambda x: x["average_score"])
    else:
        valid_plans_info.sort(key=lambda x: x["average_score"], reverse=True)
        
    return valid_plans_info, valid_count_before_topk, missing_types
