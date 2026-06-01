import re
import time
from typing import Any

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.state import Constraints, PlanState, RankedCombo, RankedPackage, RankedGift
from closedloop.graph.plan_subgraph.retrieve import _ensure_candidates_dict, _empty_candidates
from closedloop.utils.capacity import _get_effective_people, _get_capacity_from_name
from closedloop.utils.mock_db import load_mock_data

def _has_flexible_people_phrase(text: str) -> bool:
    if not text:
        return False
    t = text
    if ("单人" in t or "一人" in t) and ("双人" in t or "两人" in t or "情侣" in t or "2人" in t):
        return True
    if "单人/双人" in t or "单人 / 双人" in t:
        return True
    if re.search(r"\d+\s*[-~到]\s*\d+\s*人", t):
        return True
    return False


def _get_group_mismatch_penalty(inner_item: dict, constraints: Constraints) -> int:
    text = f"{inner_item.get('name', '')} {inner_item.get('description', '')} {inner_item.get('features', '')}"
    if not text.strip():
        return 0
    if _has_flexible_people_phrase(text):
        return 0

    effective_people = _get_effective_people(constraints)
    group_type = constraints.group_type
    is_family = group_type == "family" or (constraints.child_count or 0) > 0

    if is_family:
        forbidden = ("情侣", "约会", "双人", "单人", "一人", "独处", "工作餐", "闺蜜", "兄弟")
    elif group_type == "friends" and effective_people >= 3.0:
        forbidden = ("单人", "一人", "独处", "工作餐", "情侣", "约会", "双人", "家庭", "亲子", "三口之家", "四口之家")
    else:
        forbidden = ()

    if any(k in text for k in forbidden):
        return 30
    return 0


def score_item(item: dict, inner_item: dict, constraints: Constraints, expected_wait_minutes: int = 0) -> int:
    """
    计算排序分数 (三维度打分)：
    总分 = 场景契合分（硬编码） + 质量热度分（模拟推荐） + 商业干预分（商业加权）
    """
    # 1. 场景契合分 (Base Fit Score)
    scene_fit_score = 0
    if "distance_km" in item:
        pref_dist = constraints.preferred_distance
        actual_dist = item["distance_km"]
        
        # 距离得分逻辑：
        # 如果实际距离小于用户选择的距离下限，得满分 (20分)。
        # 如果实际距离大于用户选择的距离上限，得 0 分。
        # 如果实际距离在区间内，进行线性归一化插值。
        if pref_dist == "<2km":
            optimal_max = 2.0
            tolerate_max = 4.0
        elif pref_dist == "2km-5km":
            optimal_max = 5.0
            tolerate_max = 8.0
        elif pref_dist == ">5km":
            optimal_max = 10.0
            tolerate_max = 12.0
            
        if actual_dist <= optimal_max:
            # 距离越近越好，但在最优区间内分数都在高位 (15~20)
            scene_fit_score += 20.0 - (actual_dist / optimal_max) * 5.0
        elif actual_dist <= tolerate_max:
            # 超出最优区间，分数快速衰减 (15~0)
            ratio = (tolerate_max - actual_dist) / (tolerate_max - optimal_max)
            scene_fit_score += ratio * 15.0
        else:
            scene_fit_score += 0.0

    suitable_groups = item.get("suitable_groups", []) or []
    if isinstance(suitable_groups, list):
        matched_group = False
        if constraints.group_type == "family":
            family_keywords = ("family", "家庭", "亲子", "带娃", "儿童")
            if any(
                isinstance(g, str) and any(k in g for k in family_keywords)
                for g in suitable_groups
            ):
                scene_fit_score += 15
                matched_group = True
        elif constraints.group_type == "friends":
            friends_keywords = ("friends", "朋友", "聚会", "多人", "小聚")
            if any(
                isinstance(g, str) and any(k in g for k in friends_keywords)
                for g in suitable_groups
            ):
                scene_fit_score += 15
                matched_group = True

        if not matched_group:
            group_text = f"{inner_item.get('name', '')} {inner_item.get('features', '')} {inner_item.get('description', '')}"
            if constraints.group_type == "family":
                family_keywords = ("family", "家庭", "亲子", "带娃", "儿童", "三口之家", "老少皆宜")
                if any(k in group_text for k in family_keywords):
                    scene_fit_score += 15
            elif constraints.group_type == "friends":
                effective_people = _get_effective_people(constraints)
                friends_keywords = ("friends", "朋友", "聚会", "多人", "小聚", "团建", "派对")
                friends_pair_keywords = ("双人", "2人", "情侣", "约会", "闺蜜", "兄弟", "搭子")
                if any(k in group_text for k in friends_keywords) or (
                    effective_people <= 2.1 and any(k in group_text for k in friends_pair_keywords)
                ):
                    scene_fit_score += 15

    group_mismatch_penalty = _get_group_mismatch_penalty(inner_item, constraints)
    if group_mismatch_penalty:
        scene_fit_score -= group_mismatch_penalty

    if (
        (constraints.group_type == "family" or (constraints.child_count or 0) > 0)
        and item.get("type") == "activity"
        and item.get("age_range_mismatch_for_children")
        and any(isinstance(a, int) and a >= 0 for _, a in (constraints.child_profiles or []))
    ):
        scene_fit_score -= 20

    tag_matching_score = 0
    if constraints.activity_preferences:
        tags = [t for t in (item.get("tags", []) or []) if isinstance(t, str)]
        combined_text = " ".join(tags)
        combined_text += " " + (inner_item.get("name", "") or "")
        combined_text += " " + (inner_item.get("features", "") or "")
        combined_text += " " + (inner_item.get("description", "") or "")

        def _pref_keywords(pref: str) -> tuple[str, ...]:
            p = pref or ""
            if any(k in p for k in ("打卡", "拍照", "出片", "大头贴")):
                return ("打卡", "拍照", "出片", "大头贴", "自拍")
            if any(k in p for k in ("安静", "静", "静谧", "放松", "书店", "书吧", "展览", "咖啡")):
                return ("安静", "静谧", "静", "书店", "书吧", "展览", "博物馆", "咖啡", "茶馆", "休闲")
            if any(k in p for k in ("浪漫", "约会", "情侣", "纪念日")):
                return ("浪漫", "约会", "情侣", "纪念日", "七夕", "玫瑰", "夜景", "氛围")
            if any(k in p for k in ("亲子", "儿童", "小朋友", "带娃", "家庭")):
                return ("亲子", "儿童", "带娃", "家庭", "三口之家", "老少皆宜", "乐园")
            if "室内" in p:
                return ("室内", "书吧", "咖啡", "茶馆", "展览", "博物馆", "VR")
            if any(k in p for k in ("热闹", "聚会", "团建", "派对")):
                return ("热闹", "聚会", "团建", "派对", "狂欢", "夜市", "宵夜")
            if any(k in p for k in ("不排队", "别排队")):
                return ("免排队", "无需排队")
            return (p,)

        matched = 0
        for pref in constraints.activity_preferences:
            if not isinstance(pref, str) or not pref.strip():
                continue
            kws = _pref_keywords(pref.strip())
            if any(k and k in combined_text for k in kws):
                matched += 1
                continue
            if any(t and (t in pref or pref in t) for t in tags):
                matched += 1
                continue

            if any(k in pref for k in ("不排队", "别排队")):
                if any(k in combined_text for k in ("排队", "网红", "爆款")):
                    scene_fit_score -= 5

        tag_matching_score = min(30, matched * 8)

        if any(
            isinstance(p, str)
            and any(k in p for k in ("安静", "静谧", "放松", "书店", "书吧", "展览", "咖啡"))
            for p in constraints.activity_preferences
        ) and any(k in combined_text for k in ("热闹", "派对", "团建", "狂欢", "吵")):
            scene_fit_score -= 5

        if any(
            isinstance(p, str)
            and any(k in p for k in ("热闹", "聚会", "团建", "派对"))
            for p in constraints.activity_preferences
        ) and any(k in combined_text for k in ("安静", "静谧")):
            scene_fit_score -= 5

    scene_fit_score += tag_matching_score

    # 人数契合度打分 (Capacity Match Penalty)
    capacity_penalty = 0
    item_name = inner_item.get("name", "")
    capacity = _get_capacity_from_name(item_name)
    if capacity > 0:
        effective_people = _get_effective_people(constraints)
        diff = abs(capacity - effective_people)
        # 惩罚分：指数级惩罚，相差 1 个人等效扣 15 分，相差 2 人扣 50 分，相差 3 人扣 105 分。
        capacity_penalty = (diff ** 2) * 18 + (diff * 9)
        scene_fit_score -= capacity_penalty

    # 排队偏好打分调整
    if expected_wait_minutes > 0:
        queue_pref = getattr(constraints, "queue_preference", "neutral")
        if queue_pref == "avoid_queues":
            scene_fit_score -= (expected_wait_minutes / 10.0) * 10
        elif queue_pref == "accept_hot":
            scene_fit_score += (expected_wait_minutes / 10.0) * 2
        else:
            scene_fit_score -= (expected_wait_minutes / 10.0) * 2

    # 2. 质量热度分 (Quality & Popularity Mock)
    # 放大利差，让高分店铺更具优势，假设底分为 3.0
    rating = float(item.get("rating", 0.0) or 0.0)
    if rating >= 3.0:
        quality_score = min(65.0, ((rating - 3.0) / 2.0) * 65.0)
    else:
        quality_score = (rating / 3.0) * 10.0 # 差评店得分极低

    # 核心修正：有机得分（Organic Score）最高严格控制在 100 分
    organic_score = max(0.0, min(100.0, scene_fit_score + quality_score))

    # 3. 商业加权分 (Commercial Boost)
    # 生产环境中，这里可从 item.get("commercial_bid", 0) 获取，允许最终得分突破 100
    commercial_score = 0.0

    total_score = organic_score + commercial_score
    
    return int(total_score)


from langchain_core.runnables import RunnableConfig

def rerank_node(state: PlanState, config: RunnableConfig = None) -> PlanState:
    """
    对 filter 节点输出的候选列表进行打分并重新排序。
    """
    app_config = get_config()
    LoggerManager.setup(app_config)
    started_at = time.perf_counter()

    logger.info("phase=rerank_node | input=start")
    
    session_id = "default"
    if config and "configurable" in config:
        session_id = config["configurable"].get("thread_id", "default")

    constraints = state.get("constraints")
    candidates = _ensure_candidates_dict(state)
    processed_steps = candidates.get("processed_steps")

    if processed_steps != ["retrieve_candidates_node", "filter_node"]:
        logger.error(
            f"phase=rerank_node | error=processed_steps_not_ready | processed_steps={processed_steps}"
        )
        return state

    if not constraints:
        logger.error("phase=rerank_node | error=no constraints found")
        return state

    if isinstance(constraints, dict):
        constraints = Constraints(**constraints)

    try:
        reservations = load_mock_data("reservations.json")
    except Exception as e:
        logger.warning(f"phase=rerank_node | msg=failed_to_load_reservations | error={e}")
        reservations = []

    wait_time_map = {}
    for res in reservations:
        target_id = res.get("target_id")
        slots = res.get("time_slots", [])
        if target_id and slots:
            max_wait = max((s.get("wait_minutes", 0) for s in slots), default=0)
            wait_time_map[target_id] = max_wait

    ranked_combos: list[RankedCombo] = []
    ranked_breakfast_combos: list[RankedCombo] = []
    ranked_lunch_combos: list[RankedCombo] = []
    ranked_afternoon_tea_combos: list[RankedCombo] = []
    ranked_dinner_combos: list[RankedCombo] = []
    ranked_late_night_combos: list[RankedCombo] = []
    
    ranked_packages: list[RankedPackage] = []
    ranked_gifts: list[RankedGift] = []

    # 处理餐厅
    for rest in candidates.get("nearby_restaurants", []):
        restaurant_id = rest.get("id", "") or rest.get("restaurant_id", "")
        restaurant_expected_wait = wait_time_map.get(restaurant_id, 0)
        for combo in rest.get("combos", []):
            combo_id = combo.get("combo_id") or combo.get("id", "")
            expected_wait = restaurant_expected_wait
            rc: RankedCombo = {
                "combo_id": combo_id,
                "name": combo.get("name", ""),
                "price": combo.get("price", 0.0),
                "description": combo.get("description", ""),
                "features": combo.get("features", ""),
                "duration_mins": combo.get("duration_mins", 0),
                "duration_std_dev": combo.get("duration_std_dev", 0.0),
                "suitable_time_slots": combo.get("suitable_time_slots", []),
                "score": score_item(rest, combo, constraints, expected_wait),
                "expected_wait_minutes": expected_wait,
                "requires_booking": combo.get("requires_booking", False),
                "restaurant_id": restaurant_id,
                "restaurant_name": rest.get("name", ""),
                "distance_km": rest.get("distance_km", 0.0),
                "rating": rest.get("rating", 0.0),
                "tags": rest.get("tags", []),
                "suitable_groups": rest.get("suitable_groups", []),
                "experience_tag": rest.get("experience_tag", []),
                "photo_score_derived": rest.get("photo_score_derived"),
                "onsite_walking_level_estimated": rest.get("onsite_walking_level_estimated"),
                "noise_level_estimated": rest.get("noise_level_estimated"),
                "district": rest.get("district"),
                "address": rest.get("address"),
                "latitude": rest.get("latitude"),
                "longitude": rest.get("longitude"),
                "location": rest.get("location", {}),
                "kid_menu_status": rest.get("kid_menu_status"),
                "stroller_friendly_status": rest.get("stroller_friendly_status"),
                "child_facility_tags": rest.get("child_facility_tags", []),
                "child_friendly_score_derived": rest.get("child_friendly_score_derived"),
            }
            
            # 分类逻辑：根据套餐自带的时间段标签进行分流
            suitable_slots = combo.get("suitable_time_slots", [])
            
            if "breakfast" in suitable_slots:
                ranked_breakfast_combos.append(rc)
            if "lunch" in suitable_slots:
                ranked_lunch_combos.append(rc)
            if "afternoon_tea" in suitable_slots:
                ranked_afternoon_tea_combos.append(rc)
            if "dinner" in suitable_slots:
                ranked_dinner_combos.append(rc)
            if "late_night" in suitable_slots:
                ranked_late_night_combos.append(rc)
            
    # 处理活动
    for act in candidates.get("nearby_activities", []):
        for pkg in act.get("packages", []):
            package_id = pkg.get("package_id") or pkg.get("id", "")
            expected_wait = wait_time_map.get(package_id, 0)
            rp: RankedPackage = {
                "package_id": package_id,
                "name": pkg.get("name", ""),
                "price": pkg.get("price", 0.0),
                "description": pkg.get("description", ""),
                "features": pkg.get("features", ""),
                "duration_mins": pkg.get("duration_mins", 0),
                "duration_std_dev": pkg.get("duration_std_dev", 0.0),
                "start_time": pkg.get("start_time", ""),
                "score": score_item(act, pkg, constraints, expected_wait),
                "expected_wait_minutes": expected_wait,
                "requires_booking": pkg.get("requires_booking", False),
                "venue_id": act.get("id", ""),
                "venue_name": act.get("name", ""),
                "category": act.get("category", ""),
                "distance_km": act.get("distance_km", 0.0),
                "rating": act.get("rating", 0.0),
                "tags": act.get("tags", []),
                "suitable_groups": act.get("suitable_groups", []),
                "age_range": act.get("age_range", []),
                "experience_tag": act.get("experience_tag", []),
                "photo_score_derived": act.get("photo_score_derived"),
                "onsite_walking_level_estimated": act.get("onsite_walking_level_estimated"),
                "noise_level_estimated": act.get("noise_level_estimated"),
                "district": act.get("district"),
                "address": act.get("address"),
                "latitude": act.get("latitude"),
                "longitude": act.get("longitude"),
                "location": act.get("location", {}),
            }
            ranked_packages.append(rp)

    # 处理礼品
    for gift_shop in candidates.get("nearby_gifts", []):
        for gift in gift_shop.get("gifts", []):
            rg: RankedGift = {
                "gift_id": gift.get("gift_id") or gift.get("id", ""),
                "name": gift.get("name", ""),
                "price": gift.get("price", 0.0),
                "receive_duration_mins": int(gift.get("receive_duration_mins") or 10),
                "receive_duration_std_dev": float(gift.get("receive_duration_std_dev") or 3.0),
                "description": gift.get("description", ""),
                "features": gift.get("features", ""),
                "score": score_item(gift_shop, gift, constraints),
                "shop_id": gift_shop.get("id", ""),
                "shop_name": gift_shop.get("name", ""),
                "category": gift_shop.get("category", ""),
                "distance_km": gift_shop.get("distance_km", 0.0),
                "delivery_radius_km": float(gift_shop.get("delivery_radius_km") or 5.0),
                "rating": gift_shop.get("rating", 0.0),
                "tags": gift_shop.get("tags", []),
                "suitable_groups": gift_shop.get("suitable_groups", []),
                "experience_tag": gift_shop.get("experience_tag", []),
                "photo_score_derived": gift_shop.get("photo_score_derived"),
                "onsite_walking_level_estimated": gift_shop.get("onsite_walking_level_estimated"),
                "noise_level_estimated": gift_shop.get("noise_level_estimated"),
                "district": gift_shop.get("district"),
                "address": gift_shop.get("address"),
                "latitude": gift_shop.get("latitude"),
                "longitude": gift_shop.get("longitude"),
                "location": gift_shop.get("location", {}),
                "gift_type": gift_shop.get("gift_type"),
                "delivery_to_restaurant": gift_shop.get("delivery_to_restaurant"),
                "surprise_score_derived": gift_shop.get("surprise_score_derived"),
            }
            ranked_gifts.append(rg)

    # 降序排序

    ranked_breakfast_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_lunch_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_afternoon_tea_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_dinner_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_late_night_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    ranked_packages.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_light_packages = [p for p in ranked_packages if int(p.get("duration_mins") or 0) <= 60]
    ranked_packages = [p for p in ranked_packages if int(p.get("duration_mins") or 0) > 60]
    ranked_gifts.sort(key=lambda x: x.get("score", 0), reverse=True)

    candidates["ranked_breakfast_combos"] = ranked_breakfast_combos
    candidates["ranked_lunch_combos"] = ranked_lunch_combos
    candidates["ranked_afternoon_tea_combos"] = ranked_afternoon_tea_combos
    candidates["ranked_dinner_combos"] = ranked_dinner_combos
    candidates["ranked_late_night_combos"] = ranked_late_night_combos
    
    candidates["ranked_light_packages"] = ranked_light_packages
    candidates["ranked_packages"] = ranked_packages
    candidates["ranked_gifts"] = ranked_gifts
    candidates["processed_steps"].append("rerank_node")

    rest_count = len(candidates.get("nearby_restaurants", []))
    act_count = len(candidates.get("nearby_activities", []))
    gift_count = len(candidates.get("nearby_gifts", []))
    
    rest_combo_count = len(ranked_combos)
    act_pkg_count = len(ranked_packages)
    act_light_pkg_count = len(ranked_light_packages)
    gift_item_count = len(ranked_gifts)
    
    b_c = len(ranked_breakfast_combos)
    l_c = len(ranked_lunch_combos)
    a_c = len(ranked_afternoon_tea_combos)
    d_c = len(ranked_dinner_combos)
    n_c = len(ranked_late_night_combos)

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        f"phase=rerank_node | output=reranked {b_c} breakfast, {l_c} lunch, {a_c} tea, {d_c} dinner, {n_c} night combos (from {rest_count} restaurants), "
        f"{act_pkg_count} packages (from {act_count} activities), {act_light_pkg_count} light packages, "
        f"{gift_item_count} gifts (from {gift_count} shops) | elapsed_ms={elapsed_ms} | session_id={session_id}"
    )
    return state
