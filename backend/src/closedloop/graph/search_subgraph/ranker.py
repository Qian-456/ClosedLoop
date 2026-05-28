import math
from typing import Any

import jieba
import re

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.search_subgraph.contracts import SearchSubgraphState


_QUERY_DELIMITER_PATTERN = re.compile(r"[,，、\|/;；\t\r\n]+")
_STOPWORDS = {
    "餐厅",
    "餐馆",
    "饭店",
    "活动",
    "礼物",
    "推荐",
    "搜索",
    "附近",
    "一下",
}


def _deduplicate_tokens(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    dedup: list[str] = []
    for token in tokens:
        normalized = (token or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        dedup.append(normalized)
    return dedup


def _filter_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t and t not in _STOPWORDS]


def _normalize_query_text(user_request: str) -> str:
    return _QUERY_DELIMITER_PATTERN.sub(" ", user_request or "").strip()


def _extract_raw_keywords(user_request: str) -> list[str]:
    """从用户输入中抽取关键词 token。"""
    normalized = _normalize_query_text(user_request)
    raw_keywords = _deduplicate_tokens(_filter_stopwords([w.strip() for w in normalized.split() if w.strip()]))
    if len(raw_keywords) <= 1:
        raw_keywords = _deduplicate_tokens(
            _filter_stopwords([w.strip() for w in jieba.lcut_for_search(user_request or "") if w.strip()])
        )
    if not raw_keywords and (user_request or "").strip():
        fallback = normalized or (user_request or "").strip()
        raw_keywords = [fallback] if fallback else []
    return raw_keywords


def _normalize_negative_target(keyword: str) -> str:
    """归一化否定词的目标 token。"""
    normalized = (keyword or "").strip(" ，,。.!！?？")
    if normalized.endswith("的"):
        normalized = normalized[:-1]
    return normalized


def _extract_negative_terms(user_request: str) -> list[str]:
    """从查询里解析否定词。"""
    prefixes = ("不要", "别要", "别", "不想", "排除", "去掉", "避开", "不吃")
    terms: list[str] = []
    normalized_request = (user_request or "").strip()
    for prefix in prefixes:
        if normalized_request.startswith(prefix):
            target = _normalize_negative_target(normalized_request[len(prefix) :])
            if target:
                terms.append(target)
            break
    for token in _extract_raw_keywords(user_request):
        for prefix in prefixes:
            if token.startswith(prefix):
                target = _normalize_negative_target(token[len(prefix) :])
                if target:
                    terms.append(target)
                break
    dedup: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            dedup.append(term)
    return dedup


def _get_item_id(item: dict[str, Any]) -> str:
    """为候选生成稳定 id。"""
    item_id = item.get("id") or item.get("combo_id") or item.get("package_id") or item.get("gift_id")
    return str(item_id or "")


def _build_text_fields(item: dict[str, Any]) -> dict[str, str]:
    """构建用于检索与匹配的字段文本。"""
    name = str(item.get("name") or "")
    merchant_name = str(
        item.get("merchant_name")
        or item.get("restaurant_name")
        or item.get("venue_name")
        or item.get("shop_name")
        or ""
    )
    tags = " ".join([str(x) for x in (item.get("tags") or []) if x is not None])
    features = str(item.get("features") or "")
    description = str(item.get("description") or "")
    review_keywords = " ".join([str(x) for x in (item.get("review_keywords") or []) if x is not None])
    return {
        "name": name,
        "merchant_name": merchant_name,
        "tags": tags,
        "features": features,
        "description": description,
        "review_keywords": review_keywords,
    }


def _build_searchable_text(fields: dict[str, str]) -> str:
    """拼接可搜索文本。"""
    return " ".join([fields.get("name", ""), fields.get("merchant_name", ""), fields.get("tags", ""), fields.get("features", ""), fields.get("description", ""), fields.get("review_keywords", "")]).strip()


def _keyword_score(user_request: str, fields: dict[str, str]) -> tuple[float, list[str]]:
    """计算 keyword_score（封顶 60）。"""
    keywords = _extract_raw_keywords(user_request)
    if not keywords:
        return 0.0, []

    total = 0.0
    reasons: list[str] = []

    for kw in keywords:
        if not kw:
            continue

        score = 0.0
        level = ""
        if kw in fields.get("name", "") or kw in fields.get("merchant_name", ""):
            score = 30.0
            level = "强命中"
        elif kw in fields.get("tags", "") or kw in fields.get("features", ""):
            score = 15.0
            level = "中命中"
        elif kw in fields.get("description", "") or kw in fields.get("review_keywords", ""):
            score = 10.0
            level = "弱命中"

        if score <= 0:
            continue

        total += score
        reasons.append(f"{level}关键词: {kw}")
        if total >= 60.0:
            total = 60.0
            break

    dedup: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            dedup.append(reason)

    return min(total, 60.0), dedup


def _is_family_triggered(user_request: str) -> bool:
    """判断是否触发亲子结构化加分。"""
    triggers = ("亲子", "带娃", "儿童", "宝宝", "家庭", "小朋友")
    return any(t in (user_request or "") for t in triggers)


def _is_quiet_triggered(user_request: str) -> bool:
    """判断是否触发安静结构化加分。"""
    triggers = ("安静", "低噪", "不吵", "安静点", "清静")
    return any(t in (user_request or "") for t in triggers)


def _is_indoor_triggered(user_request: str) -> bool:
    """判断是否触发室内结构化加分。"""
    triggers = ("室内", "下雨", "不晒", "空调", "室内的")
    return any(t in (user_request or "") for t in triggers)


def _hit_family(item: dict[str, Any]) -> bool:
    """判断候选是否满足亲子命中。"""
    child_facility_tags = item.get("child_facility_tags") or []
    if isinstance(child_facility_tags, list) and len(child_facility_tags) > 0:
        return True

    kid_menu_status = str(item.get("kid_menu_status") or "")
    if kid_menu_status in {"available", "partial"}:
        return True

    stroller_friendly_status = str(item.get("stroller_friendly_status") or "")
    if stroller_friendly_status in {"good", "ok"}:
        return True

    return False


def _hit_quiet(item: dict[str, Any], fields: dict[str, str]) -> bool:
    """判断候选是否满足安静命中。"""
    noise = item.get("noise_level_estimated")
    if isinstance(noise, dict):
        level = str(noise.get("level") or noise.get("value") or "").lower()
        if level in {"low", "quiet", "very_low"}:
            return True
    return ("安静" in fields.get("review_keywords", "")) or ("低噪" in fields.get("review_keywords", ""))


def _hit_indoor(item: dict[str, Any]) -> bool:
    """判断候选是否满足室内命中。"""
    return bool(item.get("indoor") is True)


def _field_score(user_request: str, item: dict[str, Any], fields: dict[str, str]) -> tuple[float, list[str]]:
    """计算 field_score（封顶 30）。"""
    total = 0.0
    reasons: list[str] = []

    if _is_family_triggered(user_request) and _hit_family(item):
        total += 20.0
        reasons.append("结构化命中: 亲子")

    if _is_quiet_triggered(user_request) and _hit_quiet(item, fields):
        total += 10.0
        reasons.append("结构化命中: 安静")

    if _is_indoor_triggered(user_request) and _hit_indoor(item):
        total += 10.0
        reasons.append("结构化命中: 室内")

    if total > 30.0:
        total = 30.0

    return total, reasons


def _original_score_bonus(item: dict[str, Any]) -> float:
    """计算 original_score_bonus = clamp(score/10, 0~10)。"""
    score = item.get("score", 0.0)
    try:
        value = float(score or 0.0) / 10.0
    except Exception:
        value = 0.0
    return float(max(0.0, min(10.0, value)))


def _subcatory_bonus(request_subcatory: str | None, item_subcatory: str | None) -> float:
    """计算 subcatory_bonus。"""
    if request_subcatory and item_subcatory and request_subcatory == item_subcatory:
        return 10.0
    return 0.0


def _distance_for_sort(item: dict[str, Any]) -> float:
    """获取距离用于排序（缺省视为 999）。"""
    distance = item.get("distance_km")
    try:
        return float(distance) if distance is not None else 999.0
    except Exception:
        return 999.0


def _price_for_sort(item: dict[str, Any]) -> float:
    """获取价格用于排序（缺省视为 inf）。"""
    price = item.get("price")
    try:
        return float(price) if price is not None else math.inf
    except Exception:
        return math.inf


def _truncate_text(text: str, max_len: int = 120) -> str:
    content = (text or "").strip()
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


def ranked_only_search_node(state: SearchSubgraphState) -> SearchSubgraphState:
    """对扁平候选池执行 ranked-only 站内搜规则，并写回 results。"""
    config = get_config()
    LoggerManager.setup(config)

    session_id = state.get("session_id", "default")
    category = state.get("category", "")
    user_request = state.get("user_request", "") or ""
    request_subcatory = state.get("subcatory")
    top_k = int(state.get("top_k", 5) or 5)
    candidates = list(state.get("candidates", []) or [])

    keywords_preview = _extract_raw_keywords(user_request)[:8]
    logger.info(
        f"phase=search_ranked_only | session_id={session_id} | category={category} | top_k={top_k} | subcatory={request_subcatory} | query={_truncate_text(user_request)} | keywords={keywords_preview} | candidates={len(candidates)}"
    )

    negative_terms = _extract_negative_terms(user_request)

    scored: list[dict[str, Any]] = []
    for raw_item in candidates:
        if not isinstance(raw_item, dict):
            continue

        item = dict(raw_item)
        item_id = _get_item_id(item)
        item["id"] = item_id

        fields = _build_text_fields(item)
        searchable_text = _build_searchable_text(fields)

        if negative_terms and any(term in searchable_text for term in negative_terms if term):
            continue

        keyword_score, keyword_reasons = _keyword_score(user_request, fields)
        field_score, field_reasons = _field_score(user_request, item, fields)
        original_bonus = _original_score_bonus(item)
        sub_bonus = _subcatory_bonus(request_subcatory, item.get("subcatory"))

        final_score = float(keyword_score + field_score + original_bonus + sub_bonus)

        hit_reasons = []
        hit_reasons.extend(keyword_reasons)
        hit_reasons.extend(field_reasons)
        if negative_terms:
            hit_reasons.append(f"已避开排除词: {', '.join(negative_terms)}")

        item.update(
            {
                "keyword_score": float(keyword_score),
                "field_score": float(field_score),
                "original_score_bonus": float(original_bonus),
                "subcatory_bonus": float(sub_bonus),
                "final_score": float(final_score),
                "hit_reasons": hit_reasons,
            }
        )
        scored.append(item)

    scored.sort(
        key=lambda item: (
            -float(item.get("final_score", 0.0) or 0.0),
            -float(item.get("score", 0.0) or 0.0),
            _distance_for_sort(item),
            _price_for_sort(item),
            str(item.get("id") or ""),
        )
    )

    results = scored[: max(0, top_k)]
    logger.info(
        f"phase=search_ranked_only | session_id={session_id} | category={category} | candidates={len(candidates)} | returned={len(results)}"
    )

    state["results"] = results
    return state
