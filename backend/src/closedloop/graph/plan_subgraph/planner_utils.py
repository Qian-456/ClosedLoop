import itertools
import math
import heapq

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger

DELIVERY_BASE_FEE = 3.0
DELIVERY_PER_KM_FEE = 2.0
DELIVERY_MAX_FEE = 15.0


def calculate_delivery_fee(delivery_distance_km: float) -> float:
    fee = DELIVERY_BASE_FEE + DELIVERY_PER_KM_FEE * float(delivery_distance_km)
    return float(round(min(DELIVERY_MAX_FEE, max(0.0, fee)), 2))

def get_coords(item: dict) -> tuple[float, float]:
    """提取经纬度作为 (x, y) 坐标，单位 km"""
    x = item.get("longitude")
    y = item.get("latitude")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return (float(x), float(y))

    loc = item.get("location", {})
    if isinstance(loc, dict):
        x2 = loc.get("longitude", 0.0)
        y2 = loc.get("latitude", 0.0)
        return (float(x2 or 0.0), float(y2 or 0.0))

    return (0.0, 0.0)

def calculate_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """计算两点间的欧氏距离（km）"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def _commute_by_mode(dist_km: float, mode: str) -> tuple[float, float, str]:
    if mode == "walking":
        speed_km_h = 5.0
        bias_min = 2.0
        cost = 0.0
    elif mode == "taxi":
        speed_km_h = 30.0
        bias_min = 5.0
        cost = 10.0 + max(0, dist_km - 3.0) * 2.0
    else:
        speed_km_h = 40.0
        bias_min = 10.0
        cost = 0.0

    time_min = (dist_km / speed_km_h) * 60.0 + bias_min
    return time_min, cost, mode


def calculate_commute_info_for_mode(dist_km: float, mode: str) -> tuple[float, float, str]:
    return _commute_by_mode(dist_km, mode)


def calculate_commute_info(dist_km: float, commute_preference: str = "auto") -> tuple[float, float, str]:
    """
    根据距离计算通勤时间（分钟）、成本（元）以及推荐的交通方式。
    返回: (时间分钟, 成本元, 交通方式)
    """
    if commute_preference == "driving":
        return _commute_by_mode(dist_km, "driving")

    mode = "walking" if dist_km <= 2.0 else "taxi"
    return _commute_by_mode(dist_km, mode)


def calculate_commute_options(dist_km: float, commute_preference: str = "auto") -> list[dict]:
    """
    为前端提供可切换的通勤方式选项（时间/费用均为估算）。
    返回: [{"mode": "walking|taxi|driving", "time_minutes": int, "cost": float}, ...]
    """
    options = []
    modes = ["driving"] if commute_preference == "driving" else ["walking", "taxi"]

    for mode in modes:
        time_min, cost, _ = _commute_by_mode(dist_km, mode)
        options.append({
            "mode": mode,
            "time_minutes": int(math.ceil(time_min)),
            "cost": float(round(cost, 2)),
        })

    return options


def compute_time_window_params(duration_range_mins: tuple[float, float]) -> dict:
    a = float(duration_range_mins[0])
    b = float(duration_range_mins[1])
    if a > b:
        a, b = b, a

    range_len = b - a

    if range_len <= 0:
        target = a
        return {
            "is_range": False,
            "target_mins": target,
            "hard_min_mins": target - 45.0,
            "hard_max_mins": target + 45.0,
            "mid_mins": target,
            "full_min_mins": target,
            "full_max_mins": target,
            "range_len_mins": 0.0,
            "full_radius_mins": 0.0,
            "hard_radius_mins": 45.0,
        }

    hard_tol = 15.0
    hard_min = a - hard_tol
    hard_max = b + hard_tol
    mid = (a + b) / 2.0
    full_min = a
    full_max = b

    return {
        "is_range": True,
        "target_mins": mid,
        "hard_min_mins": hard_min,
        "hard_max_mins": hard_max,
        "mid_mins": mid,
        "full_min_mins": full_min,
        "full_max_mins": full_max,
        "range_len_mins": range_len,
        "full_radius_mins": 0.0,
        "hard_radius_mins": hard_tol,
        "hard_tol_mins": hard_tol,
    }


def compute_time_score(total_duration_mins: float, params: dict) -> float:
    if not params.get("is_range"):
        target = float(params.get("target_mins", 0.0))
        diff = abs(float(total_duration_mins) - target)
        return max(0.0, 100.0 - diff * 1.5)

    hard_min = float(params["hard_min_mins"])
    hard_max = float(params["hard_max_mins"])
    if total_duration_mins < hard_min or total_duration_mins > hard_max:
        return 0.0

    full_min = float(params["full_min_mins"])
    full_max = float(params["full_max_mins"])
    if full_min <= total_duration_mins <= full_max:
        return 100.0

    if total_duration_mins < full_min:
        diff = full_min - total_duration_mins
    else:
        diff = total_duration_mins - full_max

    hard_tol = float(params.get("hard_tol_mins", 15.0))
    if hard_tol <= 0.0:
        return 100.0

    t = diff / hard_tol
    if t < 0.0:
        t = 0.0
    if t > 1.0:
        t = 1.0

    return 100.0 - 40.0 * (t ** 2)



def generate_and_score_combinations(
    queues: dict,
    patterns: list[dict],
    budget: float,
    required_duration_range_mins: tuple[float, float],
    commute_preference: str = "auto",
    dfs_global_prune_stats: dict = None,
) -> tuple[list[dict], int, set[str]]:
    """
    使用 DFS 回溯算法生成、剪枝并对组合进行打分。
    避免了生成无用组合，数量级提升性能。
    返回: (最终TopK方案列表, 过滤前合法方案总数, 缺失的组件类型集合)
    """
    config = get_config()
    LoggerManager.setup(config)
    log_stats = bool(getattr(config.logging, "LOG_PLANNER_STATS", False))

    TOP_K_PER_STEP = 10
    grouped_plans = []
    missing_types = set()
    valid_count_before_topk = 0

    num_patterns_input = len(patterns)
    num_patterns_used = 0
    skipped_patterns_count = 0
    skipped_reason_counts: dict[str, int] = {}

    time_params = compute_time_window_params(required_duration_range_mins)
    is_range = bool(time_params.get("is_range"))
    target_duration_mins = float(time_params.get("target_mins", 0.0))
    hard_max_mins = float(time_params.get("hard_max_mins", target_duration_mins + 45.0))
    
    # 预处理所有 pattern 的 step_pools，如果有缺失直接跳过该 pattern 并记录缺失类型
    for pattern in patterns:
        pattern_steps = pattern.get("steps", [])
        step_pools = []
        is_pattern_valid = True

        step_pool_sizes: dict[str, int] = {s: 0 for s in pattern_steps}
        fallback_used: dict[str, str] = {}
        skip_reason_code: str | None = None
        missing_step_type: str | None = None
        pattern_valid_leaf_count = 0
        prune_counts = {
            "prune_budget_over": 0,
            "prune_partial_time_over": 0,
            "prune_walk_leg_over_2km": 0,
            "prune_walk_home_over_2km": 0,
            "prune_gift_delivery_radius": 0,
            "prune_final_duration_too_short": 0,
            "prune_final_duration_too_long": 0,
        }
        
        for step_type in pattern_steps:
            pool = []
            if step_type == "activity":
                pool = queues.get("activity", [])[:TOP_K_PER_STEP]
            elif step_type == "activity_light":
                pool = queues.get("activity_light", [])[:TOP_K_PER_STEP]
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
                            fallback_used[step_type] = f"restaurant:{f}"
                            break
                            
            step_pool_sizes[step_type] = len(pool)
            if not pool:
                is_pattern_valid = False
                missing_step_type = step_type
                if step_type == "activity" and not queues.get("activity"):
                    missing_types.add("activity")
                    skip_reason_code = "missing_activity_pool"
                elif step_type == "activity_light" and not queues.get("activity_light"):
                    missing_types.add("activity")
                    skip_reason_code = "missing_activity_pool"
                elif step_type == "gift_shop" and not queues.get("gift_shop"):
                    missing_types.add("gift_shop")
                    skip_reason_code = "missing_gift_pool"
                elif step_type.startswith("restaurant:"):
                    has_rest = any(f in queues and queues[f] for f in ["dinner", "lunch", "late_night", "breakfast", "afternoon_tea"])
                    if not has_rest:
                        missing_types.add("restaurant")
                        skip_reason_code = "missing_restaurant_pool"
                    else:
                        skip_reason_code = "missing_meal_pool"
                break
                
            # 记录下这一步的类别，以备后续检查重复
            # 为了不修改原始队列数据，我们可以做浅拷贝并更新字段，或者在这里动态注入
            prices: list[float] = []
            for item in pool:
                v = item.get("price", 0.0)
                if isinstance(v, (int, float)):
                    prices.append(float(v))
            min_price = min(prices) if prices else 0.0
            max_price = max(prices) if prices else 0.0
            price_range = max(0.0, max_price - min_price)

            formatted_pool = []
            for item in pool:
                item_copy = item.copy()
                item_copy["_step_type"] = step_type
                if step_type.startswith("restaurant:"):
                    item_copy["_meal_category"] = step_type.split(":")[1]
                else:
                    item_copy["_meal_category"] = None
                price = item_copy.get("price", 0.0)
                if not isinstance(price, (int, float)):
                    price = 0.0
                if price_range > 0:
                    item_copy["_premium_bonus"] = (float(price) - min_price) / price_range * 20.0
                else:
                    item_copy["_premium_bonus"] = 0.0
                formatted_pool.append(item_copy)
            step_pools.append(formatted_pool)
            
        if not is_pattern_valid:
            skipped_patterns_count += 1
            if skip_reason_code:
                skipped_reason_counts[skip_reason_code] = skipped_reason_counts.get(skip_reason_code, 0) + 1
            if log_stats:
                pattern_id = pattern.get("id") or pattern.get("pattern_id")
                pattern_desc = pattern.get("desc")
                logger.info(
                    f"phase=planner_pattern_skipped | pattern_id={pattern_id} | desc={pattern_desc} | steps={pattern_steps} | missing_step_type={missing_step_type} | skip_reason_code={skip_reason_code} | step_pool_sizes={step_pool_sizes} | fallback_used={fallback_used}"
                )
            continue

        num_patterns_used += 1
            
        pattern_plans = []
            
        # 开始 DFS 回溯生成组合
        def dfs(step_idx, current_combo, current_pos, cost_without_gift, cost_with_gift, 
                total_duration_minutes, total_score_raw, total_score_clamped_100, total_premium_bonus,
                total_commute_distance, commutes_info, used_item_ids):
            nonlocal valid_count_before_topk
            nonlocal pattern_valid_leaf_count
            
            # 剪枝 1: 如果当前已经超预算（即使不加后面的项目），直接剪枝
            if cost_without_gift > budget:
                prune_counts["prune_budget_over"] += 1
                return
            if cost_with_gift > budget * 1.2:
                prune_counts["prune_budget_over"] += 1
                return
                
            # 剪枝 2: 如果时间已经超出预期上限太多，直接剪枝 (考虑剩余步骤最少时间也可以加，这里简单用上限)
            if is_range:
                if total_duration_minutes > hard_max_mins:
                    prune_counts["prune_partial_time_over"] += 1
                    return
            else:
                if total_duration_minutes > target_duration_mins + 45:
                    prune_counts["prune_partial_time_over"] += 1
                    return
                
            # 达到叶子节点，计算回家的通勤和最终指标
            if step_idx == len(pattern_steps):
                dist_home = calculate_distance(current_pos, (0.0, 0.0))
                if commute_preference == "walking" and dist_home > 2.0:
                    prune_counts["prune_walk_home_over_2km"] += 1
                    return
                time_min_home, cost_val_home, mode_home = calculate_commute_info(
                    dist_home, commute_preference=commute_preference
                )
                
                final_cost_without_gift = cost_without_gift + cost_val_home
                final_cost_with_gift = cost_with_gift + cost_val_home
                final_total_duration = total_duration_minutes + int(math.ceil(time_min_home))
                final_total_commute_distance = total_commute_distance + dist_home
                
                if final_cost_without_gift > budget:
                    prune_counts["prune_budget_over"] += 1
                    return
                if final_cost_with_gift > budget * 1.2:
                    prune_counts["prune_budget_over"] += 1
                    return
                if is_range:
                    hard_min_mins = float(time_params["hard_min_mins"])
                    if final_total_duration < hard_min_mins:
                        prune_counts["prune_final_duration_too_short"] += 1
                        return
                    if final_total_duration > hard_max_mins:
                        prune_counts["prune_final_duration_too_long"] += 1
                        return
                else:
                    if final_total_duration < target_duration_mins - 45:
                        prune_counts["prune_final_duration_too_short"] += 1
                        return
                    if final_total_duration > target_duration_mins + 45:
                        prune_counts["prune_final_duration_too_long"] += 1
                        return
                    
                # 计算打分
                avg_item_score_raw = (total_score_raw / len(current_combo)) if current_combo else 0.0
                base_score_100 = min(100.0, avg_item_score_raw)
                spatial_score = max(0.0, 100.0 - max(0.0, final_total_commute_distance - 10.0) * 5.0)
                time_score = compute_time_score(final_total_duration, time_params)
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

                avg_item_score_clamped = (total_score_clamped_100 / len(current_combo)) if current_combo else 0.0
                avg_premium_bonus = (total_premium_bonus / len(current_combo)) if current_combo else 0.0
                experience_score = (
                    avg_item_score_clamped * 0.65 +
                    spatial_score * 0.25 +
                    theme_score * 0.10 +
                    avg_premium_bonus
                )
                experience_score = min(100.0, max(0.0, experience_score))
                
                # 构建完整的通勤信息
                final_commutes_info = commutes_info.copy()
                final_commutes_info.append({
                    "time": time_min_home,
                    "cost": round(cost_val_home, 2),
                    "mode": mode_home,
                    "distance": dist_home
                })
                
                valid_count_before_topk += 1
                pattern_valid_leaf_count += 1
                
                pattern_plans.append({
                    "pattern": pattern,
                    "combo": current_combo.copy(),
                    "commutes": final_commutes_info,
                    "average_score": round(final_score, 2),
                    "experience_score": round(experience_score, 2),
                    "total_cost": round(final_cost_with_gift, 2),
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
                premium_bonus = selected_item.get("_premium_bonus", 0.0)
                if not isinstance(premium_bonus, (int, float)):
                    premium_bonus = 0.0
                
                if step_type == "activity":
                    duration_mins = selected_item.get("duration_mins", 90)
                elif step_type == "gift_shop":
                    duration_mins = int(selected_item.get("receive_duration_mins") or 10)
                elif step_type.startswith("restaurant:"):
                    duration_mins = selected_item.get("duration_mins", 60) if meal_category != "afternoon_tea" else selected_item.get("duration_mins", 45)
                else:
                    duration_mins = 60

                expected_wait_minutes = selected_item.get("expected_wait_minutes", 0)
                duration_mins += expected_wait_minutes

                if step_type == "gift_shop":
                    gift_shop_pos = get_coords(selected_item)
                    delivery_distance_km = calculate_distance(current_pos, gift_shop_pos)
                    delivery_radius_km = float(selected_item.get("delivery_radius_km") or 5.0)
                    if delivery_distance_km > delivery_radius_km:
                        prune_counts["prune_gift_delivery_radius"] += 1
                        continue

                    delivery_fee = calculate_delivery_fee(delivery_distance_km)
                    gift_price = float(price) if isinstance(price, (int, float)) else 0.0

                    # 添加礼品店本身的耗时，并在步骤后附加 5 分钟的空余时间缓冲
                    new_total_duration = total_duration_minutes + duration_mins + 5

                    if is_range:
                        if new_total_duration > hard_max_mins:
                            continue
                    else:
                        if new_total_duration > target_duration_mins + 45:
                            continue

                    new_cost_with_gift = cost_with_gift + gift_price + delivery_fee
                    new_cost_without_gift = cost_without_gift

                    if new_cost_without_gift > budget:
                        continue
                    if new_cost_with_gift > budget * 1.2:
                        continue

                    score_raw = float(score) if isinstance(score, (int, float)) else 0.0
                    score_clamped = min(100.0, max(0.0, score_raw))

                    new_total_score_raw = total_score_raw + score_raw
                    new_total_score_clamped_100 = total_score_clamped_100 + score_clamped
                    new_total_premium_bonus = total_premium_bonus + float(premium_bonus)
                    new_total_commute_distance = total_commute_distance

                    item_for_combo = selected_item.copy()
                    item_for_combo["gift_price"] = gift_price
                    item_for_combo["delivery_fee"] = delivery_fee
                    item_for_combo["delivery_distance_km"] = float(round(delivery_distance_km, 2))

                    current_combo.append(item_for_combo)
                    used_item_ids.add(item_id)
                    commutes_info.append({
                        "time": 0.0,
                        "cost": 0.0,
                        "mode": None,
                        "distance": 0.0
                    })

                    dfs(step_idx + 1, current_combo, current_pos, new_cost_without_gift, new_cost_with_gift,
                        new_total_duration, new_total_score_raw, new_total_score_clamped_100, new_total_premium_bonus,
                        new_total_commute_distance, commutes_info, used_item_ids)

                    current_combo.pop()
                    used_item_ids.remove(item_id)
                    commutes_info.pop()
                    continue

                next_pos = get_coords(selected_item)
                dist = calculate_distance(current_pos, next_pos)
                if commute_preference == "walking" and dist > 2.0:
                    prune_counts["prune_walk_leg_over_2km"] += 1
                    continue
                time_min, cost_val, mode = calculate_commute_info(
                    dist, commute_preference=commute_preference
                )

                # 通勤步骤(1个)和活动/餐饮步骤(1个)，分别在各自结束后加 5 分钟缓冲，共计 10 分钟
                new_total_duration = total_duration_minutes + duration_mins + int(math.ceil(time_min)) + 10
                
                # 剪枝判断，尽早退出
                if is_range:
                    if new_total_duration > hard_max_mins:
                        continue
                else:
                    if new_total_duration > target_duration_mins + 45:
                        continue
                    
                new_cost_with_gift = cost_with_gift + cost_val + price
                new_cost_without_gift = cost_without_gift + cost_val
                if step_type != "gift_shop":
                    new_cost_without_gift += price
                    
                if new_cost_without_gift > budget:
                    continue
                if new_cost_with_gift > budget * 1.2:
                    continue

                score_raw = float(score) if isinstance(score, (int, float)) else 0.0
                score_clamped = min(100.0, max(0.0, score_raw))

                new_total_score_raw = total_score_raw + score_raw
                new_total_score_clamped_100 = total_score_clamped_100 + score_clamped
                new_total_premium_bonus = total_premium_bonus + float(premium_bonus)
                new_total_commute_distance = total_commute_distance + dist
                
                current_combo.append(selected_item)
                used_item_ids.add(item_id)
                commutes_info.append({
                    "time": time_min,
                    "cost": round(cost_val, 2),
                    "mode": mode,
                    "distance": dist
                })
                
                dfs(step_idx + 1, current_combo, next_pos, new_cost_without_gift, new_cost_with_gift,
                    new_total_duration, new_total_score_raw, new_total_score_clamped_100, new_total_premium_bonus,
                    new_total_commute_distance, commutes_info, used_item_ids)
                    
                # 回溯
                current_combo.pop()
                used_item_ids.remove(item_id)
                commutes_info.pop()
                
        # 从起始点(0.0, 0.0) 开始 DFS
        dfs(0, [], (0.0, 0.0), 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0, [], set())
        
        if pattern_plans:
            # 不再限制 Top N，保留所有合法方案，以最大化后续去重/多样性选择的空间
            grouped_plans.append(pattern_plans)

        if log_stats:
            pattern_plans_count = len(pattern_plans) if pattern_plans else 0
            unique_sigs_count = 0
            if pattern_plans:
                sigs = set()
                for p in pattern_plans:
                    sig = tuple(
                        item.get("combo_id") or item.get("package_id") or item.get("gift_id", "unknown")
                        for item in p.get("combo", [])
                    )
                    sigs.add(sig)
                unique_sigs_count = len(sigs)

            for k, v in prune_counts.items():
                if dfs_global_prune_stats is not None:
                    dfs_global_prune_stats[k] = dfs_global_prune_stats.get(k, 0) + v

            pattern_id = pattern.get("id") or pattern.get("pattern_id")
            pattern_desc = pattern.get("desc")
            logger.info(
                f"phase=planner_dfs_stats | pattern_id={pattern_id} | desc={pattern_desc} | step_pool_sizes={step_pool_sizes} | leaf_valid={pattern_valid_leaf_count} | pattern_plans_count={pattern_plans_count} | unique_sigs_count={unique_sigs_count} | prune_counts={prune_counts}"
            )
        
    candidate_pool = []
    for p_plans in grouped_plans:
        candidate_pool.extend(p_plans)
        
    def get_combo_signature(plan: dict) -> tuple:
        return tuple(
            item.get("combo_id") or item.get("package_id") or item.get("gift_id", "unknown")
            for item in plan.get("combo", [])
        )
        
    unique_candidates = []
    seen_sigs = set()
    
    # 按照分数整体降序排序，保证高分方案优先
    candidate_pool.sort(key=lambda x: x["average_score"], reverse=True)
    
    for p in candidate_pool:
        sig = get_combo_signature(p)
        if sig not in seen_sigs:
            unique_candidates.append(p)
            seen_sigs.add(sig)

    unique_after_dedup = len(unique_candidates)

    if log_stats:
        logger.info(
            f"phase=planner_candidate_pool_stats | num_patterns_input={num_patterns_input} | num_patterns_used={num_patterns_used} | patterns_skipped={skipped_patterns_count} | pattern_skip_reason_counts={skipped_reason_counts} | valid_count_before_topk={valid_count_before_topk} | candidate_pool_size_before_dedup={len(candidate_pool)} | unique_after_dedup={unique_after_dedup} | unique_after_fill={len(unique_candidates)}"
        )

    return unique_candidates, valid_count_before_topk, missing_types
