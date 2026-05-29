import os
import json
import math
import random
import re
import sys
from typing import List, Dict, Any, Optional

from scripts.mock_data.constants import *
from scripts.mock_data.constants import _ensure_people_expr_in_name, _infer_default_people_expr_for_combo, _render_sectionalized_description, _render_sections
def _dedupe_str_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        v = value.strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _matched_keywords(review_keywords: list[str], patterns: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for keyword in review_keywords or []:
        if not isinstance(keyword, str):
            continue
        if any(p in keyword for p in patterns):
            matches.append(keyword)
    return _dedupe_str_list(matches)


def _clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def _build_derived_score(*, score: float, confidence: float, sub_category: str, matched_review_keywords: list[str], rule: str) -> dict[str, Any]:
    return {
        "score": round(_clamp(score, 0.0, 5.0), 2),
        "confidence": round(_clamp(confidence, 0.0, 1.0), 2),
        "source": {
            "sub_category": sub_category,
            "matched_review_keywords": _dedupe_str_list(matched_review_keywords),
            "rule": rule,
        },
    }


def _derive_suitable_groups(*, category: str, sub_category: str, tags: list[str], review_keywords: list[str]) -> list[str]:
    text = " ".join([sub_category] + list(tags or []) + list(review_keywords or []))
    groups: list[str] = []
    if any(k in text for k in ("亲子", "儿童", "家庭", "乐园", "绘本", "商场儿童友好", "DIY", "玩具")):
        groups.append("family")
    if any(k in text for k in ("聚会", "热闹", "桌游", "KTV", "烤肉", "火锅", "剧本杀", "密室", "朋友")):
        groups.append("friends")

    if not groups:
        groups.append("friends")
    return _dedupe_str_list(groups)


def _derive_activity_age_range(*, profile: str, sub_category: str, tags: list[str], review_keywords: list[str]) -> list[str]:
    text = " ".join([profile, sub_category] + list(tags or []) + list(review_keywords or []))
    if any(k in text for k in ("3-6", "3-6岁", "适合3-6岁", "低龄", "绘本", "木偶", "儿童乐园")):
        return ["3-6"]
    if any(k in text for k in ("7-10", "7-10岁", "适合7-10岁", "科技馆", "拼搭", "自然教育", "亲子手工")):
        return ["7-10", "adult"]
    if any(k in text for k in ("11-17", "11-17岁", "适合11-17岁", "VR", "轻恐", "剧本杀", "电玩城", "街机")):
        return ["11-17", "adult"]
    return ["adult"]


def _derive_experience_tags(*, category: str, sub_category: str, tags: list[str], review_keywords: list[str]) -> list[str]:
    text = " ".join([sub_category] + list(tags or []) + list(review_keywords or []))
    experience_tags: list[str] = []
    if any(k in text for k in ("氛围感", "小聚", "纪念日", "景观", "花艺", "鲜花", "巧克力")):
        experience_tags.append("氛围感")
        experience_tags.append("仪式感")
    if any(k in text for k in ("拍照", "出片", "打卡", "夜景", "复古", "甜品", "盲盒")):
        experience_tags.append("适合拍照")
        experience_tags.append("出片率高")
    if any(k in text for k in ("安静", "书店", "咖啡", "展览", "美术馆", "治愈")):
        experience_tags.append("安静")
        experience_tags.append("轻松")
    if any(k in text for k in ("互动", "手作", "DIY", "剧本杀", "密室", "拼搭", "运动")):
        experience_tags.append("互动感强")
    if any(k in text for k in ("亲子", "儿童", "家庭")):
        experience_tags.append("亲子友好")
    if any(k in text for k in ("室内", "商场", "少走路")):
        experience_tags.append("室内兜底")
        experience_tags.append("少走路")
    if any(k in text for k in ("庆生", "蛋糕", "奶茶", "鲜花", "礼盒")):
        experience_tags.append("庆生友好")
        experience_tags.append("惊喜感")
    if any(k in text for k in ("高性价比", "低预算", "低决策成本")):
        experience_tags.append("高性价比")
        experience_tags.append("低决策成本")
    if any(k in text for k in ("展览", "书店", "文创", "美术馆")):
        experience_tags.append("轻文化")

    if category == "gift_shop" and "惊喜感" not in experience_tags:
        experience_tags.append("惊喜感")
    return _dedupe_str_list(experience_tags)[:6]


def _derive_photo_score(*, sub_category: str, review_keywords: list[str]) -> dict[str, Any]:
    base = 1.0
    if any(k in sub_category for k in ("景观", "甜品", "展览", "复古", "花艺", "文创", "盲盒", "潮玩", "美术馆")):
        base = 4.0
    matched = _matched_keywords(review_keywords, ("拍照", "出片", "打卡", "装修", "高级感", "好看"))
    return _build_derived_score(
        score=base + 0.35 * len(matched),
        confidence=0.65 + 0.08 * len(matched),
        sub_category=sub_category,
        matched_review_keywords=matched,
        rule="photo_from_sub_category_and_keywords",
    )


def _derive_onsite_walking_level(*, sub_category: str, review_keywords: list[str], indoor: bool) -> dict[str, Any]:
    base = 2.0
    if any(k in sub_category for k in ("商场儿童友好", "室内儿童乐园", "私人影院", "KTV", "礼品店", "鲜花店", "蛋糕店", "咖啡")):
        base = 1.0
    elif any(k in sub_category for k in ("公园", "综合体", "乐园", "书城", "街区", "观景", "展览")):
        base = 3.5
    if not indoor:
        base += 0.6
    matched = _matched_keywords(review_keywords, ("少走路", "适合散步", "交通方便", "室内"))
    delta = 0.0
    for m in matched:
        if "少走路" in m or "室内" in m:
            delta -= 0.5
        if "散步" in m:
            delta += 0.6
    return _build_derived_score(
        score=base + delta,
        confidence=0.62 + 0.08 * len(matched),
        sub_category=sub_category,
        matched_review_keywords=matched,
        rule="walking_from_sub_category_and_keywords",
    )


def _derive_noise_level(*, sub_category: str, review_keywords: list[str]) -> dict[str, Any]:
    base = 2.0
    if any(k in sub_category for k in ("桌游", "KTV", "电玩城", "火锅", "烤肉", "炸鸡", "乐园", "Livehouse")):
        base = 4.2
    elif any(k in sub_category for k in ("书店", "美术馆", "茶餐厅", "咖啡书房", "文创", "鲜花", "本帮菜", "江浙菜")):
        base = 1.2
    matched = _matched_keywords(review_keywords, ("热闹", "人多", "排队", "安静", "不拥挤"))
    delta = 0.0
    for m in matched:
        if any(k in m for k in ("热闹", "人多", "排队")):
            delta += 0.5
        if any(k in m for k in ("安静", "不拥挤")):
            delta -= 0.6
    return _build_derived_score(
        score=base + delta,
        confidence=0.64 + 0.08 * len(matched),
        sub_category=sub_category,
        matched_review_keywords=matched,
        rule="noise_from_sub_category_and_keywords",
    )


def _derive_profile_fields(*, category: str, profile: str, sub_category: str, tags: list[str], review_keywords: list[str], indoor: bool) -> dict[str, Any]:
    derived = {
        "suitable_groups": _derive_suitable_groups(
            category=category,
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
        ),
        "experience_tag": _derive_experience_tags(
            category=category,
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
        ),
        "photo_score_derived": _derive_photo_score(
            sub_category=sub_category,
            review_keywords=review_keywords,
        ),
        "onsite_walking_level_estimated": _derive_onsite_walking_level(
            sub_category=sub_category,
            review_keywords=review_keywords,
            indoor=indoor,
        ),
        "noise_level_estimated": _derive_noise_level(
            sub_category=sub_category,
            review_keywords=review_keywords,
        ),
    }
    if category == "activity":
        derived["age_range"] = _derive_activity_age_range(
            profile=profile,
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
        )
    return derived


def _ensure_profile_fields(
    *,
    item: dict[str, Any],
    category: str,
    profile: str,
    sub_category: str,
    tags: list[str],
    review_keywords: list[str],
    indoor: bool,
) -> dict[str, Any]:
    derived = _derive_profile_fields(
        category=category,
        profile=profile,
        sub_category=sub_category,
        tags=tags,
        review_keywords=review_keywords,
        indoor=indoor,
    )
    for key, value in derived.items():
        if key not in item or item.get(key) in (None, [], {}):
            item[key] = value
    return item


def _derive_kid_menu_status(*, sub_category: str, tags: list[str], review_keywords: list[str]) -> str:
    text = " ".join([sub_category] + list(tags or []) + list(review_keywords or []))
    if any(k in text for k in ("儿童套餐", "儿童餐", "儿童套餐友好", "亲子餐厅", "儿童友好")):
        return "explicit"
    if any(k in text for k in ("亲子", "儿童", "家庭", "宝宝", "小朋友", "3-6岁", "7-10岁")):
        return "possible"
    if any(k in text for k in ("清吧", "Livehouse", "夜宵", "重口")) and not any(k in text for k in ("亲子", "儿童", "家庭")):
        return "none"
    return "unknown"


def _derive_stroller_friendly_status(
    *, indoor: bool, walking_score: float | None, tags: list[str], review_keywords: list[str]
) -> tuple[str, list[str]]:
    walking = float(walking_score) if isinstance(walking_score, (int, float)) else None
    matched = _matched_keywords(review_keywords, ("少走路", "商场", "室内", "推车", "电梯", "婴儿车"))
    text = " ".join(list(tags or []) + list(review_keywords or []))

    if indoor and walking is not None and walking <= 1.5:
        return "yes", matched
    if indoor and (walking is None or walking <= 3.0) and any(k in text for k in ("少走路", "商场", "室内", "电梯")):
        return "likely", matched
    if (not indoor) and walking is not None and walking >= 3.5:
        return "no", matched
    return "unknown", matched


def _derive_child_facility_tags(
    *,
    sub_category: str,
    tags: list[str],
    review_keywords: list[str],
    indoor: bool,
    walking_score: float | None,
) -> list[str]:
    text = " ".join([sub_category] + list(tags or []) + list(review_keywords or []))
    out: list[str] = []
    if any(k in text for k in ("亲子", "儿童", "宝宝", "家庭")):
        out.append("儿童座椅")
    if any(k in text for k in ("商场", "儿童乐园", "亲子餐厅")):
        out.append("亲子卫生间")
    if any(k in text for k in ("商场", "商场内")):
        out.append("商场内")
    if indoor:
        out.append("室内")
    walking = float(walking_score) if isinstance(walking_score, (int, float)) else None
    if walking is not None and walking <= 1.5:
        out.append("少走路")
    if _matched_keywords(review_keywords, ("少走路",)):
        out.append("少走路")
    return _dedupe_str_list(out)


def _derive_child_friendly_score(
    *,
    sub_category: str,
    tags: list[str],
    review_keywords: list[str],
    kid_menu_status: str,
    stroller_friendly_status: str,
    child_facility_tags: list[str],
    walking_score: float | None,
    noise_score: float | None,
) -> dict[str, Any]:
    base_map = {"explicit": 4.0, "possible": 3.2, "unknown": 2.5, "none": 0.8}
    base = float(base_map.get(kid_menu_status, 2.5))
    base += 0.25 * len(child_facility_tags)

    if stroller_friendly_status == "yes":
        base += 0.35
    elif stroller_friendly_status == "likely":
        base += 0.15
    elif stroller_friendly_status == "no":
        base -= 0.4

    walking = float(walking_score) if isinstance(walking_score, (int, float)) else 2.5
    noise = float(noise_score) if isinstance(noise_score, (int, float)) else 2.5
    base += 0.25 * max(0.0, 2.5 - walking)
    base -= 0.2 * max(0.0, noise - 3.0)

    matched = _matched_keywords(review_keywords, ("亲子", "儿童", "座椅", "宝宝", "家庭", "商场", "少走路", "室内"))
    confidence = 0.55 + 0.08 * len(matched)
    if kid_menu_status in ("explicit", "possible"):
        confidence += 0.08
    if any(k in sub_category for k in ("亲子", "儿童")):
        confidence += 0.06

    return _build_derived_score(
        score=base,
        confidence=confidence,
        sub_category=sub_category,
        matched_review_keywords=matched,
        rule="child_friendly_from_facilities_and_keywords",
    )


def _ensure_restaurant_child_fields(
    *, item: dict[str, Any], sub_category: str, tags: list[str], review_keywords: list[str], indoor: bool
) -> dict[str, Any]:
    if item.get("kid_menu_status") not in ("explicit", "possible", "none", "unknown"):
        item["kid_menu_status"] = _derive_kid_menu_status(
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
        )

    walking_score = None
    noise_score = None
    walking = item.get("onsite_walking_level_estimated")
    if isinstance(walking, dict) and isinstance(walking.get("score"), (int, float)):
        walking_score = float(walking["score"])
    noise = item.get("noise_level_estimated")
    if isinstance(noise, dict) and isinstance(noise.get("score"), (int, float)):
        noise_score = float(noise["score"])

    if item.get("stroller_friendly_status") not in ("yes", "likely", "no", "unknown"):
        stroller_status, _ = _derive_stroller_friendly_status(
            indoor=indoor,
            walking_score=walking_score,
            tags=tags,
            review_keywords=review_keywords,
        )
        item["stroller_friendly_status"] = stroller_status

    if not isinstance(item.get("child_facility_tags"), list):
        item["child_facility_tags"] = _derive_child_facility_tags(
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
            indoor=indoor,
            walking_score=walking_score,
        )

    if not isinstance(item.get("child_friendly_score_derived"), dict):
        item["child_friendly_score_derived"] = _derive_child_friendly_score(
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
            kid_menu_status=str(item.get("kid_menu_status") or "unknown"),
            stroller_friendly_status=str(item.get("stroller_friendly_status") or "unknown"),
            child_facility_tags=list(item.get("child_facility_tags") or []),
            walking_score=walking_score,
            noise_score=noise_score,
        )

    return item


def _derive_gift_type(*, sub_category: str, tags: list[str]) -> str:
    text = " ".join([sub_category] + list(tags or []))
    if any(k in text for k in ("鲜花", "花艺", "永生花", "玫瑰")):
        return "flower"
    if any(k in text for k in ("蛋糕", "甜品", "芝士")):
        return "cake"
    if any(k in text for k in ("玩具", "拼图", "毛绒", "益智")):
        return "toy"
    if any(k in text for k in ("奶茶", "咖啡")):
        return "coffee"
    if any(k in text for k in ("盲盒", "潮玩")):
        return "blind_box"
    if "零食" in text:
        return "snack"
    if any(k in text for k in ("文创", "明信片", "纪念品", "手账", "摆件", "礼品")):
        return "blind_box"
    return "toy"


def _derive_delivery_to_restaurant(*, delivery_time_mins: int | None, gift_type: str) -> bool:
    if not isinstance(delivery_time_mins, int):
        return False
    return gift_type in ("flower", "cake", "coffee")


def _derive_surprise_score(
    *,
    sub_category: str,
    review_keywords: list[str],
    gift_type: str,
    delivery_to_restaurant: bool,
    experience_tag: list[str],
) -> dict[str, Any]:
    base_map = {
        "flower": 4.6,
        "cake": 4.4,
        "coffee": 3.5,
        "toy": 3.2,
        "blind_box": 3.6,
        "snack": 3.0,
    }
    base = float(base_map.get(gift_type, 3.2))
    if delivery_to_restaurant:
        base += 0.4

    exp_text = " ".join(experience_tag or [])
    if any(k in exp_text for k in ("惊喜感", "仪式感", "庆生友好")):
        base += 0.2

    matched = _matched_keywords(review_keywords, ("惊喜", "仪式感", "庆生", "小聚", "氛围"))
    confidence = 0.6 + 0.06 * len(matched) + (0.1 if delivery_to_restaurant else 0.0)
    return _build_derived_score(
        score=base,
        confidence=confidence,
        sub_category=sub_category,
        matched_review_keywords=matched,
        rule="surprise_from_gift_type_and_delivery",
    )


def _ensure_gift_shop_special_fields(
    *, item: dict[str, Any], sub_category: str, tags: list[str], review_keywords: list[str]
) -> dict[str, Any]:
    gift_type = item.get("gift_type")
    if gift_type not in ("flower", "cake", "toy", "snack", "blind_box", "coffee"):
        gift_type = _derive_gift_type(sub_category=sub_category, tags=tags)
        item["gift_type"] = gift_type

    if not isinstance(item.get("delivery_to_restaurant"), bool):
        item["delivery_to_restaurant"] = _derive_delivery_to_restaurant(
            delivery_time_mins=item.get("delivery_time_mins"),
            gift_type=str(item.get("gift_type") or gift_type),
        )

    if not isinstance(item.get("surprise_score_derived"), dict):
        item["surprise_score_derived"] = _derive_surprise_score(
            sub_category=sub_category,
            review_keywords=review_keywords,
            gift_type=str(item.get("gift_type") or gift_type),
            delivery_to_restaurant=bool(item.get("delivery_to_restaurant") is True),
            experience_tag=list(item.get("experience_tag") or []),
        )

    return item


def _pool_items(sub_category: str, section: str) -> list[str]:
    sub = sub_category or ""
    if section in ("锅底",):
        return ["番茄锅", "菌汤锅", "清汤锅", "微辣牛油锅", "猪肚鸡汤底"]
    if section in ("荤菜",):
        if "韩" in sub:
            return ["五花肉", "牛肋条", "辣白菜", "芝士年糕"]
        if "火锅" in sub or "猪肚鸡" in sub:
            return ["肥牛", "虾滑", "毛肚", "午餐肉", "鱼片"]
        if "日式" in sub:
            return ["寿喜牛肉", "鳗鱼", "鸡软骨"]
        return ["红烧肉", "清蒸鱼", "宫保鸡丁", "黑椒牛柳", "香辣小龙虾"]
    if section in ("素菜", "配菜", "小菜"):
        if "日式" in sub:
            return ["温泉蛋", "海带芽", "毛豆", "泡菜"]
        return ["时蔬拼盘", "土豆丝", "拍黄瓜", "凉拌木耳", "烤蔬菜"]
    if section in ("主食",):
        if "日式拉面" in sub or "乌冬" in sub:
            return ["拉面", "乌冬", "米饭", "溏心蛋"]
        if "茶餐厅" in sub:
            return ["菠萝油", "叉烧包", "白饭", "云吞面"]
        return ["米饭", "面食", "炒饭", "馒头"]
    if section in ("汤品",):
        if "本帮" in sub or "江浙" in sub:
            return ["腌笃鲜", "老鸭汤", "菌菇汤"]
        return ["番茄蛋花汤", "冬瓜排骨汤", "紫菜蛋花汤"]
    if section in ("饮品",):
        if "甜品下午茶" in sub or "咖啡" in sub or "Brunch" in sub:
            return ["拿铁", "美式", "气泡水", "柠檬茶"]
        return ["酸梅汤", "柠檬水", "果汁", "热茶"]
    if section in ("甜品",):
        return ["巴斯克蛋糕", "布丁", "提拉米苏", "冰粉"]
    if section in ("小食", "加点"):
        return ["小油条", "薯条", "鸡翅", "沙拉杯"]
    return ["招牌单品", "人气单品", "时令单品"]


def _build_combo(*, sub_category: str, people_expr: str, title_style: str, slots: list[str], is_western: bool) -> dict:
    title = _ensure_people_expr_in_name(f"{title_style}".strip(), default_people_expr=people_expr)
    if not title.strip() or title.strip() == people_expr:
        title = f"{people_expr}招牌套餐"
    if is_western and any(k in title_style for k in ("小聚", "纪念日")):
        title = _ensure_people_expr_in_name(f"{title_style}", default_people_expr=people_expr)

    if any(k in sub_category for k in ("火锅", "猪肚鸡")):
        sections = {
            "锅底": random.sample(_pool_items(sub_category, "锅底"), k=1),
            "荤菜": random.sample(_pool_items(sub_category, "荤菜"), k=3),
            "素菜": random.sample(_pool_items(sub_category, "素菜"), k=2),
            "主食": random.sample(_pool_items(sub_category, "主食"), k=1),
            "饮品": random.sample(_pool_items(sub_category, "饮品"), k=1),
        }
    elif any(k in sub_category for k in ("甜品下午茶", "咖啡", "面包", "烘焙")):
        sections = {
            "饮品": random.sample(_pool_items(sub_category, "饮品"), k=1),
            "甜品": random.sample(_pool_items(sub_category, "甜品"), k=2),
            "小食": random.sample(_pool_items(sub_category, "小食"), k=2),
        }
    elif "日式" in sub_category:
        sections = {
            "主食": random.sample(_pool_items(sub_category, "主食"), k=1),
            "小菜": random.sample(_pool_items(sub_category, "小菜"), k=2),
            "汤品": random.sample(_pool_items(sub_category, "汤品"), k=1),
            "饮品": random.sample(_pool_items(sub_category, "饮品"), k=1),
        }
    elif any(k in sub_category for k in ("西餐", "Brunch")):
        sections = {
            "主菜": random.sample(_pool_items(sub_category, "荤菜"), k=2),
            "配菜": random.sample(_pool_items(sub_category, "配菜"), k=2),
            "饮品": random.sample(_pool_items(sub_category, "饮品"), k=1),
            "甜品": random.sample(_pool_items(sub_category, "甜品"), k=1),
        }
    else:
        sections = {
            "主菜": random.sample(_pool_items(sub_category, "荤菜"), k=2),
            "配菜": random.sample(_pool_items(sub_category, "配菜"), k=2),
            "汤品": random.sample(_pool_items(sub_category, "汤品"), k=1),
            "主食": random.sample(_pool_items(sub_category, "主食"), k=1),
            "饮品": random.sample(_pool_items(sub_category, "饮品"), k=1),
        }

    description = _render_sections(sections)
    features = f"{people_expr}吃得更舒服，搭配更均衡，适合轻松不踩雷。"
    price_base = 48.0
    if "西餐" in sub_category:
        price_base = 168.0
    elif "火锅" in sub_category or "猪肚鸡" in sub_category:
        price_base = 128.0
    elif "东北菜" in sub_category:
        price_base = 98.0
    elif "甜品" in sub_category or "咖啡" in sub_category or "烘焙" in sub_category:
        price_base = 58.0
    elif "融合" in sub_category:
        price_base = 188.0
    elif "韩餐" in sub_category:
        price_base = 138.0

    people_mult = 1.0
    if "2大1小" in people_expr or "三口之家" in people_expr:
        people_mult = 1.8
    elif any(k in people_expr for k in ("四人", "4人")):
        people_mult = 2.6
    elif any(k in people_expr for k in ("六人", "6人")):
        people_mult = 3.6
    elif any(k in people_expr for k in ("双人", "两人", "2人")):
        people_mult = 1.4

    price = float(round(price_base * people_mult + random.uniform(-8.0, 12.0), 2))
    duration_mins = int(60 + random.randint(-10, 40))
    duration_std = float(round(random.choice([10.0, 12.0, 15.0, 20.0]), 1))
    if any(k in sub_category for k in ("甜品下午茶", "咖啡", "面包", "烘焙")):
        duration_mins = int(45 + random.randint(-5, 25))
        duration_std = float(round(random.choice([8.0, 10.0, 12.0, 15.0]), 1))

    return {
        "name": title,
        "price": price,
        "description": description,
        "features": features,
        "duration_mins": duration_mins,
        "duration_std_dev": duration_std,
        "suitable_time_slots": slots,
        "requires_booking": bool(random.random() < 0.12),
    }


