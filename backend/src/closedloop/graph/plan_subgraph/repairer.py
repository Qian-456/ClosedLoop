import math
from typing import Any, Dict, List, Tuple
from copy import deepcopy

from closedloop.contracts.itinerary import ItineraryPlanVariant, ItineraryItem, ItineraryStep
from closedloop.graph.plan_subgraph.planner_utils import (
    calculate_distance,
    calculate_commute_info,
    calculate_commute_options,
    calculate_delivery_fee
)
from closedloop.core.logger import logger

def get_coords_from_item(item_data: dict) -> tuple[float, float]:
    """提取经纬度作为 (x, y) 坐标，单位 km"""
    x = item_data.get("longitude")
    y = item_data.get("latitude")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return (float(x), float(y))

    loc = item_data.get("location", {})
    if isinstance(loc, dict):
        x2 = loc.get("longitude", 0.0)
        y2 = loc.get("latitude", 0.0)
        return (float(x2 or 0.0), float(y2 or 0.0))

    return (0.0, 0.0)

def _build_itinerary_item(raw_item: dict, step_type: str) -> ItineraryItem:
    item_type = raw_item.get("type", step_type)
    if step_type.startswith("restaurant:"):
        item_type = "restaurant"
    elif step_type in ("activity", "activity_light"):
        item_type = "activity"
        
    item_id = str(raw_item.get("combo_id") or raw_item.get("package_id") or raw_item.get("gift_id") or raw_item.get("id"))
    name = raw_item.get("name", "Unknown")
    
    address = raw_item.get("address")
    if not isinstance(address, str) or not address:
        loc = raw_item.get("location", {})
        address = loc.get("address", "未知地址") if isinstance(loc, dict) else "未知地址"
        
    price = float(raw_item.get("price", 0.0))
    distance = float(raw_item.get("distance_km", 0.0))
    
    gift_price = None
    delivery_fee = None
    delivery_distance_km = None
    cost = price
    
    parent_name = None
    if item_type == "gift_shop":
        parent_name = raw_item.get("shop_name")
        gift_price = price
        # Default delivery logic
        delivery_distance_km = distance
        delivery_fee = calculate_delivery_fee(delivery_distance_km)
        cost = float(round(gift_price + delivery_fee, 2))
    elif item_type == "restaurant":
        parent_name = raw_item.get("restaurant_name")
    elif item_type == "activity":
        parent_name = raw_item.get("venue_name")
        
    display_name = parent_name or name
    sub_name = name if name != display_name else None
    
    return ItineraryItem(
        id=item_id,
        name=name,
        type=item_type,
        location=address,
        distance_km=distance,
        cost=cost,
        gift_price=gift_price,
        delivery_fee=delivery_fee,
        delivery_distance_km=delivery_distance_km,
        parent_name=parent_name,
        display_name=display_name,
        sub_name=sub_name,
        intro=raw_item.get("description"),
        features=raw_item.get("features"),
        user_touched=True,
        replacement_policy="strict"
    )

def _float_hours_to_time_str(hours: float) -> str:
    h = int(hours) % 24
    m = int(round((hours - int(hours)) * 60))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    return f"{h:02d}:{m:02d}"

def repair_plan(
    plan: dict,
    target_item_id: str,
    new_item: dict,
    budget: float,
    duration_range_mins: tuple[float, float],
    candidates: dict,
    commute_preference: str = "auto"
) -> dict:
    """
    5级冲突修复策略
    """
    logger.info(f"phase=repairer | plan_id={plan.get('plan_id')} | target={target_item_id} | new_item={new_item.get('name')}")
    
    # 1. 提取出原方案的物理节点（剔除通勤）
    original_steps = plan.get("steps", [])
    physical_items = []
    
    target_index = -1
    for idx, step in enumerate(original_steps):
        if step.get("item", {}).get("type") == "commute":
            continue
        item_dict = step.get("item", {})
        dur = step.get("duration_minutes", 60)
        
        # We need raw item data to know duration_std_dev etc.
        # Since we don't have it in ItineraryItem, we search in candidates.
        item_id = item_dict.get("id")
        raw_data = None
        for k in ["ranked_breakfast_combos", "ranked_lunch_combos", "ranked_afternoon_tea_combos", "ranked_dinner_combos", "ranked_late_night_combos", "ranked_packages", "ranked_light_packages", "ranked_gifts"]:
            for cand in candidates.get(k, []):
                cand_id = str(cand.get("combo_id") or cand.get("package_id") or cand.get("gift_id") or cand.get("id"))
                if cand_id == item_id:
                    raw_data = cand
                    break
            if raw_data: break
            
        if not raw_data:
            # Fallback
            raw_data = {
                "id": item_id,
                "name": item_dict.get("name"),
                "price": item_dict.get("cost"),
                "duration_mins": dur,
                "duration_std_dev": 10.0,
                "type": item_dict.get("type")
            }
            
        physical_items.append({
            "raw": raw_data,
            "it_item": item_dict,
            "duration": dur,
            "is_locked": False
        })
        
        if item_id == target_item_id:
            target_index = len(physical_items) - 1

    if target_index == -1:
        return {"status": "need_user_choice", "report": {"reason": f"在方案中找不到要替换的条目: {target_item_id}"}}

    # 2. 替换目标条目
    new_item_type = new_item.get("type")
    if not new_item_type:
        if "gift_id" in new_item:
            new_item_type = "gift_shop"
        elif "combo_id" in new_item:
            new_item_type = "restaurant"
        elif "package_id" in new_item:
            new_item_type = "activity"
        else:
            new_item_type = "activity"
            
    new_it_item = _build_itinerary_item(new_item, new_item_type)
    new_dur = int(new_item.get("duration_mins") or new_item.get("receive_duration_mins") or 60)
    
    physical_items[target_index] = {
        "raw": new_item,
        "it_item": new_it_item.model_dump() if hasattr(new_it_item, "model_dump") else new_it_item,
        "duration": new_dur,
        "is_locked": True # 用户替换的新条目被锁定
    }
    
    locked_items = [new_item.get("name")]

    def _calc_plan_metrics(items: list, start_time_str: str = "10:00") -> tuple[float, int, list]:
        """计算当前组合的总花费、总时长、重新生成的完整 steps"""
        total_cost = 0.0
        total_dur = 0
        new_steps = []
        
        current_pos = (0.0, 0.0)
        last_name = "家"
        step_counter = 1
        commute_counter = 1
        
        # Parse start_time_str to float
        h, m = map(int, start_time_str.split(":"))
        current_time = h + m / 60.0
        
        for item_obj in items:
            raw = item_obj["raw"]
            it = item_obj["it_item"]
            dur = item_obj["duration"]
            
            # 针对 gift_shop，需要重新计算配送距离和费用
            item_type = raw.get("type", it.get("type"))
            if item_type == "gift_shop":
                gift_pos = get_coords_from_item(raw)
                delivery_dist = calculate_distance(current_pos, gift_pos)
                fee = calculate_delivery_fee(delivery_dist)
                price = float(raw.get("price", 0.0))
                if isinstance(it, dict):
                    it["delivery_distance_km"] = float(round(delivery_dist, 2))
                    it["delivery_fee"] = fee
                    it["cost"] = float(round(price + fee, 2))
                else:
                    it.delivery_distance_km = float(round(delivery_dist, 2))
                    it.delivery_fee = fee
                    it.cost = float(round(price + fee, 2))
            else:
                next_pos = get_coords_from_item(raw)
                dist = calculate_distance(current_pos, next_pos)
                time_min, cost_val, mode = calculate_commute_info(dist, commute_preference=commute_preference)
                
                if time_min > 0:
                    place_name = it.get("display_name", it.get("name")) if isinstance(it, dict) else (it.display_name or it.name)
                    c_item = ItineraryItem(
                        id=f"commute_repair_{commute_counter}",
                        name=f"前往 {place_name}",
                        display_name=f"{last_name} -> {place_name}",
                        sub_name=f"推荐方式：{ {'walking': '步行', 'taxi': '打车', 'driving': '自驾'}.get(mode, '未知') }",
                        type="commute",
                        location="途中",
                        distance_km=dist,
                        cost=cost_val,
                        commute_from=last_name,
                        commute_to=place_name,
                        commute_mode=mode,
                        commute_options=calculate_commute_options(dist, commute_preference="driving" if commute_preference == "driving" else "auto")
                    )
                    commute_dur_mins = int(math.ceil(time_min))
                    start_str = _float_hours_to_time_str(current_time)
                    current_time += (commute_dur_mins / 60.0)
                    end_str = _float_hours_to_time_str(current_time)
                    
                    new_steps.append(ItineraryStep(
                        order_id=f"C{commute_counter}",
                        item=c_item,
                        duration_minutes=commute_dur_mins,
                        start_time=start_str,
                        end_time=end_str
                    ).model_dump())
                    total_cost += cost_val
                    total_dur += commute_dur_mins
                    commute_counter += 1
                    current_time += (5.0 / 60.0)
                
                current_pos = next_pos
                last_name = it.get("display_name", it.get("name")) if isinstance(it, dict) else (it.display_name or it.name)

            start_str = _float_hours_to_time_str(current_time)
            current_time += (dur / 60.0)
            end_str = _float_hours_to_time_str(current_time)

            new_steps.append(ItineraryStep(
                order_id=str(step_counter),
                item=it,
                duration_minutes=dur,
                start_time=start_str,
                end_time=end_str
            ).model_dump())
            
            cost = float(it.get("cost", 0.0) if isinstance(it, dict) else it.cost)
            total_cost += cost
            total_dur += dur
            step_counter += 1
            current_time += (5.0 / 60.0)
            
        # 返程
        dist_home = calculate_distance(current_pos, (0.0, 0.0))
        time_home, cost_home, mode_home = calculate_commute_info(dist_home, commute_preference=commute_preference)
        
        if time_home > 0:
            c_item = ItineraryItem(
                id=f"commute_repair_{commute_counter}",
                name="返程回家",
                display_name=f"{last_name} -> 家",
                sub_name=f"推荐方式：{ {'walking': '步行', 'taxi': '打车', 'driving': '自驾'}.get(mode_home, '未知') }",
                type="commute",
                location="途中",
                distance_km=dist_home,
                cost=cost_home,
                commute_from=last_name,
                commute_to="家",
                commute_mode=mode_home,
                commute_options=calculate_commute_options(dist_home, commute_preference="driving" if commute_preference == "driving" else "auto")
            )
            commute_dur_mins = int(math.ceil(time_home))
            start_str = _float_hours_to_time_str(current_time)
            current_time += (commute_dur_mins / 60.0)
            end_str = _float_hours_to_time_str(current_time)
            
            new_steps.append(ItineraryStep(
                order_id=f"C{commute_counter}",
                item=c_item,
                duration_minutes=commute_dur_mins,
                start_time=start_str,
                end_time=end_str
            ).model_dump())
            total_cost += cost_home
            total_dur += commute_dur_mins
            
        # 根据契约，每个步骤之后增加5分钟缓冲（不包含在具体步骤时长中，但计入总时长）
        num_buffers = max(0, len(new_steps) - 1)
        total_dur += 5 * num_buffers
            
        return round(total_cost, 2), total_dur, new_steps

    failed_repairs = []
    
    # Extract original start time
    original_start_time = "10:00"
    if original_steps and original_steps[0].get("start_time"):
        original_start_time = original_steps[0].get("start_time")
    
    # Base Evaluation
    cost, dur, steps = _calc_plan_metrics(physical_items, original_start_time)
    max_dur = duration_range_mins[1] + 45.0 # 加上一定的宽容度
    
    if cost <= budget * 1.2 and dur <= max_dur:
        # No conflict
        updated_plan = deepcopy(plan)
        updated_plan["steps"] = steps
        updated_plan["total_duration_minutes"] = dur
        updated_plan["total_cost"] = cost
        updated_plan["selected_item_ids"] = [it["it_item"].get("id") if isinstance(it["it_item"], dict) else it["it_item"].id for it in physical_items]
        return {"status": "success", "plan": updated_plan}

    # Level 1 & 2: 吃 buffer + 压缩可压缩项目
    if dur > max_dur:
        logger.info(f"phase=repairer | level=1_and_2 | dur={dur} > max={max_dur}")
        for item_obj in physical_items:
            if item_obj["is_locked"]:
                continue
            
            raw = item_obj["raw"]
            std_dev = float(raw.get("duration_std_dev") or raw.get("receive_duration_std_dev") or 0.0)
            
            # 吃 buffer
            if std_dev > 0:
                shrink = min(dur - max_dur, std_dev)
                if shrink > 0:
                    item_obj["duration"] -= int(shrink)
                    dur -= int(shrink)
            
            if dur <= max_dur:
                break
                
            # 压缩
            item_type = raw.get("type", "activity")
            if item_type in ("activity", "gift_shop"): # 正餐通常不压缩
                min_dur = int(raw.get("duration_mins", 60) * 0.6) # 极限压缩到60%
                current_dur = item_obj["duration"]
                if current_dur > min_dur:
                    shrink = min(dur - max_dur, current_dur - min_dur)
                    if shrink > 0:
                        item_obj["duration"] -= int(shrink)
                        dur -= int(shrink)
                        
            if dur <= max_dur:
                break
                
        cost, dur, steps = _calc_plan_metrics(physical_items)
        if cost <= budget * 1.2 and dur <= max_dur:
            updated_plan = deepcopy(plan)
            updated_plan["steps"] = steps
            updated_plan["total_duration_minutes"] = dur
            updated_plan["total_cost"] = cost
            updated_plan["selected_item_ids"] = [it["it_item"].get("id") if isinstance(it["it_item"], dict) else it["it_item"].id for it in physical_items]
            return {"status": "success", "plan": updated_plan}
        else:
            failed_repairs.append(f"已尝试压缩时间，但仍超出限制 (耗时: {dur}分钟)")

    # Level 3: 替换可替换项目 (为简化，MVP只做 Level 1/2/4/5)
    # TODO: Implement Level 3

    # Level 4: 删除低优先级组件
    if dur > max_dur or cost > budget * 1.2:
        logger.info(f"phase=repairer | level=4 | dur={dur}, cost={cost}")
        # 优先级：gift_shop -> afternoon_tea -> activity
        priority_to_delete = ["gift_shop", "afternoon_tea", "activity"]
        
        for p_type in priority_to_delete:
            to_remove = None
            for idx, item_obj in enumerate(physical_items):
                if item_obj["is_locked"]:
                    continue
                raw = item_obj["raw"]
                item_type = raw.get("type", "")
                meal_cat = raw.get("_meal_category", "")
                
                if p_type == "gift_shop" and item_type == "gift_shop":
                    to_remove = idx
                    break
                if p_type == "afternoon_tea" and meal_cat == "afternoon_tea":
                    to_remove = idx
                    break
                if p_type == "activity" and item_type == "activity":
                    to_remove = idx
                    break
                    
            if to_remove is not None:
                removed_item = physical_items.pop(to_remove)
                cost, dur, steps = _calc_plan_metrics(physical_items)
                if cost <= budget * 1.2 and dur <= max_dur:
                    updated_plan = deepcopy(plan)
                    updated_plan["steps"] = steps
                    updated_plan["total_duration_minutes"] = dur
                    updated_plan["total_cost"] = cost
                    updated_plan["selected_item_ids"] = [it["it_item"].get("id") if isinstance(it["it_item"], dict) else it["it_item"].id for it in physical_items]
                    return {"status": "success", "plan": updated_plan}
                
        failed_repairs.append(f"已尝试删除低优先级项目，仍不满足约束 (花费: {cost}, 耗时: {dur}分钟)")

    # Level 5: 系统无法自动修复，交给 Agent 生成解释和选择项
    reason = []
    if dur > max_dur:
        reason.append(f"修改后超出原定结束时间约 {int(dur - max_dur)} 分钟")
    if cost > budget * 1.2:
        reason.append(f"修改后超出预算约 {int(cost - budget)} 元")

    report = {
        "status": "need_user_choice",
        "reason": "，".join(reason),
        "locked_items": locked_items,
        "failed_repairs": failed_repairs,
        "options": [
            {
                "label": "保留全部并延长",
                "action": "无视超出的时间和预算，强制保留替换后的方案",
            },
            {
                "label": "撤销替换",
                "action": "放弃本次替换，保留原有行程",
            }
        ]
    }
    
    return {"status": "need_user_choice", "report": report}

