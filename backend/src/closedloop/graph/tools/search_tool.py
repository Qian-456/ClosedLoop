import json
from typing import Annotated, Literal

import httpx
import jieba
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field, model_validator

from closedloop.contracts.state import Constraints
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger


DIETARY_RESTRICTION_KEYWORDS = {
    "辣": ["热辣", "重口味", "火锅", "川菜", "小龙虾", "湘菜", "重辣"],
    "海鲜": ["海鲜", "日料", "刺身"],
    "生冷": ["日料", "刺身", "沙拉", "轻食", "冷饮"],
    "甜": ["甜点", "甜品", "蛋糕", "奶茶", "冰淇淋"],
    "快餐": ["汉堡", "披萨", "炸鸡"],
    "垃圾食品": ["汉堡", "披萨", "炸鸡"],
    "牛": ["牛排", "潮汕牛肉", "牛肉"],
}


class SearchCandidatesInput(BaseModel):
    category: Literal["restaurant", "activity", "gift_shop"] = Field(
        ..., description="搜索类别"
    )
    user_request: str = Field(
        ..., description="用户的自然语言搜索词，例如 '找个便宜点的' 或 '有儿童乐园的'"
    )
    top_k: int = Field(default=5, description="最多返回的结果数量")
    subcatory: (
        Literal[
            "breakfast",
            "lunch",
            "afternoon_tea",
            "dinner",
            "late_night",
            "light",
            "normal",
        ]
        | None
    ) = Field(default=None, description="子类目：restaurant=餐时，activity=light/normal")

    @model_validator(mode="after")
    def _validate_subcatory(self) -> "SearchCandidatesInput":
        restaurant_values = {"breakfast", "lunch", "afternoon_tea", "dinner", "late_night"}
        activity_values = {"light", "normal"}

        if self.subcatory is None:
            return self

        if self.category == "restaurant" and self.subcatory not in restaurant_values:
            raise ValueError(f"invalid subcatory for restaurant: {self.subcatory}")

        if self.category == "activity" and self.subcatory not in activity_values:
            raise ValueError(f"invalid subcatory for activity: {self.subcatory}")

        if self.category == "gift_shop":
            raise ValueError("subcatory must be null for gift_shop")

        return self


def _extract_ranked_only_candidates(category: str, candidates: dict) -> list[dict]:
    """Extract ranked-only candidates from state, and attach subcatory for downstream search."""
    if not isinstance(candidates, dict):
        return []

    extracted: list[dict] = []

    if category == "restaurant":
        key_to_subcatory = {
            "ranked_breakfast_combos": "breakfast",
            "ranked_lunch_combos": "lunch",
            "ranked_afternoon_tea_combos": "afternoon_tea",
            "ranked_dinner_combos": "dinner",
            "ranked_late_night_combos": "late_night",
        }
        for key, subcatory in key_to_subcatory.items():
            for item in candidates.get(key, []) or []:
                if isinstance(item, dict):
                    extracted.append({**item, "subcatory": subcatory})
        return extracted

    if category == "activity":
        key_to_subcatory = {
            "ranked_light_packages": "light",
            "ranked_packages": "normal",
        }
        for key, subcatory in key_to_subcatory.items():
            for item in candidates.get(key, []) or []:
                if isinstance(item, dict):
                    extracted.append({**item, "subcatory": subcatory})
        return extracted

    for item in candidates.get("ranked_gifts", []) or []:
        if isinstance(item, dict):
            extracted.append({**item})
    return extracted

def _normalize_constraints(raw_constraints: dict | Constraints | None) -> Constraints | None:
    """Normalize raw constraints into a validated Constraints model."""
    if raw_constraints is None:
        return None
    if isinstance(raw_constraints, Constraints):
        return raw_constraints
    if isinstance(raw_constraints, dict):
        try:
            return Constraints(**raw_constraints)
        except Exception as error:
            logger.warning(f"phase=search_candidates | msg=constraints_normalize_failed | error={error}")
    return None


def _build_distance_threshold(preferred_distance: str) -> float:
    """Map preferred distance to a concrete distance threshold in km."""
    if preferred_distance == "<2km":
        return 2.0
    if preferred_distance == "2km-5km":
        return 7.0
    return 10.0


def _get_age_bucket(age: int) -> str | None:
    """Convert a concrete child age into the contracted age bucket."""
    if age < 0:
        return None
    if age <= 6:
        return "3-6"
    if age <= 10:
        return "7-10"
    if age <= 17:
        return "11-17"
    return None

def _prepare_text(item: dict) -> str:
    name = item.get("name", "")
    intro = item.get("description", "") or item.get("intro", "")

    features = item.get("features", "")
    if isinstance(features, list):
        features = " ".join(features)

    tags = item.get("experience_tag", "")
    if isinstance(tags, list):
        tags = " ".join(tags)

    groups = item.get("suitable_groups", [])
    groups_str = " ".join(groups) if isinstance(groups, list) else str(groups)

    child_facilities = item.get("child_facility_tags", [])
    child_facilities_str = (
        " ".join(child_facilities) if isinstance(child_facilities, list) else str(child_facilities)
    )

    age_range = item.get("age_range", [])
    age_range_str = "适合年龄: " + " ".join(age_range) if isinstance(age_range, list) and age_range else ""

    kid_menu_str = "提供儿童餐" if item.get("kid_menu_status") in ("explicit", "possible") else ""
    stroller_str = "婴儿推车友好" if item.get("stroller_friendly_status") in ("yes", "likely") else ""

    gift_type = item.get("gift_type", "")

    parts = [
        name,
        intro,
        features,
        tags,
        groups_str,
        child_facilities_str,
        age_range_str,
        kid_menu_str,
        stroller_str,
        gift_type,
    ]
    return " ".join([part for part in parts if part]).strip()


def _expand_keyword(keyword: str) -> list[str]:
    """Expand user-facing keywords into retrieval-friendly synonyms."""
    normalized = (keyword or "").strip()
    if not normalized:
        return []

    expansion_map = {
        "儿童设施": ["儿童", "亲子", "儿童乐园", "儿童区", "儿童座椅", "宝宝椅", "儿童餐"],
        "儿童": ["儿童", "亲子", "带娃", "宝宝椅", "儿童乐园", "儿童区", "儿童餐"],
        "亲子": ["亲子", "儿童", "家庭", "带娃"],
        "清淡": ["清淡", "健康", "轻食"],
        "活动": ["活动", "体验", "玩乐"],
        "礼物": ["礼物", "蛋糕", "鲜花", "惊喜"],
    }
    return [normalized, *expansion_map.get(normalized, [])]


def _extract_raw_keywords(user_request: str) -> list[str]:
    """Extract raw query keywords from the user's request."""
    raw_keywords = [w.strip() for w in user_request.split() if w.strip()]
    if len(raw_keywords) <= 1:
        raw_keywords = [w.strip() for w in jieba.lcut_for_search(user_request) if w.strip()]
    if not raw_keywords and user_request.strip():
        raw_keywords = [user_request.strip()]
    return raw_keywords


def _normalize_negative_target(keyword: str) -> str:
    """Normalize a negative target parsed from the query."""
    normalized = (keyword or "").strip(" ，,。.!！?？")
    if normalized.endswith("的"):
        normalized = normalized[:-1]
    return normalized


def _extract_negative_target(keyword: str) -> str | None:
    """Extract the target term from a negated query token."""
    normalized = (keyword or "").strip()
    negative_prefixes = ("不要", "别要", "别", "不想", "排除", "去掉", "避开", "不吃")
    for prefix in negative_prefixes:
        if normalized.startswith(prefix):
            target = _normalize_negative_target(normalized[len(prefix) :])
            return target or None
    return None


def _expand_negative_keyword(keyword: str) -> list[str]:
    """Expand a negative keyword into concrete exclusion terms."""
    normalized = _normalize_negative_target(keyword)
    if not normalized:
        return []
    return [normalized, *DIETARY_RESTRICTION_KEYWORDS.get(normalized, [])]


def _constraint_keywords(constraints: Constraints | None, category: str) -> list[str]:
    """Derive implicit retrieval keywords from current constraints."""
    if constraints is None:
        return []

    keywords: list[str] = []
    is_family = constraints.group_type == "family" or (constraints.child_count or 0) > 0
    if is_family:
        keywords.extend(["亲子", "家庭", "儿童"])
    elif constraints.group_type == "friends":
        keywords.extend(["朋友", "聚会"])

    if category == "restaurant":
        if is_family:
            keywords.extend(["宝宝椅", "儿童餐", "儿童乐园"])
    elif category == "activity" and (constraints.child_count or 0) > 0:
        keywords.extend(["亲子活动", "儿童体验"])
    elif category == "gift_shop" and constraints.include_gift:
        keywords.extend(["礼物", "惊喜"])

    dietary_map = {
        "辣": ["清淡", "健康"],
        "海鲜": ["非海鲜"],
        "生冷": ["热食", "熟食"],
        "甜": ["低糖", "清爽"],
        "快餐": ["正餐", "健康"],
        "垃圾食品": ["正餐", "健康"],
        "牛": ["非牛肉"],
    }
    for restriction in constraints.dietary_restrictions:
        keywords.extend(dietary_map.get(restriction, []))

    return keywords


def _build_search_keywords(
    user_request: str,
    constraints: Constraints | None,
    category: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Build explicit and inherited keywords for scoring."""
    raw_keywords = _extract_raw_keywords(user_request)
    explicit_keywords: list[str] = []
    negative_terms: list[str] = []
    for keyword in raw_keywords:
        negative_target = _extract_negative_target(keyword)
        if negative_target:
            negative_terms.append(negative_target)
            continue
        explicit_keywords.append(keyword)

    inherited_keywords = _constraint_keywords(constraints, category)

    expanded_explicit: list[str] = []
    for keyword in explicit_keywords:
        expanded_explicit.extend(_expand_keyword(keyword))

    expanded_inherited: list[str] = []
    for keyword in inherited_keywords:
        expanded_inherited.extend(_expand_keyword(keyword))

    expanded_negative: list[str] = []
    for keyword in negative_terms:
        expanded_negative.extend(_expand_negative_keyword(keyword))

    def _deduplicate(items: list[str]) -> list[str]:
        seen: set[str] = set()
        deduplicated: list[str] = []
        for item in items:
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduplicated.append(normalized)
        return deduplicated

    return (
        _deduplicate(expanded_explicit),
        _deduplicate(expanded_inherited),
        _deduplicate(expanded_negative),
        _deduplicate(negative_terms),
    )


def _deduplicate_items(items: list[dict]) -> list[dict]:
    """Remove duplicate candidates while preserving the original order."""
    seen_ids: set[str] = set()
    deduplicated: list[dict] = []
    for item in items:
        item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id") or "")
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        deduplicated.append(item)
    return deduplicated


def _flatten_restaurants(restaurants: list[dict]) -> list[dict]:
    """Flatten restaurant combos into searchable candidate items."""
    flattened: list[dict] = []
    for restaurant in restaurants or []:
        for combo in restaurant.get("combos", []) or []:
            flattened.append(
                {
                    **combo,
                    "combo_id": combo.get("combo_id") or combo.get("id"),
                    "restaurant_id": restaurant.get("id"),
                    "restaurant_name": restaurant.get("name"),
                    "distance_km": restaurant.get("distance_km"),
                    "tags": restaurant.get("tags", []),
                    "suitable_groups": restaurant.get("suitable_groups", []),
                    "experience_tag": restaurant.get("experience_tag", []),
                    "district": restaurant.get("district"),
                    "address": restaurant.get("address"),
                    "latitude": restaurant.get("latitude"),
                    "longitude": restaurant.get("longitude"),
                    "location": restaurant.get("location"),
                    "kid_menu_status": restaurant.get("kid_menu_status"),
                    "stroller_friendly_status": restaurant.get("stroller_friendly_status"),
                    "child_facility_tags": restaurant.get("child_facility_tags", []),
                    "child_friendly_score_derived": restaurant.get("child_friendly_score_derived"),
                    "type": "restaurant",
                    "category": "restaurant",
                }
            )
    return flattened


def _flatten_activities(activities: list[dict]) -> list[dict]:
    """Flatten activity packages into searchable candidate items."""
    flattened: list[dict] = []
    for activity in activities or []:
        for package in activity.get("packages", []) or []:
            flattened.append(
                {
                    **package,
                    "package_id": package.get("package_id") or package.get("id"),
                    "venue_id": activity.get("id"),
                    "venue_name": activity.get("name"),
                    "distance_km": activity.get("distance_km"),
                    "tags": activity.get("tags", []),
                    "suitable_groups": activity.get("suitable_groups", []),
                    "age_range": activity.get("age_range", []),
                    "experience_tag": activity.get("experience_tag", []),
                    "district": activity.get("district"),
                    "address": activity.get("address"),
                    "latitude": activity.get("latitude"),
                    "longitude": activity.get("longitude"),
                    "location": activity.get("location"),
                    "type": "activity",
                    "category": "activity",
                }
            )
    return flattened


def _flatten_gifts(gifts: list[dict]) -> list[dict]:
    """Flatten gift items into searchable candidate items."""
    flattened: list[dict] = []
    for gift_shop in gifts or []:
        for gift in gift_shop.get("gifts", []) or []:
            flattened.append(
                {
                    **gift,
                    "gift_id": gift.get("gift_id") or gift.get("id"),
                    "shop_id": gift_shop.get("id"),
                    "shop_name": gift_shop.get("name"),
                    "distance_km": gift_shop.get("distance_km"),
                    "delivery_radius_km": gift_shop.get("delivery_radius_km"),
                    "tags": gift_shop.get("tags", []),
                    "suitable_groups": gift_shop.get("suitable_groups", []),
                    "experience_tag": gift_shop.get("experience_tag", []),
                    "gift_type": gift_shop.get("gift_type"),
                    "delivery_to_restaurant": gift_shop.get("delivery_to_restaurant"),
                    "surprise_score_derived": gift_shop.get("surprise_score_derived"),
                    "district": gift_shop.get("district"),
                    "address": gift_shop.get("address"),
                    "latitude": gift_shop.get("latitude"),
                    "longitude": gift_shop.get("longitude"),
                    "location": gift_shop.get("location"),
                    "type": "gift_shop",
                    "category": "gift_shop",
                }
            )
    return flattened


def _load_state_candidates(state_candidates: dict, category: str) -> list[dict]:
    """Load current-round searchable items from state candidates."""
    if category == "restaurant":
        ranked_items = (
            list(state_candidates.get("ranked_breakfast_combos", []) or [])
            + list(state_candidates.get("ranked_lunch_combos", []) or [])
            + list(state_candidates.get("ranked_afternoon_tea_combos", []) or [])
            + list(state_candidates.get("ranked_dinner_combos", []) or [])
            + list(state_candidates.get("ranked_late_night_combos", []) or [])
        )
        if ranked_items:
            return _deduplicate_items(ranked_items)
        return _deduplicate_items(_flatten_restaurants(list(state_candidates.get("nearby_restaurants", []) or [])))

    if category == "activity":
        ranked_items = list(state_candidates.get("ranked_packages", []) or []) + list(
            state_candidates.get("ranked_light_packages", []) or []
        )
        if ranked_items:
            return _deduplicate_items(ranked_items)
        return _deduplicate_items(_flatten_activities(list(state_candidates.get("nearby_activities", []) or [])))

    ranked_gifts = list(state_candidates.get("ranked_gifts", []) or [])
    if ranked_gifts:
        return _deduplicate_items(ranked_gifts)
    return _deduplicate_items(_flatten_gifts(list(state_candidates.get("nearby_gifts", []) or [])))


def _match_suitable_groups(constraints: Constraints, suitable_groups: list) -> bool:
    """Check whether the candidate's suitable groups match the active constraints."""
    if not isinstance(suitable_groups, list) or not suitable_groups:
        return True

    target_group = "family" if constraints.group_type == "family" or (constraints.child_count or 0) > 0 else constraints.group_type
    family_keywords = ("family", "家庭", "亲子", "带娃", "儿童", "三口之家", "宝宝", "老少皆宜")
    friends_keywords = ("friends", "朋友", "情侣", "约会", "聚会", "同事", "闺蜜", "兄弟", "年轻")
    keyword_map = {
        "family": family_keywords,
        "friends": friends_keywords,
    }
    group_keywords = keyword_map.get(target_group, ())

    for group in suitable_groups:
        if not isinstance(group, str):
            continue
        if target_group in group:
            return True
        if any(keyword in group for keyword in group_keywords):
            return True
    return False


def _hit_dietary_restriction(item: dict, constraints: Constraints, prepared_text: str) -> bool:
    """Check whether the candidate conflicts with dietary restrictions."""
    if not constraints.dietary_restrictions:
        return False

    tags = " ".join(item.get("tags", []) or [])
    searchable_text = f"{prepared_text} {tags}"

    for restriction in constraints.dietary_restrictions:
        for keyword in DIETARY_RESTRICTION_KEYWORDS.get(restriction, []):
            if keyword in searchable_text:
                return True
    return False


def _hit_negative_keyword(item: dict, prepared_text: str, negative_keywords: list[str]) -> bool:
    """Check whether the candidate violates negative terms from the query."""
    if not negative_keywords:
        return False

    tags = " ".join(item.get("tags", []) or [])
    searchable_text = f"{prepared_text} {tags}"
    return any(keyword and keyword in searchable_text for keyword in negative_keywords)


def _match_constraints(category: str, item: dict, constraints: Constraints | None, prepared_text: str) -> bool:
    """Apply lightweight rule checks so search inherits current constraints."""
    if constraints is None:
        return True

    if not _match_suitable_groups(constraints, item.get("suitable_groups", [])):
        return False

    price = item.get("price")
    if isinstance(price, (int, float)):
        max_ratio = 0.3 if category == "gift_shop" else 0.7
        if float(price) > float(constraints.budget) * max_ratio:
            return False

    distance_km = item.get("distance_km")
    if isinstance(distance_km, (int, float)):
        if float(distance_km) > _build_distance_threshold(constraints.preferred_distance):
            return False

    if category == "activity" and (constraints.child_count or 0) > 0:
        age_ranges = item.get("age_range")
        if isinstance(age_ranges, list) and age_ranges:
            for _, age in constraints.child_profiles or []:
                if not isinstance(age, int):
                    continue
                bucket = _get_age_bucket(age)
                if bucket and bucket not in age_ranges:
                    return False

    if _hit_dietary_restriction(item, constraints, prepared_text):
        return False

    return True


def _build_hit_reasons(
    prepared_text: str,
    explicit_keywords: list[str],
    inherited_keywords: list[str],
    negative_terms: list[str],
) -> list[str]:
    """Build concise hit reasons for the returned candidate."""
    reasons: list[str] = []

    for keyword in explicit_keywords:
        if keyword and keyword in prepared_text:
            reasons.append(f"显式关键词命中: {keyword}")
            if len(reasons) >= 2:
                break

    inherited_hits = 0
    for keyword in inherited_keywords:
        if keyword and keyword in prepared_text:
            reasons.append(f"继承约束命中: {keyword}")
            inherited_hits += 1
            if inherited_hits >= 2:
                break

    if negative_terms:
        reasons.append(f"已避开排除词: {', '.join(negative_terms)}")

    deduplicated: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            deduplicated.append(reason)
    return deduplicated


def _score_item(
    item: dict,
    prepared_text: str,
    explicit_keywords: list[str],
    inherited_keywords: list[str],
) -> float:
    """Score a candidate by keyword hit count plus lightweight ranking hints."""
    score = float(item.get("score", 0.0) or 0.0)

    for keyword in explicit_keywords:
        if keyword and keyword in prepared_text:
            score += 3.0

    for keyword in inherited_keywords:
        if keyword and keyword in prepared_text:
            score += 1.0

    child_facilities = " ".join(item.get("child_facility_tags", []) or [])
    if "儿童" in "".join(explicit_keywords) and child_facilities:
        score += 2.0

    distance_km = item.get("distance_km")
    if isinstance(distance_km, (int, float)):
        score += max(0.0, 1.5 - min(float(distance_km), 1.5))

    return score


def _search_from_source(
    *,
    category: str,
    user_request: str,
    constraints: Constraints | None,
    source_items: list[dict],
    top_k: int,
) -> list[dict]:
    """Run keyword plus rule-based search over an in-memory candidate list."""
    explicit_keywords, inherited_keywords, negative_keywords, negative_terms = _build_search_keywords(
        user_request, constraints, category
    )
    scored_items: list[tuple[float, dict]] = []

    for item in source_items:
        prepared_text = _prepare_text(item)
        if not prepared_text:
            prepared_text = " ".join(
                [
                    str(item.get("name", "") or ""),
                    str(item.get("description", "") or ""),
                    str(item.get("features", "") or ""),
                    " ".join(item.get("tags", []) or []),
                ]
            ).strip()

        if not _match_constraints(category, item, constraints, prepared_text):
            continue

        if _hit_negative_keyword(item, prepared_text, negative_keywords):
            continue

        item_score = _score_item(item, prepared_text, explicit_keywords, inherited_keywords)
        if item_score > 0:
            scored_items.append(
                (
                    item_score,
                    {
                        **item,
                        "hit_reasons": _build_hit_reasons(
                            prepared_text,
                            explicit_keywords,
                            inherited_keywords,
                            negative_terms,
                        ),
                    },
                )
            )

    scored_items.sort(
        key=lambda pair: (
            pair[0],
            float(pair[1].get("score", 0.0) or 0.0),
            -float(pair[1].get("distance_km", 999.0) or 999.0),
        ),
        reverse=True,
    )
    return [item for _, item in scored_items[:top_k]]

@tool(args_schema=SearchCandidatesInput)
def search_candidates(
    category: Literal["restaurant", "activity", "gift_shop"],
    user_request: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config: RunnableConfig,
    subcatory: (
        Literal[
            "breakfast",
            "lunch",
            "afternoon_tea",
            "dinner",
            "late_night",
            "light",
            "normal",
        ]
        | None
    ) = None,
    top_k: int = 5,
) -> Command:
    """Search candidates by delegating to the external search service."""
    config_app = get_config()
    LoggerManager.setup(config_app)
    session_id = config.get("configurable", {}).get("thread_id", "default")
    tool_http_timeout_secs = float(getattr(config_app, "TOOL_HTTP_TIMEOUT_SECS", 3.0))
    logger.info(
        f"phase=search_candidates | category={category} | query={user_request} | top_k={top_k} | session_id={session_id} | subcatory={subcatory}"
    )

    state_candidates = state.get("candidates", {}) or {}
    ranked_candidates = _extract_ranked_only_candidates(category, state_candidates)
    if subcatory:
        ranked_candidates = [item for item in ranked_candidates if item.get("subcatory") == subcatory]

    logger.info(
        f"phase=search_candidates | msg=search_sub_request | category={category} | count={len(ranked_candidates)} | session_id={session_id} | subcatory={subcatory}"
    )
    if not ranked_candidates:
        logger.warning(
            f"phase=search_candidates | msg=candidate_pool_empty | category={category} | session_id={session_id} | subcatory={subcatory}"
        )

    configured_url = getattr(config_app, "SEARCH_SUB_API_URL", "http://127.0.0.1:8002/search")
    payload = {
        "session_id": session_id,
        "category": category,
        "user_request": user_request,
        "subcatory": subcatory,
        "top_k": top_k,
        "candidates": ranked_candidates,
    }

    try:
        with httpx.Client(timeout=tool_http_timeout_secs, trust_env=False, proxy=None) as client:
            response = client.post(configured_url, json=payload)
            response.raise_for_status()
            res_json = response.json()
    except httpx.TimeoutException as error:
        logger.error(f"phase=search_candidates | msg=search_sub_timeout | error={error}")
        fail_msg = ToolMessage(
            content=json.dumps(
                {
                    "tool": "search_candidates",
                    "status": "timeout",
                    "result": {
                        "error": "搜索服务超时",
                        "code": "TOOL_TIMEOUT",
                        "recoverable": True,
                        "detail": "搜索服务暂时不可用，请稍后重试，或改用重新规划。",
                    },
                },
                ensure_ascii=False,
            ),
            tool_call_id=tool_call_id,
        )
        return Command(update={"messages": [fail_msg]})
    except Exception as error:
        logger.error(f"phase=search_candidates | msg=search_sub_failed | error={error}")
        fail_msg = ToolMessage(
            content=json.dumps(
                {
                    "tool": "search_candidates",
                    "status": "failed",
                    "result": {
                        "error": "搜索服务不可用",
                        "code": "UPSTREAM_ERROR",
                        "recoverable": True,
                        "detail": "搜索服务暂时不可用，请稍后重试，或改用重新规划。",
                    },
                },
                ensure_ascii=False,
            ),
            tool_call_id=tool_call_id,
        )
        return Command(update={"messages": [fail_msg]})

    results = []
    if isinstance(res_json, dict):
        if isinstance(res_json.get("results"), list):
            results = res_json.get("results") or []
        elif isinstance(res_json.get("result"), dict) and isinstance(res_json.get("result", {}).get("results"), list):
            results = res_json.get("result", {}).get("results") or []

    if not results:
        logger.info(
            f"phase=search_candidates | msg=query_no_match | category={category} | query={user_request} "
            f"| session_id={session_id} | subcatory={subcatory} | candidate_count={len(ranked_candidates)}"
        )
        fail_msg = ToolMessage(
            content=json.dumps(
                {
                    "error": "没有找到结果",
                    "detail": "当前候选池里没有符合条件的结果，请尝试换一个搜索词、放宽限制，或者重新规划。",
                },
                ensure_ascii=False,
            ),
            tool_call_id=tool_call_id,
        )
        return Command(
            update={
                "candidates": state.get("candidates", {}),
                "messages": [fail_msg],
            }
        )
    
    simplified_results = []
    for item in results:
        item_id = item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id")
        name = item.get("name")
        price = item.get("price")
        duration_mins = item.get("duration_mins") or item.get("receive_duration_mins")
        features = item.get("features")
        description = item.get("description")
        
        # 将影响 Agent 判断的关键字段也吐回去
        child_facilities = item.get("child_facility_tags", [])
        suitable_groups = item.get("suitable_groups", [])
        kid_menu_status = item.get("kid_menu_status")
        stroller_friendly_status = item.get("stroller_friendly_status")
        hit_reasons = item.get("hit_reasons", [])
        returned_subcatory = item.get("subcatory")
        
        simplified_results.append({
            "id": str(item_id),
            "name": name,
            "price": price,
            "duration_mins": duration_mins,
            "features": features,
            "description": description,
            "child_facilities": child_facilities,
            "suitable_groups": suitable_groups,
            "kid_menu_status": kid_menu_status,
            "stroller_friendly_status": stroller_friendly_status,
            "hit_reasons": hit_reasons,
            "subcatory": returned_subcatory,
        })

    logger.info(
        f"phase=search_candidates | msg=search_completed | found={len(simplified_results)} | candidate_count={len(ranked_candidates)}"
    )
    
    result_data = {
        "results": simplified_results,
        "total_returned": len(simplified_results)
    }

    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "search_candidates",
            "status": "success",
            "result": result_data,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )

    update = {
        "current_step": "search_candidates",
        "messages": [transfer_message],
    }

    return Command(update=update)
