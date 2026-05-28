from typing import Any
import copy
import math
import time

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.state import PlanState
from closedloop.contracts.itinerary import (
    ItineraryPlan,
    ItineraryPlanVariant,
    ItineraryStep,
    ItineraryItem,
)
from closedloop.graph.policies import parse_time_period, parse_target_start_time, match_patterns, get_time_of_day
from closedloop.graph.plan_subgraph.planner_utils import (
    generate_and_score_combinations,
    calculate_commute_options,
    calculate_commute_info_for_mode,
)


def _plan_signature(plan_info: dict, exclude_gifts: bool = False) -> str:
    combo = plan_info.get("combo", []) or []
    ids: list[str] = []
    for item in combo:
        if exclude_gifts and (item.get("gift_id") or item.get("_step_type") == "gift_shop"):
            continue
        item_id = item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id")
        if item_id:
            ids.append(str(item_id))
    return "|".join(ids)

def _get_letter_id(index: int) -> str:
    """将数字索引转换为字母 (如 1->A, 2->B, 27->AA)"""
    result = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result

def _is_sufficiently_different(new_plan: dict, past_plans: list[dict], threshold_ratio: float = 0.0) -> bool:
    """判断新方案与已有方案集合是否有足够差异（允许重合的比例 <= threshold_ratio）"""
    new_ids = set([x for x in _plan_signature(new_plan, exclude_gifts=True).split("|") if x])
    if not new_ids:
        return True
        
    for past_plan in past_plans:
        past_ids = set(past_plan.get("core_item_ids", []))
        if not past_ids:
            continue
            
        intersection = new_ids.intersection(past_ids)
        if len(intersection) > len(new_ids) * threshold_ratio:
            return False
            
    return True

def _select_top_k_diverse_plans(plan_infos: list[dict], top_k: int, past_itinerary: list[dict]) -> list[dict]:
    """
    根据分数排序并挑选出与历史行程有足够差异的 Top K 方案。
    使用梯度降级策略：默认要求 0% 重合 -> 25% 重合 -> 50% 重合 -> 无视重合度
    在计算重合度时，剔除礼品项目。
    """
    if not plan_infos:
        return []

    def safe_score(p: dict) -> float:
        v = p.get("average_score", 0.0)
        return float(v) if isinstance(v, (int, float)) else 0.0

    unique: list[dict] = []
    seen: set[str] = set()
    for p in plan_infos:
        sig = _plan_signature(p)
        if not sig or sig in seen:
            continue
        seen.add(sig)
        unique.append(p)

    unique.sort(key=safe_score, reverse=True)

    selected: list[dict] = []
    current_past = list(past_itinerary)
    
    # 历史方案也要预处理出 core_item_ids 供 _is_sufficiently_different 使用
    for pp in current_past:
        if "core_item_ids" not in pp:
            # 如果是传进来的旧历史，我们假设 selected_item_ids 都在里面，
            # 为了安全起见我们直接把原来的全拿过来。由于旧数据无法精确排除，所以尽量兼容。
            pp["core_item_ids"] = pp.get("selected_item_ids", [])
    
    thresholds = [0.0, 0.25, 0.50]
    
    for threshold in thresholds:
        if len(selected) >= top_k:
            break
            
        for p in unique:
            if len(selected) >= top_k:
                break
            
            # 如果该方案已经被选中过了，跳过
            if _plan_signature(p) in { _plan_signature(s) for s in selected }:
                continue
                
            if _is_sufficiently_different(p, current_past, threshold_ratio=threshold):
                selected.append(p)
                # 将当前选中的方案模拟为历史，提取剔除礼品后的 core_ids
                core_ids = [x for x in _plan_signature(p, exclude_gifts=True).split("|") if x]
                mock_past_plan = {
                    "selected_item_ids": _plan_signature(p).split("|"),
                    "core_item_ids": core_ids
                }
                current_past.append(mock_past_plan)

    # 兜底：如果跑完了 50% 的容忍度还是没凑够 top_k，直接按分数硬塞
    if len(selected) < top_k:
        used_sigs = { _plan_signature(p) for p in selected }
        for p in unique:
            if len(selected) >= top_k:
                break
            sig = _plan_signature(p)
            if sig not in used_sigs:
                selected.append(p)
                used_sigs.add(sig)

    return selected

def _float_hours_to_time_str(hours: float) -> str:
    h = int(hours) % 24
    m = int(round((hours - int(hours)) * 60))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    return f"{h:02d}:{m:02d}"

def _rewrite_commutes_for_taxi_preference(commutes: list[dict]) -> list[dict]:
    if not commutes:
        return []

    def safe_dist(c: dict) -> float:
        v = c.get("distance", 0.0)
        return float(v) if isinstance(v, (int, float)) else 0.0

    n = len(commutes)
    max_walk = 1 if n <= 3 else 2

    candidates = []
    for i, c in enumerate(commutes):
        dist = safe_dist(c)
        if dist > 2.0:
            continue
        if c.get("mode") is None:
            continue
        candidates.append((i, dist))
    candidates.sort(key=lambda x: x[1])
    walk_idxs = {i for i, _ in candidates[:max_walk]}

    rewritten: list[dict] = []
    for i, c in enumerate(commutes):
        dist = safe_dist(c)
        if c.get("mode") is None:
            rewritten.append({
                "time": 0.0,
                "cost": 0.0,
                "mode": None,
                "distance": dist,
            })
            continue
        mode = "walking" if (dist <= 2.0 and i in walk_idxs) else "taxi"
        time_min, cost, _ = calculate_commute_info_for_mode(dist, mode)
        rewritten.append({
            "time": time_min,
            "cost": float(round(cost, 2)),
            "mode": mode,
            "distance": dist,
        })

    return rewritten

def planner_node(state: PlanState) -> PlanState:
    """
    根据规则匹配 Pattern，从 rerank 后的候选集中挑选条目组装成最终行程计划。
    """
    config = get_config()
    LoggerManager.setup(config)
    started_at = time.perf_counter()

    logger.info("phase=planner_node | status=started")

    constraints = state.get("constraints", {})
    candidates = state.get("candidates", {})

    if not constraints or not candidates:
        logger.error("phase=planner_node | error=missing_prerequisites")
        state["itinerary"] = {
            "plans": [],
            "status": "insufficient_candidates",
            "missing_types": ["restaurant", "activity", "gift_shop"]
        }
        return state

    # 1. 提取时间与人群信息
    time_period = constraints.get("time_period", "")
    budget = constraints.get("budget")
    if budget is None or budget <= 0:
        budget = float('inf')
    
    start_time = parse_target_start_time(time_period)
    _, parsed_duration = parse_time_period(time_period)

    duration_hours = constraints.get("duration_hours")
    duration_hours_range: tuple[float, float] | None = None
    if isinstance(duration_hours, (list, tuple)) and len(duration_hours) == 2:
        a, b = duration_hours[0], duration_hours[1]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            lo, hi = float(a), float(b)
            if lo > hi:
                lo, hi = hi, lo
            duration_hours_range = (lo, hi)
    elif isinstance(duration_hours, (int, float)):
        v = float(duration_hours)
        duration_hours_range = (v, v)

    preferred_pattern_steps = constraints.get("preferred_pattern_steps")

    if duration_hours_range is None:
        if isinstance(time_period, str) and "-" in time_period:
            duration_hours_range = (float(parsed_duration), float(parsed_duration))
        else:
            # 如果未指定时长范围，如果是自定义较长序列，我们应该根据步骤数量放大默认的最大时间，防止因为默认的(4.0, 6.0)太短而排不下
            if preferred_pattern_steps and len(preferred_pattern_steps) >= 4:
                duration_hours_range = (4.0, 10.0)
            else:
                duration_hours_range = (4.0, 6.0)

    if isinstance(time_period, str) and "-" in time_period:
        window_h = float(parsed_duration)
        lo = min(duration_hours_range[0], window_h)
        hi = min(duration_hours_range[1], window_h)
        if lo > hi:
            lo = hi
        duration_hours_range = (lo, hi)

    required_duration_range_mins = (duration_hours_range[0] * 60.0, duration_hours_range[1] * 60.0)

    group_type = constraints.get("group_type", "family")
    child_profiles = constraints.get("child_profiles", [])
    commute_preference = constraints.get("commute_preference", "auto")
    commute_preference_for_dfs = "auto" if commute_preference == "taxi" else commute_preference
    include_gift = constraints.get("include_gift", True)

    # 2. 匹配 Pattern
    patterns = match_patterns(group_type, child_profiles, start_time, duration_hours_range)

    preferred_pattern_steps = constraints.get("preferred_pattern_steps")
    if preferred_pattern_steps:
        # 将 "restaurant" 归一化为具体的餐次，避免在 DFS 阶段找不到对应队列
        time_of_day = get_time_of_day(start_time)
        meal_map = {
            "morning": "breakfast",
            "noon": "lunch",
            "afternoon": "afternoon_tea",
            "evening": "dinner",
            "night": "late_night"
        }
        default_meal = meal_map.get(time_of_day, "dinner")
        
        normalized_steps = []
        for step in preferred_pattern_steps:
            if step == "restaurant":
                normalized_steps.append(f"restaurant:{default_meal}")
            else:
                normalized_steps.append(step)
        preferred_pattern_steps = normalized_steps
        constraints["preferred_pattern_steps"] = preferred_pattern_steps

        def is_subsequence(sub, full):
            it = iter(full)
            return all(x in it for x in sub)

        matching_patterns = [p for p in patterns if is_subsequence(preferred_pattern_steps, p.get("steps", []))]

        if matching_patterns:
            # 存在子集匹配的 pattern，将其排到最前面（优先短的，即包含额外步骤最少的）
            patterns.sort(key=lambda p: (not is_subsequence(preferred_pattern_steps, p.get("steps", [])), len(p.get("steps", []))))
            logger.info(f"phase=planner_node | patterns_matched={len(patterns)} (sorted by subset match)")
        else:
            # 没有任何 pattern 包含该子集，构造自定义 pattern
            custom_patterns = []
            base_desc = "用户自定义顺序"
            start_pref = [get_time_of_day(start_time)]

            # 无论如何先放入原始指定的 pattern
            custom_patterns.append({
                "id": "CUSTOM-00",
                "group": group_type,
                "duration_range": duration_hours_range,
                "steps": preferred_pattern_steps,
                "desc": base_desc,
                "start_time_pref": start_pref
            })

            # 如果允许礼品，则在每个步骤之后尝试插入 gift_shop
            if include_gift:
                for i in range(len(preferred_pattern_steps)):
                    new_steps = preferred_pattern_steps[:]
                    new_steps.insert(i + 1, "gift_shop")
                    custom_patterns.append({
                        "id": f"CUSTOM-GIFT-{i+1}",
                        "group": group_type,
                        "duration_range": duration_hours_range,
                        "steps": new_steps,
                        "desc": f"{base_desc}(含礼品)",
                        "start_time_pref": start_pref
                    })

            patterns = custom_patterns + patterns
            logger.info(f"phase=planner_node | patterns_matched={len(patterns)} (generated {len(custom_patterns)} custom patterns)")
    else:
        logger.info(f"phase=planner_node | patterns_matched={len(patterns)}")

    # 如果用户明确不需要 gift_shop，我们需要对匹配出来的 pattern 进行修改，剔除 gift_shop 步骤
    if not include_gift:
        new_patterns = []
        for p in patterns:
            p_copy = p.copy()
            p_copy["steps"] = [step for step in p["steps"] if step != "gift_shop"]
            new_patterns.append(p_copy)
        patterns = new_patterns

    # 3. 准备可消费的候选集队列（深拷贝以免影响原状态）
    queues = {
        "activity": candidates.get("ranked_packages", []),
        "activity_light": candidates.get("ranked_light_packages", []),
        "gift_shop": candidates.get("ranked_gifts", []),
        "breakfast": candidates.get("ranked_breakfast_combos", []),
        "lunch": candidates.get("ranked_lunch_combos", []),
        "afternoon_tea": candidates.get("ranked_afternoon_tea_combos", []),
        "dinner": candidates.get("ranked_dinner_combos", []),
        "late_night": candidates.get("ranked_late_night_combos", []),
    }

    # 4 & 5. 时间线推演与条目组装，同时进行过滤与提取候选池 (生成多套方案)
    
    # 用来记录 dfs 剪枝丢弃的各类原因（统计最后给 Agent 报错用）
    dfs_global_prune_stats = {
        "prune_budget_over": 0,
        "prune_partial_time_over": 0,
        "prune_walk_leg_over_2km": 0,
        "prune_walk_home_over_2km": 0,
        "prune_gift_delivery_radius": 0,
        "prune_final_duration_too_short": 0,
        "prune_final_duration_too_long": 0,
    }

    valid_plans_info, valid_count_before_topk, missing_types_set = generate_and_score_combinations(
        queues,
        patterns,
        budget,
        required_duration_range_mins,
        commute_preference=commute_preference_for_dfs,
        dfs_global_prune_stats=dfs_global_prune_stats,
    )
    missing_types = list(missing_types_set)
    
    logger.info(f"phase=planner_node | valid_after_filter={valid_count_before_topk} | final_top_k={len(valid_plans_info)}")

    status = "ok" if valid_plans_info else "insufficient_candidates"
    plans = []
    
    if valid_plans_info:
        if bool(getattr(config.logging, "LOG_PLANNER_STATS", False)):
            logger.info(f"phase=planner_node_stats | before_select_diverse={len(valid_plans_info)}")

        if commute_preference == "taxi":
            for p in valid_plans_info:
                commutes = p.get("commutes", [])
                rewritten = _rewrite_commutes_for_taxi_preference(commutes)
                p["commutes"] = rewritten
                combo = p.get("combo", []) or []
                items_cost = sum(float(i.get("price", 0.0) or 0.0) for i in combo)
                commutes_cost = sum(float(c.get("cost", 0.0) or 0.0) for c in rewritten)
                p["total_cost"] = float(round(items_cost + commutes_cost, 2))

        top_k = state.get("top_k", 1)
        past_itinerary = state.get("past_itinerary", [])
        
        valid_plans_info = _select_top_k_diverse_plans(valid_plans_info, top_k, past_itinerary)
        
        if bool(getattr(config.logging, "LOG_PLANNER_STATS", False)):
            logger.info(f"phase=planner_node_stats | after_select_diverse={len(valid_plans_info)}")
            
        start_index = len(past_itinerary) + 1
        
        for plan_index_offset, plan_info in enumerate(valid_plans_info, start=0):
            plan_index = start_index + plan_index_offset
            pattern = plan_info["pattern"]
            combo = plan_info["combo"]
            commutes = plan_info["commutes"]
            
            steps = []
            item_ids = []
            current_time = start_time
            
            step_counter = 1
            commute_counter = 1
            last_physical_name = "家"
            
            for i, selected_item in enumerate(combo):
                step_type = selected_item["_step_type"]
                meal_category = selected_item.get("_meal_category")
                place_name = selected_item.get("name", "目的地")
                is_activity_step = step_type in ("activity", "activity_light")
                if is_activity_step:
                    place_name = selected_item.get("venue_name") or place_name
                elif step_type.startswith("restaurant:"):
                    place_name = selected_item.get("restaurant_name") or place_name
                elif step_type == "gift_shop":
                    place_name = selected_item.get("shop_name") or place_name

                # 1. 先加入通勤节点 (前往当前地点)
                commute = commutes[i]
                if commute["time"] > 0:
                    dist = float(commute.get("distance", 0.0))
                    commute_from = last_physical_name
                    commute_to = place_name
                    commute_mode = commute.get("mode")
                    commute_item = ItineraryItem(
                        id=f"commute_{plan_index}_{commute_counter}",
                        name=f"前往 {place_name}",
                        display_name=f"{commute_from} -> {commute_to}",
                        sub_name=f"推荐方式：{ {'walking': '步行', 'taxi': '打车', 'driving': '自驾'}.get(commute_mode, '未知') }",
                        type="commute",
                        location="途中",
                        distance_km=dist,
                        cost=commute["cost"],
                        commute_from=commute_from,
                        commute_to=commute_to,
                        commute_mode=commute_mode,
                        commute_options=calculate_commute_options(
                            dist,
                            commute_preference="driving" if commute_preference == "driving" else "auto",
                        )
                    )
                    commute_dur_mins = int(math.ceil(float(commute["time"])))
                    start_str = _float_hours_to_time_str(current_time)
                    current_time += (commute_dur_mins / 60.0)
                    end_str = _float_hours_to_time_str(current_time)

                    steps.append(ItineraryStep(
                        order_id=f"C{commute_counter}",
                        item=commute_item,
                        duration_minutes=commute_dur_mins,
                        start_time=start_str,
                        end_time=end_str
                    ))
                    commute_counter += 1
                    # 每个步骤后加5分钟缓冲
                    current_time += (5.0 / 60.0)
                
                # 2. 加入实际地点节点
                # 确定时长
                if is_activity_step:
                    duration_mins = selected_item.get("duration_mins", 90)
                elif step_type == "gift_shop":
                    duration_mins = int(selected_item.get("receive_duration_mins") or 10)
                elif step_type.startswith("restaurant:"):
                    duration_mins = selected_item.get("duration_mins", 60) if meal_category != "afternoon_tea" else selected_item.get("duration_mins", 45)
                else:
                    duration_mins = 60

                if step_type.startswith("restaurant:"):
                    item_type = "restaurant"
                elif is_activity_step:
                    item_type = "activity"
                elif step_type == "gift_shop":
                    item_type = "gift_shop"
                else:
                    item_type = step_type
                item_id = selected_item.get("combo_id") or selected_item.get("package_id") or selected_item.get("gift_id", "unknown")
                name = selected_item.get("name", "Unknown")
                address = selected_item.get("address")
                if not isinstance(address, str) or not address:
                    location_dict = selected_item.get("location", {})
                    if isinstance(location_dict, dict):
                        address = location_dict.get("address", "未知地址")
                    else:
                        address = "未知地址"
                price = selected_item.get("price", 0.0)

                gift_price = None
                delivery_fee = None
                delivery_distance_km = None
                distance = selected_item.get("distance_km", 0.0)
                cost = price
                if item_type == "gift_shop":
                    gift_price = float(selected_item.get("gift_price", price) or 0.0)
                    delivery_fee = float(selected_item.get("delivery_fee", 0.0) or 0.0)
                    delivery_distance_km = float(selected_item.get("delivery_distance_km", 0.0) or 0.0)
                    distance = delivery_distance_km
                    cost = float(round(gift_price + delivery_fee, 2))

                parent_name = selected_item.get("shop_name") if item_type == "gift_shop" else place_name
                display_name = parent_name or name
                sub_name = name if name != display_name else None

                it_item = ItineraryItem(
                    id=item_id,
                    name=name,
                    parent_name=parent_name,
                    display_name=display_name,
                    sub_name=sub_name,
                    type=item_type,
                    location=address,
                    distance_km=distance,
                    cost=cost,
                    gift_price=gift_price,
                    delivery_fee=delivery_fee,
                    delivery_distance_km=delivery_distance_km,
                    intro=selected_item.get("description"),
                    features=selected_item.get("features"),
                )

                start_str = _float_hours_to_time_str(current_time)
                current_time += (duration_mins / 60.0)
                end_str = _float_hours_to_time_str(current_time)

                steps.append(ItineraryStep(
                    order_id=str(step_counter),
                    item=it_item,
                    duration_minutes=duration_mins,
                    start_time=start_str,
                    end_time=end_str
                ))
                step_counter += 1
                item_ids.append(item_id)
                # 每个步骤后加5分钟缓冲（如果是最后一个且没有回家通勤，就不该加？下面会处理最后一部通勤）
                # 这里统加，不管它是不是最后一个步骤，总耗时计算时我们减去最后一个缓冲或者在外部控制
                current_time += (5.0 / 60.0)

                if item_type != "gift_shop":
                    last_physical_name = display_name
                
            # 3. 加入最后返程回家的通勤节点
            final_commute = commutes[-1]
            if final_commute["time"] > 0:
                dist = float(final_commute.get("distance", 0.0))
                commute_from = last_physical_name
                commute_to = "家"
                commute_mode = final_commute.get("mode")
                commute_item = ItineraryItem(
                    id=f"commute_{plan_index}_{commute_counter}",
                    name="返程回家",
                    display_name=f"{commute_from} -> {commute_to}",
                    sub_name=f"推荐方式：{ {'walking': '步行', 'taxi': '打车', 'driving': '自驾'}.get(commute_mode, '未知') }",
                    type="commute",
                    location="途中",
                    distance_km=dist,
                    cost=final_commute["cost"],
                    commute_from=commute_from,
                    commute_to=commute_to,
                    commute_mode=commute_mode,
                    commute_options=calculate_commute_options(
                        dist,
                        commute_preference="driving" if commute_preference == "driving" else "auto",
                    )
                )
                commute_dur_mins = int(math.ceil(float(final_commute["time"])))
                start_str = _float_hours_to_time_str(current_time)
                current_time += (commute_dur_mins / 60.0)
                end_str = _float_hours_to_time_str(current_time)

                steps.append(ItineraryStep(
                    order_id=f"C{commute_counter}",
                    item=commute_item,
                    duration_minutes=commute_dur_mins,
                    start_time=start_str,
                    end_time=end_str
                ))
            
            # 根据契约：独立缓冲在计算总耗时和时序时生效，不加入具体step中。每个步骤后加5分钟，除了最后一步。
            num_buffers = max(0, len(steps) - 1)
            total_duration_minutes = sum(int(s.duration_minutes) for s in steps) + 5 * num_buffers
            total_cost = sum(float(s.item.cost or 0.0) for s in steps)

            plan_variant = ItineraryPlanVariant(
                plan_id=f"plan_{_get_letter_id(plan_index)}",
                title=f"{pattern['desc']}行程方案 {_get_letter_id(plan_index)}",
                steps=steps,
                selected_item_ids=item_ids,
                total_duration_minutes=total_duration_minutes,
                total_cost=float(round(total_cost, 2)),
                average_score=plan_info.get("average_score", 0.0),
                experience_score=plan_info.get("experience_score", plan_info.get("average_score", 0.0)),
            )
            plans.append(plan_variant)

    if not plans:
        logger.warning("phase=planner_node | warning=all_plans_filtered_out_by_budget_or_time")
        error_msg = "规划失败：符合条件的方案组合为 0。\n\n"
        
        # 初步过滤统计报告 (从 filter_node 传递过来)
        filter_stats = candidates.get("filter_stats", {})
        if filter_stats:
            error_msg += "【初步过滤阶段】\n"
            global_reason_counts = {}
            for cat, stats in filter_stats.items():
                before_count = stats.get("before_count", 0)
                after_count = stats.get("after_count", 0)
                dropped = stats.get("dropped_count", 0)
                sub_dropped = stats.get("dropped_sub_item_count", 0)
                
                cat_name = "餐厅" if "restaurants" in cat else "活动" if "activities" in cat else "礼品" if "gifts" in cat else cat
                if before_count > 0:
                    error_msg += f"- {cat_name}: 初始 {before_count} 家，过滤后剩余 {after_count} 家 (剔除了 {dropped} 家店，{sub_dropped} 个单品套餐)\n"
                
                for rc, count in stats.get("reason_counts", {}).items():
                    global_reason_counts[rc] = global_reason_counts.get(rc, 0) + count

            if global_reason_counts:
                reason_translations = {
                    "sub_item_price_too_high": "单品价格超出预算",
                    "sub_item_capacity_mismatch": "容纳人数不匹配",
                    "all_sub_items_filtered": "子项(套餐)全部被过滤",
                    "distance_over_max": "超出偏好距离",
                    "outside_open_hours": "营业时间不匹配",
                    "suitable_groups_missing_or_empty": "缺少适合群体标签",
                    "suitable_groups_mismatch": "群体类型不匹配",
                    "activity_age_range_missing_or_empty": "缺少儿童年龄标签",
                    "activity_age_range_mismatch": "儿童年龄不匹配",
                    "family_forbidden_terms": "包含亲子不宜内容",
                    "dietary_restriction_hit": "触碰饮食禁忌",
                    "family_avoid_infant": "婴儿不宜",
                }
                
                error_msg += "  过滤主要原因分布：\n"
                sorted_reasons = sorted(global_reason_counts.items(), key=lambda x: x[1], reverse=True)
                for rc, count in sorted_reasons:
                    if count > 0:
                        desc = reason_translations.get(rc, rc)
                        error_msg += f"  * {count} 次因为 [{desc}]\n"
                        
            error_msg += "\n"

        # 尝试分析失败原因并生成统计报告
        total_pruned = sum(dfs_global_prune_stats.values())
        if total_pruned > 0:
            error_msg += f"【深度组合阶段】\n系统共尝试了 {total_pruned} 种潜在组合，均因不满足约束被过滤，具体原因分布如下：\n"
            
            budget_pruned = dfs_global_prune_stats.get("prune_budget_over", 0)
            time_long_pruned = dfs_global_prune_stats.get("prune_partial_time_over", 0) + dfs_global_prune_stats.get("prune_final_duration_too_long", 0)
            time_short_pruned = dfs_global_prune_stats.get("prune_final_duration_too_short", 0)
            dist_pruned = dfs_global_prune_stats.get("prune_walk_leg_over_2km", 0) + dfs_global_prune_stats.get("prune_walk_home_over_2km", 0)
            gift_pruned = dfs_global_prune_stats.get("prune_gift_delivery_radius", 0)
            
            reasons = [
                (budget_pruned, "因为超出预算限制"),
                (time_long_pruned, "因为行程耗时过长(超出预期上限)"),
                (time_short_pruned, "因为行程耗时过短(达不到预期下限)"),
                (dist_pruned, "因为步行距离超限(>2km)"),
                (gift_pruned, "因为礼品配送距离超限")
            ]
            
            # 过滤掉为 0 的项，并按占比(即数量)降序排序
            reasons = sorted([(count, msg) for count, msg in reasons if count > 0], key=lambda x: x[0], reverse=True)
            
            for count, msg in reasons:
                error_msg += f"- {count/total_pruned*100:.1f}% {msg}\n"
        elif missing_types:
            error_msg += f"原因：缺乏对应的组件库存或该类型无法匹配当前条件：{', '.join(missing_types)}\n"

        state["itinerary"] = {
            "status": "failed",
            "plans": [],
            "error": error_msg,
            "missing_types": list(missing_types)
        }
        
        processed_steps = state.setdefault("processed_steps", [])
        processed_steps.append("planner_node")
        
        logger.info(
            f"phase=planner_node | status=failed | missing={missing_types} | elapsed_ms={int((time.perf_counter() - started_at) * 1000)}"
        )
        return state

    itinerary_plan = ItineraryPlan(
        plans=plans,
        status=status,
        missing_types=list(missing_types)
    )

    state["itinerary"] = itinerary_plan.model_dump(exclude_none=True)
    
    # 记录执行步骤
    processed_steps = state.setdefault("processed_steps", [])
    processed_steps.append("planner_node")
    
    logger.info(
        f"phase=planner_node | status={status} | generated_plans={len(plans)} | missing={missing_types} | elapsed_ms={int((time.perf_counter() - started_at) * 1000)}"
    )

    return state
