import re
import uuid
import math

from closedloop.contracts.state import Constraints, PlanState
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.utils.mock_db import load_mock_data
from closedloop.utils.capacity import _get_capacity_from_name, _get_effective_people

MAX_CANDIDATE_DISTANCE_KM = 12.0


def parse_time(time_str: str) -> float:
    """解析 HH:MM 为小时浮点数"""
    if not time_str:
        return 0.0
    parts = time_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) + int(parts[1]) / 60.0
    return 0.0


def _ensure_candidates_dict(state: PlanState) -> dict:
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


def _get_item_id(item: dict) -> str:
    item_id = item.get("id") or item.get("restaurant_id") or item.get("venue_id") or item.get("shop_id")
    return str(item_id) if item_id is not None else ""


def _get_sub_item_id(sub_item: dict, *, subject: str) -> str:
    key_map = {
        "combo": "combo_id",
        "package": "package_id",
        "gift": "gift_id",
    }
    k = key_map.get(subject, "id")
    v = sub_item.get(k) or sub_item.get("id")
    return str(v) if v is not None else ""


def _find_first_match(text: str, terms: list[str]) -> str | None:
    if not text:
        return None
    for t in terms:
        if t and t in text:
            return t
    return None


def _apply_filters_with_events(
    items: list[dict],
    constraints: Constraints,
    *,
    category: str,
) -> tuple[list[dict], list[dict], dict]:
    effective_people = _get_effective_people(constraints)
    budget = constraints.budget
    hard_capacity_diff = 0.6

    def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(k.lower() in t for k in keywords if k)

    def _match_suitable_groups(target_group: str, suitable_groups: list) -> bool:
        if not isinstance(suitable_groups, list) or not suitable_groups:
            return False
        family_keywords = ("family", "家庭", "亲子", "带娃", "儿童", "三口之家", "宝宝", "老少皆宜")
        friends_keywords = ("friends", "朋友", "情侣", "约会", "聚会", "同事", "闺蜜", "兄弟", "年轻")
        kw_map = {
            "family": family_keywords,
            "friends": friends_keywords,
        }
        kws = kw_map.get(target_group, ())
        for g in suitable_groups:
            if not isinstance(g, str) or not g.strip():
                continue
            if target_group in g:
                return True
            if _contains_keyword(g, kws):
                return True
        return False

    def _age_bucket(age: int) -> str | None:
        if age < 0:
            return None
        if age < 3:
            return "3-6"
        if age <= 6:
            return "3-6"
        if age <= 10:
            return "7-10"
        if age <= 17:
            return "11-17"
        return None

    before_sub_item_count = 0
    for it in items:
        t = it.get("type")
        if t == "restaurant":
            before_sub_item_count += len(it.get("combos", []) or [])
        elif t == "activity":
            before_sub_item_count += len(it.get("packages", []) or [])
        elif t == "gift_shop":
            before_sub_item_count += len(it.get("gifts", []) or [])

    filtered_items: list[dict] = []
    events: list[dict] = []

    def _emit_drop(
        *,
        stage: str,
        subject: str,
        reason_code: str,
        item_id: str,
        parent_id: str | None = None,
        reason_detail: dict | None = None,
    ) -> None:
        ev = {
            "event": "filter_drop",
            "phase": "filter_node",
            "category": category,
            "stage": stage,
            "subject": subject,
            "reason_code": reason_code,
            "item_id": item_id,
            "reason_detail": reason_detail or {},
        }
        if parent_id:
            ev["parent_id"] = parent_id
        events.append(ev)

    def _has_flexible_people_phrase(text: str) -> bool:
        if not text:
            return False
        t = text
        if ("单人" in t or "一人" in t) and (
            "双人" in t or "两人" in t or "情侣" in t or "2人" in t
        ):
            return True
        if "单人/双人" in t or "单人 / 双人" in t:
            return True
        if re.search(r"\d+\s*[-~到]\s*\d+\s*人", t):
            return True
        return False

    def _get_group_mismatch_detail(text: str) -> dict | None:
        if not text:
            return None
        if _has_flexible_people_phrase(text):
            return None

        group_type = constraints.group_type
        is_family = group_type == "family" or (constraints.child_count or 0) > 0

        if is_family:
            forbidden = ["情侣", "约会", "双人", "单人", "一人", "独处", "工作餐", "闺蜜", "兄弟"]
        elif group_type == "friends" and effective_people >= 3.0:
            forbidden = ["单人", "一人", "独处", "工作餐", "情侣", "约会", "双人", "家庭", "亲子", "三口之家", "四口之家"]
        else:
            forbidden = []

        matched = _find_first_match(text, forbidden)
        if matched:
            return {"matched_term": matched}
        return None

    def _find_forbidden_term_detail(item: dict, forbidden_terms: list[str]) -> dict | None:
        item_name = item.get("name", "") or ""
        matched = _find_first_match(item_name, forbidden_terms)
        if matched:
            return {
                "matched_term": matched,
                "matched_field": "name",
                "matched_element_type": "item",
                "matched_element_id": _get_item_id(item),
            }

        tags = " ".join(item.get("tags", []) or [])
        matched = _find_first_match(tags, forbidden_terms)
        if matched:
            return {
                "matched_term": matched,
                "matched_field": "tags",
                "matched_element_type": "item",
                "matched_element_id": _get_item_id(item),
            }

        for subject, arr in [
            ("combo", item.get("combos", []) or []),
            ("package", item.get("packages", []) or []),
            ("gift", item.get("gifts", []) or []),
        ]:
            for sub in arr:
                for field in ["name", "description", "features"]:
                    v = sub.get(field, "") or ""
                    matched = _find_first_match(v, forbidden_terms)
                    if matched:
                        return {
                            "matched_term": matched,
                            "matched_field": field,
                            "matched_element_type": subject,
                            "matched_element_id": _get_sub_item_id(sub, subject=subject),
                        }
        return None

    def _dietary_detail(tags_set: set[str]) -> dict | None:
        if not constraints.dietary_restrictions:
            return None

        mapping: dict[str, list[str]] = {}
        for r in constraints.dietary_restrictions:
            if "辣" in r:
                mapping[r] = ["热辣", "重口味", "火锅", "川菜", "小龙虾", "湘菜"]
            elif "海鲜" in r:
                mapping[r] = ["海鲜", "日料", "刺身"]
            elif "生冷" in r:
                mapping[r] = ["日料", "刺身", "沙拉", "轻食", "冷饮"]
            elif "甜" in r:
                mapping[r] = ["甜点", "甜品", "蛋糕", "奶茶", "冰淇淋"]
            elif "快餐" in r or "垃圾食品" in r:
                mapping[r] = ["汉堡", "披萨", "炸鸡"]
            elif "牛" in r:
                mapping[r] = ["牛排", "潮汕牛肉", "牛肉"]

        for r, kws in mapping.items():
            for kw in kws:
                if kw in tags_set:
                    return {"matched_term": kw, "matched_field": "tags", "restriction": r}
        return None

    for item in items:
        item_id = _get_item_id(item)
        item_type = item.get("type")

        is_family = constraints.group_type == "family" or (constraints.child_count or 0) > 0
        target_group = "family" if is_family else constraints.group_type
        suitable_groups = item.get("suitable_groups")
        if not isinstance(suitable_groups, list) or not suitable_groups:
            _emit_drop(
                stage="hard_filter",
                subject="item",
                reason_code="suitable_groups_missing_or_empty",
                item_id=item_id,
                reason_detail={"target_group": target_group, "suitable_groups": suitable_groups},
            )
            continue
        if not _match_suitable_groups(target_group, suitable_groups):
            _emit_drop(
                stage="hard_filter",
                subject="item",
                reason_code="suitable_groups_mismatch",
                item_id=item_id,
                reason_detail={"target_group": target_group, "suitable_groups": suitable_groups},
            )
            continue

        if item_type == "activity" and (constraints.child_count or 0) > 0:
            age_ranges = item.get("age_range")
            if not isinstance(age_ranges, list) or not age_ranges:
                _emit_drop(
                    stage="hard_filter",
                    subject="item",
                    reason_code="activity_age_range_missing_or_empty",
                    item_id=item_id,
                    reason_detail={"age_range": age_ranges},
                )
                continue

            mismatch = None
            for _, age in constraints.child_profiles or []:
                if not isinstance(age, int):
                    continue
                bucket = _age_bucket(age)
                if not bucket:
                    continue
                if bucket not in age_ranges:
                    mismatch = {"child_age": int(age), "bucket": bucket, "age_range": age_ranges}
                    break
            if mismatch:
                _emit_drop(
                    stage="hard_filter",
                    subject="item",
                    reason_code="activity_age_range_mismatch",
                    item_id=item_id,
                    reason_detail=mismatch,
                )
                item["age_range_mismatch_for_children"] = True

        if item_type in ("restaurant", "activity"):
            threshold = budget * 0.7
            sub_key = "combos" if item_type == "restaurant" else "packages"
            subject = "combo" if item_type == "restaurant" else "package"
            sub_items = item.get(sub_key, []) or []
            valid_sub_items = []
            for sub in sub_items:
                sub_id = _get_sub_item_id(sub, subject=subject)
                price = sub.get("price", 0) or 0
                if price > threshold:
                    _emit_drop(
                        stage="hard_filter",
                        subject=subject,
                        reason_code="sub_item_price_too_high",
                        item_id=sub_id,
                        parent_id=item_id,
                        reason_detail={"actual": float(price), "threshold": float(threshold)},
                    )
                    continue

                searchable_text = f"{sub.get('name', '')} {sub.get('description', '')} {sub.get('features', '')}"

                capacity = _get_capacity_from_name(sub.get("name", ""))
                if capacity > 0 and abs(capacity - effective_people) >= hard_capacity_diff:
                    _emit_drop(
                        stage="hard_filter",
                        subject=subject,
                        reason_code="sub_item_capacity_mismatch",
                        item_id=sub_id,
                        parent_id=item_id,
                        reason_detail={"actual": float(capacity), "threshold": float(effective_people)},
                    )
                    continue

                valid_sub_items.append(sub)

            if sub_items and not valid_sub_items:
                _emit_drop(
                    stage="hard_filter",
                    subject="item",
                    reason_code="all_sub_items_filtered",
                    item_id=item_id,
                    reason_detail={"actual": 0, "threshold": 1, "original_sub_item_count": len(sub_items)},
                )
                continue

            item[sub_key] = valid_sub_items

        elif item_type == "gift_shop":
            threshold = budget * 0.3
            gifts = item.get("gifts", []) or []
            valid_gifts = []
            for g in gifts:
                gift_id = _get_sub_item_id(g, subject="gift")
                price = g.get("price", 0) or 0
                if price > threshold:
                    _emit_drop(
                        stage="hard_filter",
                        subject="gift",
                        reason_code="sub_item_price_too_high",
                        item_id=gift_id,
                        parent_id=item_id,
                        reason_detail={"actual": float(price), "threshold": float(threshold)},
                    )
                    continue
                valid_gifts.append(g)

            if gifts and not valid_gifts:
                _emit_drop(
                    stage="hard_filter",
                    subject="item",
                    reason_code="all_sub_items_filtered",
                    item_id=item_id,
                    reason_detail={"actual": 0, "threshold": 1, "original_sub_item_count": len(gifts)},
                )
                continue

            item["gifts"] = valid_gifts

        if "distance_km" in item:
            pref_dist = constraints.preferred_distance
            max_distance = 10.0
            if pref_dist == "<2km":
                max_distance = 2.0
            elif pref_dist == "2km-5km":
                max_distance = 7.0

            if item["distance_km"] > max_distance:
                _emit_drop(
                    stage="hard_filter",
                    subject="item",
                    reason_code="distance_over_max",
                    item_id=item_id,
                    reason_detail={"actual": float(item["distance_km"]), "threshold": float(max_distance)},
                )
                continue

        time_period = constraints.time_period
        if time_period:
            req_start = 0.0
            req_end = 0.0

            if "-" in time_period:
                parts = time_period.split("-")
                req_start = parse_time(parts[0])
                req_end = parse_time(parts[1])
                if req_end < req_start:
                    req_end += 24.0
            else:
                req_start = parse_time(time_period)
                duration_hours = constraints.duration_hours
                max_h = 6.0
                if isinstance(duration_hours, (list, tuple)) and len(duration_hours) == 2:
                    v = duration_hours[1]
                    if isinstance(v, (int, float)) and float(v) > 0:
                        max_h = float(v)
                req_end = req_start + max_h

            open_time = parse_time(item.get("open_time", "00:00"))
            close_time = parse_time(item.get("close_time", "23:59"))
            if close_time < open_time:
                close_time += 24.0

            if req_end <= open_time or req_start >= close_time:
                if not (close_time > 24 and req_start + 24 < close_time):
                    _emit_drop(
                        stage="hard_filter",
                        subject="item",
                        reason_code="outside_open_hours",
                        item_id=item_id,
                        reason_detail={
                            "actual": {"req_start": req_start, "req_end": req_end},
                            "threshold": {"open_time": open_time, "close_time": close_time},
                        },
                    )
                    continue

        tags = set(item.get("tags", []) or [])
        avoid_tags = set(item.get("avoid_tags", []) or [])

        if constraints.child_count > 0 or constraints.group_type == "family":
            known_ages = [
                age
                for _, age in (constraints.child_profiles or [])
                if isinstance(age, int) and age >= 0
            ]
            youngest_age = min(known_ages) if known_ages else 6

            forbidden = ["酒吧", "精酿", "红酒", "啤酒", "酒香", "微醺", "成人", "极速"]
            if youngest_age < 16:
                forbidden += ["网吧", "电竞", "极限", "尸潮", "失重"]
            if youngest_age < 12:
                forbidden += ["密室", "夜宵", "深夜", "KTV", "盲盒", "端盒", "随机"]
            if youngest_age < 6:
                forbidden += ["剧本杀", "恐怖", "刺激", "烧烤", "恶搞", "发泄", "重口味"]

            forbidden_detail = _find_forbidden_term_detail(item, forbidden)
            if forbidden_detail:
                _emit_drop(
                    stage="rule_filter",
                    subject="item",
                    reason_code="family_forbidden_terms",
                    item_id=item_id,
                    reason_detail=forbidden_detail,
                )
                continue

        dietary_detail = _dietary_detail(tags)
        if dietary_detail:
            dietary_detail.update(
                {
                    "matched_element_type": "item",
                    "matched_element_id": item_id,
                }
            )
            _emit_drop(
                stage="rule_filter",
                subject="item",
                reason_code="dietary_restriction_hit",
                item_id=item_id,
                reason_detail=dietary_detail,
            )
            continue

        if constraints.group_type == "family" and "幼儿" in avoid_tags:
            _emit_drop(
                stage="rule_filter",
                subject="item",
                reason_code="family_avoid_infant",
                item_id=item_id,
                reason_detail={
                    "matched_term": "幼儿",
                    "matched_field": "avoid_tags",
                    "matched_element_type": "item",
                    "matched_element_id": item_id,
                },
            )
            continue

        filtered_items.append(item)

    after_sub_item_count = 0
    for it in filtered_items:
        t = it.get("type")
        if t == "restaurant":
            after_sub_item_count += len(it.get("combos", []) or [])
        elif t == "activity":
            after_sub_item_count += len(it.get("packages", []) or [])
        elif t == "gift_shop":
            after_sub_item_count += len(it.get("gifts", []) or [])

    counts = {
        "before_count": len(items),
        "after_count": len(filtered_items),
        "dropped_count": len(items) - len(filtered_items),
        "before_sub_item_count": before_sub_item_count,
        "after_sub_item_count": after_sub_item_count,
        "dropped_sub_item_count": before_sub_item_count - after_sub_item_count,
    }

    return filtered_items, events, counts


def _within_distance_cap(item: dict) -> bool:
    """判断候选是否满足全局距离上限（12km）。"""
    distance = item.get("distance_km")
    if distance is None:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            distance = math.sqrt(float(lat) ** 2 + float(lon) ** 2)
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
        if "distance_km" not in item:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                item["distance_km"] = float(math.sqrt(float(lat) ** 2 + float(lon) ** 2))

        name = item.get("name")
        if not isinstance(name, str) or not name:
            logger.warning(
                f"phase={stage} | warn=missing_name | category={category} | item_id={item.get('id')}"
            )
            item["name"] = "未知"

        cat = item.get("category")
        if cat != expected_type:
            if cat is not None:
                logger.warning(
                    f"phase={stage} | warn=category_mismatch | category={category} | item_id={item.get('id')} | old_category={cat} | new_category={expected_type}"
                )
            item["category"] = expected_type

        t = item.get("type")
        if t != expected_type:
            if t is not None:
                logger.warning(
                    f"phase={stage} | warn=type_mismatch | category={category} | item_id={item.get('id')} | old_type={t} | new_type={expected_type}"
                )
            item["type"] = expected_type

        bh = item.get("business_hours")
        if isinstance(bh, str) and "-" in bh and ("open_time" not in item or "close_time" not in item):
            try:
                o, c = bh.split("-", 1)
                item.setdefault("open_time", o.strip())
                item.setdefault("close_time", c.strip())
            except Exception:
                pass

        normalized.append(item)

    return normalized


def retrieve_candidates_node(state: PlanState) -> PlanState:
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
    """第一层：硬过滤（预算/距离偏好/营业时间/儿童年龄/容量）。"""
    budget = constraints.budget
    effective_people = _get_effective_people(constraints)
    hard_capacity_diff = 0.6

    def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(k.lower() in t for k in keywords if k)

    def _match_suitable_groups(target_group: str, suitable_groups: list) -> bool:
        if not isinstance(suitable_groups, list) or not suitable_groups:
            return False
        family_keywords = ("family", "家庭", "亲子", "带娃", "儿童", "三口之家", "宝宝", "老少皆宜")
        friends_keywords = ("friends", "朋友", "情侣", "约会", "聚会", "同事", "闺蜜", "兄弟", "年轻")
        kw_map = {
            "family": family_keywords,
            "friends": friends_keywords,
        }
        kws = kw_map.get(target_group, ())
        for g in suitable_groups:
            if not isinstance(g, str) or not g.strip():
                continue
            if target_group in g:
                return True
            if _contains_keyword(g, kws):
                return True
        return False

    def _age_bucket(age: int) -> str | None:
        if age < 0:
            return None
        if age < 3:
            return "3-6"
        if age <= 6:
            return "3-6"
        if age <= 10:
            return "7-10"
        if age <= 17:
            return "11-17"
        return None

    is_family = constraints.group_type == "family" or (constraints.child_count or 0) > 0
    target_group = "family" if is_family else constraints.group_type
    suitable_groups = item.get("suitable_groups")
    if not isinstance(suitable_groups, list) or not suitable_groups:
        return False
    if not _match_suitable_groups(target_group, suitable_groups):
        return False

    item_type = item.get("type")
    if item_type == "activity" and (constraints.child_count or 0) > 0:
        age_ranges = item.get("age_range")
        if not isinstance(age_ranges, list) or not age_ranges:
            return False
        mismatch = False
        for _, age in constraints.child_profiles or []:
            if not isinstance(age, int):
                continue
            bucket = _age_bucket(age)
            if not bucket:
                continue
            if bucket not in age_ranges:
                mismatch = True
                break
        if mismatch:
            item["age_range_mismatch_for_children"] = True

    if item_type == "restaurant":
        combos = item.get("combos", [])
        valid_combos = []
        for c in combos:
            if c.get("price", 0) > budget * 0.7:
                continue
            searchable_text = f"{c.get('name', '')} {c.get('description', '')} {c.get('features', '')}"
            capacity = _get_capacity_from_name(c.get("name", ""))
            if capacity > 0 and abs(capacity - effective_people) >= hard_capacity_diff:
                continue
            valid_combos.append(c)
        if not valid_combos and combos:
            return False
        item["combos"] = valid_combos
    elif item_type == "activity":
        packages = item.get("packages", [])
        valid_packages = []
        for p in packages:
            if p.get("price", 0) > budget * 0.7:
                continue
            searchable_text = f"{p.get('name', '')} {p.get('description', '')} {p.get('features', '')}"
            capacity = _get_capacity_from_name(p.get("name", ""))
            if capacity > 0 and abs(capacity - effective_people) >= hard_capacity_diff:
                continue
            valid_packages.append(p)
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
            max_distance = 7.0

        if item["distance_km"] > max_distance:
            return False

    time_period = constraints.time_period
    if time_period:
        req_start = 0.0
        req_end = 0.0

        if "-" in time_period:
            parts = time_period.split("-")
            req_start = parse_time(parts[0])
            req_end = parse_time(parts[1])
            if req_end < req_start:
                req_end += 24.0
        else:
            req_start = parse_time(time_period)
            duration_hours = constraints.duration_hours
            max_h = 6.0
            if isinstance(duration_hours, (list, tuple)) and len(duration_hours) == 2:
                v = duration_hours[1]
                if isinstance(v, (int, float)) and float(v) > 0:
                    max_h = float(v)
            req_end = req_start + max_h

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
    
    # 提取所有可搜索的文本特征（店铺名，标签，套餐名，描述，特色）
    searchable_text = item.get("name", "") + " " + " ".join(tags)
    for c in item.get("combos", []) + item.get("packages", []) + item.get("gifts", []):
        searchable_text += " " + c.get("name", "")
        searchable_text += " " + c.get("description", "")
        searchable_text += " " + c.get("features", "")

    if constraints.child_count > 0 or constraints.group_type == "family":
        # 如果有儿童，提取最小儿童年龄；如果未知则默认假设为 6 岁（更严格的保护）
        known_ages = [
            age
            for _, age in (constraints.child_profiles or [])
            if isinstance(age, int) and age >= 0
        ]
        youngest_age = min(known_ages) if known_ages else 6
        
        # 对于所有未成年人：严格禁止酒精和极端成人向词汇
        forbidden = {"酒吧", "精酿", "红酒", "啤酒", "酒香", "微醺", "成人", "极速"}
        
        if youngest_age < 16:
            # 16岁以下限制网吧及高强度刺激
            forbidden.update(["网吧", "电竞", "极限", "尸潮", "失重"])
            
        if youngest_age < 12:
            # 12岁以下限制密室、深夜夜宵场所及盲盒等可能引发冲动消费的内容
            forbidden.update(["密室", "夜宵", "深夜", "KTV", "盲盒", "端盒", "随机"])
            
        if youngest_age < 6:
            # 6岁以下限制剧本杀、恐怖、烧烤及可能引起不适的搞怪内容
            forbidden.update(["剧本杀", "恐怖", "刺激", "烧烤", "恶搞", "发泄", "重口味"])

        if any(f in searchable_text for f in forbidden):
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


def filter_node(state: PlanState) -> PlanState:
    """对候选做确定性过滤；要求先完成 retrieve_candidates_node。"""
    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=filter_node | input=start")
    run_id = uuid.uuid4().hex
    detailed_debug = getattr(config.logging, "FILTER_LOG_DETAILED_DEBUG", True)

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
    counts_by_category: dict[str, dict] = {}

    for category in ["nearby_restaurants", "nearby_activities", "nearby_gifts"]:
        items = candidates.get(category, []) or []
        filtered_items, events, counts = _apply_filters_with_events(
            items, constraints, category=category
        )
        filtered[category] = filtered_items
        counts_by_category[category] = counts

        reason_code_counts: dict[str, int] = {}
        age_range_missing_ids: list[str] = []
        for ev in events:
            rc = ev.get("reason_code") or "unknown"
            reason_code_counts[rc] = reason_code_counts.get(rc, 0) + 1
            if rc == "activity_age_range_missing_or_empty":
                item_id = ev.get("item_id")
                if isinstance(item_id, str) and item_id:
                    age_range_missing_ids.append(item_id)

        logger.info(
            f"phase=filter_node | output=drop_reasons run_id={run_id} | category={category} | reason_code_counts={reason_code_counts}"
        )

        if age_range_missing_ids:
            sample = list(dict.fromkeys(age_range_missing_ids))[:3]
            logger.warning(
                f"phase=filter_node | warn=activity_age_range_missing_or_empty | run_id={run_id} | category={category} | count={len(age_range_missing_ids)} | sample_item_ids={sample}"
            )

        if detailed_debug:
            for ev in events:
                logger.bind(run_id=run_id, **ev).debug("filter_drop")

        logger.bind(
            event="filter_counts",
            phase="filter_node",
            run_id=run_id,
            category=category,
            before_count=counts["before_count"],
            after_count=counts["after_count"],
            dropped_count=counts["dropped_count"],
            before_sub_item_count=counts["before_sub_item_count"],
            after_sub_item_count=counts["after_sub_item_count"],
            dropped_sub_item_count=counts["dropped_sub_item_count"],
        ).info("filter_counts")

    candidates["nearby_restaurants"] = filtered["nearby_restaurants"]
    candidates["nearby_activities"] = filtered["nearby_activities"]
    candidates["nearby_gifts"] = filtered["nearby_gifts"]
    candidates["processed_steps"] = ["retrieve_candidates_node", "filter_node"]

    rest_after = len(filtered["nearby_restaurants"])
    act_after = len(filtered["nearby_activities"])
    gift_after = len(filtered["nearby_gifts"])

    rest_combo_after = sum(len(x.get("combos", [])) for x in filtered["nearby_restaurants"])
    act_pkg_after = sum(len(x.get("packages", [])) for x in filtered["nearby_activities"])
    gift_item_after = sum(len(x.get("gifts", [])) for x in filtered["nearby_gifts"])

    rest_before = counts_by_category.get("nearby_restaurants", {}).get("before_count", 0)
    act_before = counts_by_category.get("nearby_activities", {}).get("before_count", 0)
    gift_before = counts_by_category.get("nearby_gifts", {}).get("before_count", 0)

    rest_dropped = rest_before - rest_after
    act_dropped = act_before - act_after
    gift_dropped = gift_before - gift_after

    logger.info(
        f"phase=filter_node | output=counts run_id={run_id} | restaurants {rest_before}->{rest_after} (-{rest_dropped}, {rest_combo_after} combos) | activities {act_before}->{act_after} (-{act_dropped}, {act_pkg_after} packages) | gifts {gift_before}->{gift_after} (-{gift_dropped}, {gift_item_after} items)"
    )
    return state
