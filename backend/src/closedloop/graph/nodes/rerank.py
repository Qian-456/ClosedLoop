import re
from typing import Any

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.state import ClosedLoopState, Constraints, RankedCombo, RankedPackage, RankedGift
from closedloop.graph.nodes.retrieve import _ensure_candidates_dict, _empty_candidates
from closedloop.utils.capacity import _get_effective_people, _get_capacity_from_name

def score_item(item: dict, inner_item: dict, constraints: Constraints) -> int:
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
        min_distance = 0.0
        max_distance = 10.0
        
        if pref_dist == "<2km":
            min_distance = 0.0
            max_distance = 2.0
        elif pref_dist == "2km-5km":
            min_distance = 2.0
            max_distance = 5.0
        elif pref_dist == ">5km":
            min_distance = 5.0
            max_distance = 10.0 # 设定一个合理的全局上限
            
        if actual_dist <= min_distance:
            scene_fit_score += 20.0
        elif actual_dist >= max_distance:
            scene_fit_score += 0.0
        else:
            # 线性插值，距离越接近 min_distance 得分越高
            ratio = (max_distance - actual_dist) / (max_distance - min_distance)
            scene_fit_score += ratio * 20.0

    suitable_groups = item.get("suitable_groups", []) or []
    item_features = inner_item.get("features", "") or ""
    
    if isinstance(suitable_groups, list):
        if constraints.group_type == "family":
            family_keywords = ("family", "家庭", "亲子", "带娃", "儿童", "三口之家", "宝宝", "老少皆宜")
            # 匹配 suitable_groups 或者 inner_item 的 features
            if any(
                isinstance(g, str) and any(k in g for k in family_keywords)
                for g in suitable_groups
            ) or any(k in item_features for k in family_keywords):
                scene_fit_score += 15
        elif constraints.group_type == "friends":
            friends_keywords = ("friends", "朋友", "情侣", "约会", "聚会", "同事", "闺蜜", "兄弟", "年轻")
            if any(
                isinstance(g, str) and any(k in g for k in friends_keywords)
                for g in suitable_groups
            ) or any(k in item_features for k in friends_keywords):
                scene_fit_score += 15
        elif constraints.group_type == "solo":
            solo_keywords = ("单人", "一人食", "独处", "工作餐", "静谧")
            if any(k in item_features for k in solo_keywords):
                scene_fit_score += 15
            party_keywords = ("聚会", "闺蜜", "团建", "多人", "派对", "家庭", "双人", "情侣")
            if any(k in item_features for k in party_keywords):
                scene_fit_score -= 30
        elif constraints.group_type == "couple":
            couple_keywords = ("情侣", "约会", "双人", "浪漫", "七夕")
            if any(k in item_features for k in couple_keywords):
                scene_fit_score += 15
            large_group_keywords = ("聚会", "团建", "多人", "派对", "家庭", "闺蜜", "单人")
            if any(k in item_features for k in large_group_keywords):
                scene_fit_score -= 30
        elif constraints.group_type == "business":
            business_keywords = ("business", "商务", "宴请", "高端", "安静", "包间")
            if any(
                isinstance(g, str) and any(k in g for k in business_keywords)
                for g in suitable_groups
            ) or any(k in item_features for k in business_keywords):
                scene_fit_score += 15

    # 标签命中 (Tag Matching) - 暂时硬编码为 0 分
    tag_matching_score = 0
    if constraints.activity_preferences:
        tags = set(item.get("tags", []))
        for pref in constraints.activity_preferences:
            if pref in tags:
                tag_matching_score += 0 # 命中标签加分，目前暂设为 0
    scene_fit_score += tag_matching_score

    # 人数契合度打分 (Capacity Match Penalty)
    capacity_penalty = 0
    item_name = inner_item.get("name", "")
    capacity = _get_capacity_from_name(item_name)
    if capacity > 0:
        effective_people = _get_effective_people(constraints)
        diff = abs(capacity - effective_people)
        # 惩罚分：指数级惩罚，相差 1 个人等效扣 15 分，相差 2 人扣 50 分，相差 3 人扣 105 分。
        capacity_penalty = (diff ** 2) * 10 + (diff * 5)
        scene_fit_score -= capacity_penalty

    # 2. 质量热度分 (Quality & Popularity Mock)
    # 将 rating (例如 4.7) 映射到 0-65 分，使得满分体系更接近 100 分
    # 因为距离满分 20，人群匹配满分 15，加上 65 刚好 100
    quality_score = (item.get("rating", 0) / 5.0) * 65.0

    # 核心修正：有机得分（Organic Score）最高严格控制在 100 分
    organic_score = max(0.0, min(100.0, scene_fit_score + quality_score))

    # 3. 商业加权分 (Commercial Boost)
    # 生产环境中，这里可从 item.get("commercial_bid", 0) 获取，允许最终得分突破 100
    commercial_score = 0.0

    total_score = organic_score + commercial_score
    
    return int(total_score)


def rerank_node(state: ClosedLoopState) -> ClosedLoopState:
    """
    对 filter 节点输出的候选列表进行打分并重新排序。
    """
    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=rerank_node | input=start")

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
        for combo in rest.get("combos", []):
            rc: RankedCombo = {
                "combo_id": combo.get("combo_id") or combo.get("id", ""),
                "name": combo.get("name", ""),
                "price": combo.get("price", 0.0),
                "description": combo.get("description", ""),
                "duration_mins": combo.get("duration_mins", 0),
                "duration_std_dev": combo.get("duration_std_dev", 0.0),
                "suitable_time_slots": combo.get("suitable_time_slots", []),
                "score": score_item(rest, combo, constraints),
                "restaurant_id": rest.get("id", ""),
                "restaurant_name": rest.get("name", ""),
                "distance_km": rest.get("distance_km", 0.0),
                "rating": rest.get("rating", 0.0),
                "tags": rest.get("tags", []),
                "suitable_groups": rest.get("suitable_groups", []),
                "location": rest.get("location", {})
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
            rp: RankedPackage = {
                "package_id": pkg.get("package_id") or pkg.get("id", ""),
                "name": pkg.get("name", ""),
                "price": pkg.get("price", 0.0),
                "description": pkg.get("description", ""),
                "duration_mins": pkg.get("duration_mins", 0),
                "duration_std_dev": pkg.get("duration_std_dev", 0.0),
                "start_time": pkg.get("start_time", ""),
                "score": score_item(act, pkg, constraints),
                "venue_id": act.get("id", ""),
                "venue_name": act.get("name", ""),
                "category": act.get("category", ""),
                "distance_km": act.get("distance_km", 0.0),
                "rating": act.get("rating", 0.0),
                "tags": act.get("tags", []),
                "suitable_groups": act.get("suitable_groups", []),
                "location": act.get("location", {})
            }
            ranked_packages.append(rp)

    # 处理礼品
    for gift_shop in candidates.get("nearby_gifts", []):
        for gift in gift_shop.get("gifts", []):
            rg: RankedGift = {
                "gift_id": gift.get("gift_id") or gift.get("id", ""),
                "name": gift.get("name", ""),
                "price": gift.get("price", 0.0),
                "description": gift.get("description", ""),
                "score": score_item(gift_shop, gift, constraints),
                "shop_id": gift_shop.get("id", ""),
                "shop_name": gift_shop.get("name", ""),
                "category": gift_shop.get("category", ""),
                "distance_km": gift_shop.get("distance_km", 0.0),
                "rating": gift_shop.get("rating", 0.0),
                "tags": gift_shop.get("tags", []),
                "suitable_groups": gift_shop.get("suitable_groups", []),
                "location": gift_shop.get("location", {})
            }
            ranked_gifts.append(rg)

    # 降序排序

    ranked_breakfast_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_lunch_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_afternoon_tea_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_dinner_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_late_night_combos.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    ranked_packages.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked_gifts.sort(key=lambda x: x.get("score", 0), reverse=True)

    candidates["ranked_breakfast_combos"] = ranked_breakfast_combos
    candidates["ranked_lunch_combos"] = ranked_lunch_combos
    candidates["ranked_afternoon_tea_combos"] = ranked_afternoon_tea_combos
    candidates["ranked_dinner_combos"] = ranked_dinner_combos
    candidates["ranked_late_night_combos"] = ranked_late_night_combos
    
    candidates["ranked_packages"] = ranked_packages
    candidates["ranked_gifts"] = ranked_gifts
    candidates["processed_steps"].append("rerank_node")

    rest_count = len(candidates.get("nearby_restaurants", []))
    act_count = len(candidates.get("nearby_activities", []))
    gift_count = len(candidates.get("nearby_gifts", []))
    
    rest_combo_count = len(ranked_combos)
    act_pkg_count = len(ranked_packages)
    gift_item_count = len(ranked_gifts)
    
    b_c = len(ranked_breakfast_combos)
    l_c = len(ranked_lunch_combos)
    a_c = len(ranked_afternoon_tea_combos)
    d_c = len(ranked_dinner_combos)
    n_c = len(ranked_late_night_combos)

    logger.info(
        f"phase=rerank_node | output=reranked {b_c} breakfast, {l_c} lunch, {a_c} tea, {d_c} dinner, {n_c} night combos (from {rest_count} restaurants), "
        f"{act_pkg_count} packages (from {act_count} activities), "
        f"{gift_item_count} gifts (from {gift_count} shops)"
    )
    return state