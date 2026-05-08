from typing import Any
import copy

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.state import ClosedLoopState
from closedloop.contracts.itinerary import (
    ItineraryPlan,
    ItineraryPlanVariant,
    ItineraryStep,
    ItineraryItem,
)
from closedloop.graph.policies import parse_time_period, match_patterns
from closedloop.graph.nodes.planner_utils import generate_and_score_combinations

def planner_node(state: ClosedLoopState) -> ClosedLoopState:
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
    duration_hours = constraints.get("duration_hours")
    budget = constraints.get("budget")
    if budget is None or budget <= 0:
        budget = float('inf')
    
    # 默认如果没有时长，按 4.0 小时计算
    start_time, parsed_duration = parse_time_period(time_period)
    
    if not duration_hours:
        duration_hours = parsed_duration
        
    required_duration_mins = duration_hours * 60

    group_type = constraints.get("group_type", "family")
    child_ages = constraints.get("child_ages", [])

    # 2. 匹配 Pattern
    patterns = match_patterns(group_type, child_ages, start_time, duration_hours)
    logger.info(f"phase=planner_node | patterns_matched={len(patterns)}")

    # 3. 准备可消费的候选集队列（深拷贝以免影响原状态）
    queues = {
        "activity": candidates.get("ranked_packages", []),
        "gift_shop": candidates.get("ranked_gifts", []),
        "breakfast": candidates.get("ranked_breakfast_combos", []),
        "lunch": candidates.get("ranked_lunch_combos", []),
        "afternoon_tea": candidates.get("ranked_afternoon_tea_combos", []),
        "dinner": candidates.get("ranked_dinner_combos", []),
        "late_night": candidates.get("ranked_late_night_combos", []),
    }

    # 4 & 5. 时间线推演与条目组装，同时进行过滤与提取候选池 (生成多套方案)
    valid_plans_info, valid_count_before_topk, missing_types_set = generate_and_score_combinations(
        queues, patterns, budget, required_duration_mins
    )
    missing_types = list(missing_types_set)
    
    logger.info(f"phase=planner_node | valid_after_filter={valid_count_before_topk} | final_top_k={len(valid_plans_info)}")

    status = "ok" if valid_plans_info else "insufficient_candidates"
    plans = []
    
    if valid_plans_info:
        for plan_index, plan_info in enumerate(valid_plans_info, start=1):
            pattern = plan_info["pattern"]
            combo = plan_info["combo"]
            commutes = plan_info["commutes"]
            
            steps = []
            item_ids = []
            current_time = start_time
            
            step_counter = 1
            commute_counter = 1
            
            for i, selected_item in enumerate(combo):
                # 1. 先加入通勤节点 (前往当前地点)
                commute = commutes[i]
                if commute["time"] > 0:
                    commute_item = ItineraryItem(
                        id=f"commute_{plan_index}_{commute_counter}",
                        name=f"前往 {selected_item.get('name', '目的地')}",
                        type="commute",
                        location="途中",
                        distance_km=commute["distance"],
                        cost=commute["cost"]
                    )
                    steps.append(ItineraryStep(
                        order_id=f"C{commute_counter}",
                        item=commute_item,
                        duration_minutes=int(commute["time"]),
                        note=f"推荐方式: {commute['mode']}"
                    ))
                    commute_counter += 1
                    current_time += (commute["time"] / 60.0)
                
                # 2. 加入实际地点节点
                step_type = selected_item["_step_type"]
                meal_category = selected_item.get("_meal_category")
                
                # 确定时长和 Note
                note = ""
                if step_type == "activity":
                    duration_mins = selected_item.get("duration_mins", 90)
                elif step_type == "gift_shop":
                    duration_mins = 30
                elif step_type.startswith("restaurant:"):
                    duration_mins = selected_item.get("duration_mins", 60) if meal_category != "afternoon_tea" else selected_item.get("duration_mins", 45)
                else:
                    duration_mins = 60

                item_type = "restaurant" if "restaurant" in step_type else step_type
                item_id = selected_item.get("combo_id") or selected_item.get("package_id") or selected_item.get("gift_id", "unknown")
                name = selected_item.get("name", "Unknown")
                location_dict = selected_item.get("location", {})
                address = location_dict.get("address", "未知地址")
                distance = selected_item.get("distance_km", 0.0)
                price = selected_item.get("price", 0.0)

                it_item = ItineraryItem(
                    id=item_id,
                    name=name,
                    type=item_type,
                    location=address,
                    distance_km=distance,
                    cost=price
                )

                steps.append(ItineraryStep(
                    order_id=str(step_counter),
                    item=it_item,
                    duration_minutes=duration_mins,
                    note=note
                ))
                step_counter += 1
                item_ids.append(item_id)
                current_time += (duration_mins / 60.0)
                
            # 3. 加入最后返程回家的通勤节点
            final_commute = commutes[-1]
            if final_commute["time"] > 0:
                commute_item = ItineraryItem(
                    id=f"commute_{plan_index}_{commute_counter}",
                    name="返程回家",
                    type="commute",
                    location="途中",
                    distance_km=final_commute["distance"],
                    cost=final_commute["cost"]
                )
                steps.append(ItineraryStep(
                    order_id=f"C{commute_counter}",
                    item=commute_item,
                    duration_minutes=int(final_commute["time"]),
                    note=f"推荐方式: {final_commute['mode']}"
                ))
            
            plan_variant = ItineraryPlanVariant(
                plan_id=f"plan_{plan_index}",
                title=f"{pattern['desc']}行程方案 {plan_index}",
                steps=steps,
                selected_item_ids=item_ids,
                total_duration_minutes=plan_info["total_duration_minutes"],
                total_cost=plan_info["total_cost"],
                average_score=plan_info["average_score"]
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

    state["itinerary"] = itinerary_plan.model_dump()
    
    # 记录执行步骤
    processed_steps = state.setdefault("processed_steps", [])
    processed_steps.append("planner_node")
    
    logger.info(f"phase=planner_node | status={status} | generated_plans={len(plans)} | missing={missing_types}")

    return state
