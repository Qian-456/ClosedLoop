from typing import Any
import copy
import math

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.state import PlanState
from closedloop.contracts.itinerary import (
    ItineraryPlan,
    ItineraryPlanVariant,
    ItineraryStep,
    ItineraryItem,
)
from closedloop.graph.policies import parse_time_period, parse_target_start_time, match_patterns
from closedloop.graph.plan_subgraph.planner_utils import (
    generate_and_score_combinations,
    calculate_commute_options,
    calculate_commute_info_for_mode,
)


def _plan_signature(plan_info: dict) -> str:
    combo = plan_info.get("combo", []) or []
    ids: list[str] = []
    for item in combo:
        item_id = item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id")
        if item_id:
            ids.append(str(item_id))
    return "|".join(ids)


def _select_three_plans(plan_infos: list[dict]) -> list[dict]:
    """
    将候选方案整理为 3 套可比较方案（展示层语义）：
    - plan_1：价格最低
    - plan_2：比 plan_1 贵一些，但体验分明显更高（主推升级款）
    - plan_3：比 plan_2 贵很多，但体验分只高一点点（豪华款/锚点）
    若无法形成上述 decoy 结构，则按回退规则补齐。
    """
    if not plan_infos:
        return []

    def safe_cost(p: dict) -> float:
        v = p.get("total_cost")
        return float(v) if isinstance(v, (int, float)) else float("inf")

    def safe_experience(p: dict) -> float:
        v = p.get("experience_score", p.get("average_score"))
        return float(v) if isinstance(v, (int, float)) else float("-inf")

    unique: list[dict] = []
    seen: set[str] = set()
    for p in plan_infos:
        sig = _plan_signature(p)
        if not sig or sig in seen:
            continue
        seen.add(sig)
        unique.append(p)
    if not unique:
        return []

    sorted_by_cost = sorted(unique, key=safe_cost)
    if len(sorted_by_cost) <= 3:
        return sorted_by_cost

    cheapest = sorted_by_cost[0]
    cheapest_sig = _plan_signature(cheapest)
    cheapest_cost = safe_cost(cheapest)
    cheapest_exp = safe_experience(cheapest)

    most_expensive: dict | None = None
    for c in reversed(sorted_by_cost):
        sig = _plan_signature(c)
        if sig == cheapest_sig:
            continue
        most_expensive = c
        break
    if not most_expensive:
        return [cheapest]

    most_expensive_sig = _plan_signature(most_expensive)
    most_expensive_cost = safe_cost(most_expensive)

    def pick_plan2(max_multiplier: float) -> dict | None:
        lo = cheapest_cost * 1.10
        hi = cheapest_cost * max_multiplier
        best: dict | None = None
        best_key: tuple[float, float, float] | None = None
        for c in sorted_by_cost:
            sig = _plan_signature(c)
            if sig == cheapest_sig or sig == most_expensive_sig:
                continue
            cost = safe_cost(c)
            if not (lo <= cost <= hi) or not (cost < most_expensive_cost):
                continue
            exp = safe_experience(c)
            key = (exp - cheapest_exp, exp, -cost)
            if best_key is None or key > best_key:
                best_key = key
                best = c
        return best

    plan2: dict | None = None
    for mult in (1.40, 1.60, 1.80, 2.00):
        plan2 = pick_plan2(mult)
        if plan2:
            break

    if not plan2:
        best: dict | None = None
        best_key: tuple[float, float] | None = None
        for c in sorted_by_cost:
            sig = _plan_signature(c)
            if sig == cheapest_sig or sig == most_expensive_sig:
                continue
            cost = safe_cost(c)
            if not (cheapest_cost < cost < most_expensive_cost):
                continue
            exp = safe_experience(c)
            key = (exp, -cost)
            if best_key is None or key > best_key:
                best_key = key
                best = c
        plan2 = best

    if not plan2:
        return [cheapest, most_expensive]

    plan2_sig = _plan_signature(plan2)
    plan2_cost = safe_cost(plan2)
    plan2_exp = safe_experience(plan2)

    plan3: dict | None = None
    best_cost = float("-inf")
    for c in reversed(sorted_by_cost):
        sig = _plan_signature(c)
        if sig in {cheapest_sig, most_expensive_sig, plan2_sig}:
            continue
        cost = safe_cost(c)
        if cost <= plan2_cost:
            continue
        exp = safe_experience(c)
        if cost < plan2_cost * 1.40 or cost > plan2_cost * 2.20:
            continue
        if exp < plan2_exp or exp > plan2_exp + 8.0:
            continue
        if cost > best_cost:
            best_cost = cost
            plan3 = c

    if not plan3:
        plan3 = most_expensive

    if safe_cost(plan3) <= plan2_cost:
        plan3 = most_expensive

    if safe_cost(plan3) <= plan2_cost:
        best: dict | None = None
        best_key: tuple[float, float] | None = None
        for c in sorted_by_cost:
            sig = _plan_signature(c)
            if sig == cheapest_sig or sig == most_expensive_sig:
                continue
            cost = safe_cost(c)
            if not (cheapest_cost < cost < most_expensive_cost):
                continue
            exp = safe_experience(c)
            key = (exp, -cost)
            if best_key is None or key > best_key:
                best_key = key
                best = c
        if best:
            plan2 = best
            plan2_sig = _plan_signature(plan2)
            plan2_cost = safe_cost(plan2)

    selected = [cheapest, plan2, plan3]
    used = set()
    deduped: list[dict] = []
    for c in selected:
        sig = _plan_signature(c)
        if sig in used:
            continue
        used.add(sig)
        deduped.append(c)

    if len(deduped) < 3:
        for c in sorted_by_cost:
            if len(deduped) >= 3:
                break
            sig = _plan_signature(c)
            if sig in used:
                continue
            used.add(sig)
            deduped.append(c)

    return deduped[:3]

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

    if duration_hours_range is None:
        if isinstance(time_period, str) and "-" in time_period:
            duration_hours_range = (float(parsed_duration), float(parsed_duration))
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

    # 2. 匹配 Pattern
    patterns = match_patterns(group_type, child_profiles, start_time, duration_hours_range)
    logger.info(f"phase=planner_node | patterns_matched={len(patterns)}")

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
    valid_plans_info, valid_count_before_topk, missing_types_set = generate_and_score_combinations(
        queues,
        patterns,
        budget,
        required_duration_range_mins,
        commute_preference=commute_preference_for_dfs,
    )
    missing_types = list(missing_types_set)
    
    logger.info(f"phase=planner_node | valid_after_filter={valid_count_before_topk} | final_top_k={len(valid_plans_info)}")

    status = "ok" if valid_plans_info else "insufficient_candidates"
    plans = []
    
    if valid_plans_info:
        if bool(getattr(config.logging, "LOG_PLANNER_STATS", False)):
            logger.info(f"phase=planner_node_stats | before_select_three={len(valid_plans_info)}")

        if commute_preference == "taxi":
            for p in valid_plans_info:
                commutes = p.get("commutes", [])
                rewritten = _rewrite_commutes_for_taxi_preference(commutes)
                p["commutes"] = rewritten
                combo = p.get("combo", []) or []
                items_cost = sum(float(i.get("price", 0.0) or 0.0) for i in combo)
                commutes_cost = sum(float(c.get("cost", 0.0) or 0.0) for c in rewritten)
                p["total_cost"] = float(round(items_cost + commutes_cost, 2))

        valid_plans_info = _select_three_plans(valid_plans_info)
        if bool(getattr(config.logging, "LOG_PLANNER_STATS", False)):
            logger.info(f"phase=planner_node_stats | after_select_three={len(valid_plans_info)}")
        for plan_index, plan_info in enumerate(valid_plans_info, start=1):
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
                    steps.append(ItineraryStep(
                        order_id=f"C{commute_counter}",
                        item=commute_item,
                        duration_minutes=int(math.ceil(float(commute["time"])))
                    ))
                    commute_counter += 1
                    current_time += (commute["time"] / 60.0)
                
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

                steps.append(ItineraryStep(
                    order_id=str(step_counter),
                    item=it_item,
                    duration_minutes=duration_mins
                ))
                step_counter += 1
                item_ids.append(item_id)
                current_time += (duration_mins / 60.0)

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
                steps.append(ItineraryStep(
                    order_id=f"C{commute_counter}",
                    item=commute_item,
                    duration_minutes=int(math.ceil(float(final_commute["time"])))
                ))
            
            total_duration_minutes = sum(int(s.duration_minutes) for s in steps)
            total_cost = sum(float(s.item.cost or 0.0) for s in steps)

            plan_variant = ItineraryPlanVariant(
                plan_id=f"plan_{plan_index}",
                title=f"{pattern['desc']}行程方案 {plan_index}",
                steps=steps,
                selected_item_ids=item_ids,
                total_duration_minutes=total_duration_minutes,
                total_cost=float(round(total_cost, 2)),
                average_score=plan_info.get("average_score", 0.0),
                experience_score=plan_info.get("experience_score", plan_info.get("average_score", 0.0)),
            )
            plans.append(plan_variant)

    if not plans and not missing_types:
        # 如果生成了组合但是全被过滤掉了，修改状态为 insufficient_candidates 避免报错
        logger.warning("phase=planner_node | warning=all_plans_filtered_out_by_budget_or_time")

    itinerary_plan = ItineraryPlan(
        plans=plans,
        status=status,
        missing_types=list(missing_types)
    )

    state["itinerary"] = itinerary_plan.model_dump(exclude_none=True)
    
    # 记录执行步骤
    processed_steps = state.setdefault("processed_steps", [])
    processed_steps.append("planner_node")
    
    logger.info(f"phase=planner_node | status={status} | generated_plans={len(plans)} | missing={missing_types}")

    return state
