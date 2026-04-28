from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.utils.mock_db import load_mock_data

MAX_CANDIDATE_DISTANCE_KM = 15.0


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
    """判断候选是否满足全局距离上限（15km）。"""
    distance = item.get("distance_km")
    if distance is None:
        logger.warning(
            f"phase=retrieve_candidates_node | warn=missing_distance_km | item_id={item.get('id')} | item_type={item.get('type')}"
        )
        return False
    try:
        return float(distance) <= MAX_CANDIDATE_DISTANCE_KM
    except Exception:
        logger.warning(
            f"phase=retrieve_candidates_node | warn=invalid_distance_km | item_id={item.get('id')} | item_type={item.get('type')} | distance_km={distance}"
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
        if not isinstance(item_id, str) or not item_id:
            new_id = f"tmp_{expected_type}_{idx}"
            logger.warning(
                f"phase={stage} | warn=missing_id | category={category} | idx={idx} | new_id={new_id}"
            )
            item["id"] = new_id

        name = item.get("name")
        if not isinstance(name, str) or not name:
            logger.warning(
                f"phase={stage} | warn=missing_name | category={category} | item_id={item.get('id')}"
            )
            item["name"] = "未知"

        t = item.get("type")
        if t != expected_type:
            logger.warning(
                f"phase={stage} | warn=type_mismatch | category={category} | item_id={item.get('id')} | old_type={t} | new_type={expected_type}"
            )
            item["type"] = expected_type

        normalized.append(item)

    return normalized


def retrieve_candidates_node(state: ClosedLoopState) -> ClosedLoopState:
    """从 MockDB 粗召回候选，并对餐厅/活动应用 15km 距离上限。"""
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
    logger.info(
        f"phase=retrieve_candidates_node | output=loaded {len(candidates.get('nearby_restaurants', []))} restaurants, {len(candidates.get('nearby_activities', []))} activities, {len(candidates.get('nearby_gifts', []))} gifts"
    )
    return state


def hard_filter(item: dict, constraints: Constraints) -> bool:
    """第一层：硬过滤（预算/距离偏好/营业时间/儿童年龄）。"""
    people_count = constraints.people_count or 1
    budget = constraints.budget

    item_type = item.get("type")
    if item_type == "restaurant":
        price = item.get("avg_price_per_person", 0)
        if price * people_count > budget * 0.7:
            return False
    elif item_type == "activity":
        price = item.get("price_per_person", 0)
        if price * people_count > budget * 0.7:
            return False
    elif item_type == "gift_shop":
        price = item.get("price", 0)
        if price > budget * 0.3:
            return False

    if "distance_km" in item:
        pref_dist = constraints.preferred_distance
        max_distance = 12.0
        if pref_dist == "<2km":
            max_distance = 3.0
        elif pref_dist == "2km-5km":
            max_distance = 6.0

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

    if item_type == "activity" and constraints.group_type == "family":
        child_age = constraints.child_age
        if child_age is not None:
            min_age = item.get("min_child_age", 0)
            max_age = item.get("max_child_age", 99)
            if child_age < min_age or child_age > max_age:
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
                diet_keywords.update(["热辣", "重口味", "火锅"])
            if "海鲜" in r:
                diet_keywords.update(["海鲜", "日料", "刺身"])

        if tags.intersection(diet_keywords):
            return False

    if constraints.group_type == "family" and "幼儿" in avoid_tags:
        return False

    return True


def score_item(item: dict, constraints: Constraints) -> int:
    """第三层：计算排序分数。"""
    score = 0
    score += item.get("rating", 0) * 10

    if "distance_km" in item:
        score += max(0, 10 - item["distance_km"]) * 2

    suitable_groups = item.get("suitable_groups", []) or []
    if isinstance(suitable_groups, list):
        if constraints.group_type == "family":
            family_keywords = ("family", "家庭", "亲子", "带娃", "儿童")
            if any(
                isinstance(g, str) and any(k in g for k in family_keywords)
                for g in suitable_groups
            ):
                score += 15
        elif constraints.group_type == "friends":
            friends_keywords = ("friends", "朋友", "情侣", "约会", "聚会", "同事")
            if any(
                isinstance(g, str) and any(k in g for k in friends_keywords)
                for g in suitable_groups
            ):
                score += 15

    if constraints.activity_preferences:
        tags = set(item.get("tags", []))
        for pref in constraints.activity_preferences:
            if pref in tags:
                score += 10

    return int(score)


def filter_rank_node(state: ClosedLoopState) -> ClosedLoopState:
    """对候选做确定性过滤与排序；要求先完成 retrieve_candidates_node。"""
    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=filter_rank_node | input=start")

    constraints = state.get("constraints")
    candidates = _ensure_candidates_dict(state)
    processed_steps = candidates.get("processed_steps")

    if processed_steps != ["retrieve_candidates_node"]:
        logger.error(
            f"phase=filter_rank_node | error=processed_steps_not_ready | processed_steps={processed_steps}"
        )
        state["candidates"] = _empty_candidates(
            processed_steps=processed_steps if isinstance(processed_steps, list) else []
        )
        return state

    if not constraints:
        logger.error("phase=filter_rank_node | error=no constraints found")
        state["candidates"] = _empty_candidates(processed_steps=["retrieve_candidates_node"])
        return state

    if isinstance(constraints, dict):
        constraints = Constraints(**constraints)

    if (
        "nearby_restaurants" not in candidates
        or "nearby_activities" not in candidates
        or "nearby_gifts" not in candidates
    ):
        logger.error("phase=filter_rank_node | error=missing candidate lists")
        state["candidates"] = _empty_candidates(processed_steps=["retrieve_candidates_node"])
        return state

    ranked: dict = {"nearby_restaurants": [], "nearby_activities": [], "nearby_gifts": []}
    for category in ["nearby_restaurants", "nearby_activities", "nearby_gifts"]:
        items = candidates.get(category, []) or []
        filtered_items: list[dict] = []
        for item in items:
            if not hard_filter(item, constraints):
                continue
            if not rule_filter(item, constraints):
                continue
            item_copy = item.copy()
            item_copy["score"] = score_item(item, constraints)
            filtered_items.append(item_copy)

        filtered_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        ranked[category] = filtered_items

    candidates["nearby_restaurants"] = ranked["nearby_restaurants"]
    candidates["nearby_activities"] = ranked["nearby_activities"]
    candidates["nearby_gifts"] = ranked["nearby_gifts"]
    candidates["processed_steps"] = ["retrieve_candidates_node", "filter_rank_node"]

    logger.info(
        f"phase=filter_rank_node | output=ranked {len(ranked['nearby_restaurants'])} restaurants, {len(ranked['nearby_activities'])} activities, {len(ranked['nearby_gifts'])} gifts"
    )
    return state
