from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.utils.mock_db import load_mock_data

MAX_CANDIDATE_DISTANCE_KM = 12.0


def parse_time(time_str: str) -> float:
    """解析 HH:MM 为小时浮点数"""
    if not time_str:
        return 0.0
    parts = time_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) + int(parts[1]) / 60.0
    return 0.0


def _ensure_candidates_dict(state: ClosedLoopState) -> dict:
    """确保 state['candidates'] 存在且为 dict。"""
    candidates = state.get("candidates")
    if candidates is None:
        candidates = {}
        state["candidates"] = candidates
    if not isinstance(candidates, dict):
        raise ValueError("state['candidates'] must be a dict")
    return candidates


def _empty_candidates(processed_steps: list[str] | None = None) -> dict:
    """构造空的 candidates 结构。"""
    return {
        "nearby_restaurants": [],
        "nearby_activities": [],
        "nearby_gifts": [],
        "processed_steps": list(processed_steps or []),
    }


def _within_distance_cap(item: dict) -> bool:
    """判断候选是否满足全局距离上限（12km）。"""
    distance = item.get("distance_km")
    if distance is None and "location" in item:
        distance = item.get("location", {}).get("distance_to_center_km")
        
    if distance is None:
        logger.warning(
            f"phase=retrieve_candidates_node | warn=missing_distance_km | item_id={item.get('id') or item.get('restaurant_id') or item.get('venue_id') or item.get('shop_id')} | item_type={item.get('type')}"
        )
        return False
    try:
        return float(distance) <= MAX_CANDIDATE_DISTANCE_KM
    except Exception:
        logger.warning(
            f"phase=retrieve_candidates_node | warn=invalid_distance_km | item_id={item.get('id') or item.get('restaurant_id') or item.get('venue_id') or item.get('shop_id')} | item_type={item.get('type')} | distance_km={distance}"
        )
        return False


def _normalize_candidate_items(
    items: list,
    *,
    stage: str,
    category: str,
    expected_type: str,
) -> list[dict]:
    """对 candidates 列表做阶段一致性归一化（warning + 修正，不抛异常）。"""
    normalized: list[dict] = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            logger.warning(
                f"phase={stage} | warn=invalid_item_type | category={category} | idx={idx} | item_type={type(raw)}"
            )
            raw = {}

        item = dict(raw)

        if stage == "retrieve_candidates_node" and "score" in item:
            logger.warning(
                f"phase=retrieve_candidates_node | warn=unexpected_score_in_retrieve | category={category} | item_id={item.get('id')}"
            )
            item.pop("score", None)

        item_id = item.get("id")
        if not item_id:
            item_id = item.get("restaurant_id") or item.get("venue_id") or item.get("shop_id")
            
        if not isinstance(item_id, str) or not item_id:
            new_id = f"tmp_{expected_type}_{idx}"
            logger.warning(
                f"phase={stage} | warn=missing_id | category={category} | idx={idx} | new_id={new_id}"
            )
            item["id"] = new_id
        else:
            item["id"] = item_id

        if "distance_km" not in item and "location" in item:
            dist = item["location"].get("distance_to_center_km")
            if dist is not None:
                item["distance_km"] = float(dist)

        name = item.get("name")
        if not isinstance(name, str) or not name:
            logger.warning(
                f"phase={stage} | warn=missing_name | category={category} | item_id={item.get('id')}"
            )
            item["name"] = "未知"

        t = item.get("type")
        if t != expected_type:
            if t is not None:
                logger.warning(
                    f"phase={stage} | warn=type_mismatch | category={category} | item_id={item.get('id')} | old_type={t} | new_type={expected_type}"
                )
            item["type"] = expected_type

        normalized.append(item)

    return normalized


def retrieve_candidates_node(state: ClosedLoopState) -> ClosedLoopState:
    """从 MockDB 粗召回候选，并对餐厅/活动应用 12km 距离上限。"""
    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=retrieve_candidates_node | input=start")

    candidates = _ensure_candidates_dict(state)
    processed_steps = candidates.get("processed_steps")
    if processed_steps not in (None, []):
        raise ValueError(
            f"retrieve_candidates_node requires candidates.processed_steps to be empty, got: {processed_steps}"
        )

    try:
        nearby_restaurants = load_mock_data("restaurants.json")
        nearby_activities = load_mock_data("activities.json")
        nearby_gifts = load_mock_data("add_ons.json")

        candidates["nearby_restaurants"] = _normalize_candidate_items(
            [x for x in nearby_restaurants if _within_distance_cap(x)],
            stage="retrieve_candidates_node",
            category="nearby_restaurants",
            expected_type="restaurant",
        )
        candidates["nearby_activities"] = _normalize_candidate_items(
            [x for x in nearby_activities if _within_distance_cap(x)],
            stage="retrieve_candidates_node",
            category="nearby_activities",
            expected_type="activity",
        )
        candidates["nearby_gifts"] = _normalize_candidate_items(
            [x for x in nearby_gifts if _within_distance_cap(x)],
            stage="retrieve_candidates_node",
            category="nearby_gifts",
            expected_type="gift_shop",
        )
    except Exception as e:
        logger.error(f"phase=retrieve_candidates_node | error=load_mock_data failed: {e}")
        candidates.update(_empty_candidates())

    candidates["processed_steps"] = ["retrieve_candidates_node"]
    
    # Calculate combo counts for logging
    rest_count = len(candidates.get('nearby_restaurants', []))
    act_count = len(candidates.get('nearby_activities', []))
    gift_count = len(candidates.get('nearby_gifts', []))
    
    rest_combo_count = sum(len(x.get("combos", [])) for x in candidates.get("nearby_restaurants", []))
    act_pkg_count = sum(len(x.get("packages", [])) for x in candidates.get("nearby_activities", []))
    gift_item_count = sum(len(x.get("gifts", [])) for x in candidates.get("nearby_gifts", []))

    logger.info(
        f"phase=retrieve_candidates_node | output=loaded {rest_count} restaurants ({rest_combo_count} combos), {act_count} activities ({act_pkg_count} packages), {gift_count} gifts ({gift_item_count} items)"
    )
    return state


def hard_filter(item: dict, constraints: Constraints) -> bool:
    """第一层：硬过滤（预算/距离偏好/营业时间/儿童年龄）。"""
    budget = constraints.budget

    item_type = item.get("type")
    if item_type == "restaurant":
        combos = item.get("combos", [])
        valid_combos = [c for c in combos if c.get("price", 0) <= budget * 0.7]
        if not valid_combos and combos:
            return False
        item["combos"] = valid_combos
    elif item_type == "activity":
        packages = item.get("packages", [])
        valid_packages = [p for p in packages if p.get("price", 0) <= budget * 0.7]
        if not valid_packages and packages:
            return False
        item["packages"] = valid_packages
    elif item_type == "gift_shop":
        gifts = item.get("gifts", [])
        valid_gifts = [g for g in gifts if g.get("price", 0) <= budget * 0.3]
        if not valid_gifts and gifts:
            return False
        item["gifts"] = valid_gifts

    if "distance_km" in item:
        pref_dist = constraints.preferred_distance
        max_distance = 10.0
        if pref_dist == "<2km":
            max_distance = 2.0
        elif pref_dist == "2km-5km":
            max_distance = 5.0

        if item["distance_km"] > max_distance:
            return False

    time_period = constraints.time_period
    if time_period and "-" in time_period:
        parts = time_period.split("-")
        req_start = parse_time(parts[0])
        req_end = parse_time(parts[1])

        open_time = parse_time(item.get("open_time", "00:00"))
        close_time = parse_time(item.get("close_time", "23:59"))
        if close_time < open_time:
            close_time += 24.0

        if req_end <= open_time or req_start >= close_time:
            # 考虑跨天的情况，放宽条件
            if not (close_time > 24 and req_start + 24 < close_time):
                return False

    return True


def rule_filter(item: dict, constraints: Constraints) -> bool:
    """第二层：规则过滤（家庭常识/饮食限制/避坑标签）。"""
    tags = set(item.get("tags", []))
    avoid_tags = set(item.get("avoid_tags", []))

    if constraints.group_type == "family":
        forbidden = {"酒吧", "精酿", "密室", "夜宵"}
        if tags.intersection(forbidden):
            return False

    if constraints.dietary_restrictions:
        diet_keywords: set[str] = set()
        for r in constraints.dietary_restrictions:
            if "辣" in r:
                diet_keywords.update(["热辣", "重口味", "火锅", "川菜", "小龙虾", "湘菜"])
            if "海鲜" in r:
                diet_keywords.update(["海鲜", "日料", "刺身"])
            if "生冷" in r:
                diet_keywords.update(["日料", "刺身", "沙拉", "轻食", "冷饮"])
            if "甜" in r:
                diet_keywords.update(["甜点", "甜品", "蛋糕", "奶茶", "冰淇淋"])
            if "快餐" in r or "垃圾食品" in r:
                diet_keywords.update(["汉堡", "披萨", "炸鸡"])
            if "牛" in r:
                diet_keywords.update(["牛排", "潮汕牛肉", "牛肉"])

        if tags.intersection(diet_keywords):
            return False

    if constraints.group_type == "family" and "幼儿" in avoid_tags:
        return False

    return True


def filter_node(state: ClosedLoopState) -> ClosedLoopState:
    """对候选做确定性过滤；要求先完成 retrieve_candidates_node。"""
    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=filter_node | input=start")

    constraints = state.get("constraints")
    candidates = _ensure_candidates_dict(state)
    processed_steps = candidates.get("processed_steps")

    if processed_steps != ["retrieve_candidates_node"]:
        logger.error(
            f"phase=filter_node | error=processed_steps_not_ready | processed_steps={processed_steps}"
        )
        state["candidates"] = _empty_candidates(
            processed_steps=processed_steps if isinstance(processed_steps, list) else []
        )
        return state

    if not constraints:
        logger.error("phase=filter_node | error=no constraints found")
        state["candidates"] = _empty_candidates(processed_steps=["retrieve_candidates_node"])
        return state

    if isinstance(constraints, dict):
        constraints = Constraints(**constraints)

    if (
        "nearby_restaurants" not in candidates
        or "nearby_activities" not in candidates
        or "nearby_gifts" not in candidates
    ):
        logger.error("phase=filter_node | error=missing candidate lists")
        state["candidates"] = _empty_candidates(processed_steps=["retrieve_candidates_node"])
        return state

    filtered: dict = {"nearby_restaurants": [], "nearby_activities": [], "nearby_gifts": []}
    for category in ["nearby_restaurants", "nearby_activities", "nearby_gifts"]:
        items = candidates.get(category, []) or []
        filtered_items: list[dict] = []
        for item in items:
            if not hard_filter(item, constraints):
                continue
            if not rule_filter(item, constraints):
                continue
            filtered_items.append(item)

        filtered[category] = filtered_items

    candidates["nearby_restaurants"] = filtered["nearby_restaurants"]
    candidates["nearby_activities"] = filtered["nearby_activities"]
    candidates["nearby_gifts"] = filtered["nearby_gifts"]
    candidates["processed_steps"] = ["retrieve_candidates_node", "filter_node"]

    rest_count = len(filtered['nearby_restaurants'])
    act_count = len(filtered['nearby_activities'])
    gift_count = len(filtered['nearby_gifts'])
    
    rest_combo_count = sum(len(x.get("combos", [])) for x in filtered["nearby_restaurants"])
    act_pkg_count = sum(len(x.get("packages", [])) for x in filtered["nearby_activities"])
    gift_item_count = sum(len(x.get("gifts", [])) for x in filtered["nearby_gifts"])

    logger.info(
        f"phase=filter_node | output=filtered {rest_count} restaurants ({rest_combo_count} combos), {act_count} activities ({act_pkg_count} packages), {gift_count} gifts ({gift_item_count} items)"
    )
    return state
