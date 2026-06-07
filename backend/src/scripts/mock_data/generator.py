import os
import json
import math
import random
import re
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.mock_data.constants import *
from scripts.mock_data.constants import (
    _infer_receive_duration_mins,
    _keywords_for_profile,
    _sanitize_mock_dict,
    _sanitize_mock_list,
)
from scripts.mock_data.derivers import *
from scripts.mock_data.derivers import _ensure_profile_fields, _ensure_restaurant_child_fields, _ensure_gift_shop_special_fields, _build_combo
from scripts.mock_data.reservations import generate_reservations_from_mock_db
def generate_mock_db() -> dict[str, Any]:
    hubs = generate_hub_locations()
    hub_names = list(hubs.keys())
    
    mock_db = {
        "restaurants": [],
        "activity_venues": [],
        "gift_shops": []
    }
    
    def _is_strict_afternoon_tea_restaurant(sub_category: str) -> bool:
        s = str(sub_category or "")
        return any(k in s for k in ("甜品", "下午茶", "咖啡", "奶茶", "烘焙", "面包"))

    restaurant_plan: list[dict] = (
        [
            {"sub_category": "粤菜", "name": "点都德", "profile": "family_mild", "tags": ["少辣", "家庭", "亲子"]},
            {"sub_category": "茶餐厅", "name": "莲香茶餐厅", "profile": "family_mild", "tags": ["少辣", "家庭", "单人"]},
            {"sub_category": "粤菜", "name": "翠华茶餐厅", "profile": "family_mild", "tags": ["少辣", "家庭", "兜底"]},
            {"sub_category": "江浙菜", "name": "外婆家", "profile": "family_mild", "tags": ["少辣", "家庭", "安静"]},
            {"sub_category": "本帮菜", "name": "老上海本帮菜馆", "profile": "family_mild", "tags": ["少辣", "家庭", "安静约会"]},
            {"sub_category": "江浙菜", "name": "苏浙小馆", "profile": "family_mild", "tags": ["少辣", "家庭", "安静"]},
            {"sub_category": "家常菜", "name": "社区家常小馆", "profile": "family_mild", "tags": ["低预算", "家庭", "单人"]},
            {"sub_category": "社区小馆", "name": "街角社区小馆", "profile": "family_mild", "tags": ["低预算", "家庭", "兜底"]},
            {"sub_category": "连锁简餐", "name": "和府捞面·家庭简餐", "profile": "family_mild", "tags": ["亲子", "少走路", "兜底"]},
            {"sub_category": "商场家庭餐厅", "name": "商场家庭餐厅·轻简餐", "profile": "family_mild", "tags": ["亲子", "少走路", "室内"]},
            {"sub_category": "西餐", "name": "王品牛排", "profile": "friends_lively", "tags": ["纪念日", "情侣", "安静"]},
            {"sub_category": "西餐", "name": "蓝蛙西餐厅", "profile": "friends_lively", "tags": ["意面", "牛排", "约会"]},
            {"sub_category": "Brunch", "name": "Brunch Lab", "profile": "friends_lively", "tags": ["轻食", "下午约会", "拍照"]},
            {"sub_category": "景观餐厅", "name": "云顶露台景观餐厅", "profile": "friends_lively", "tags": ["拍照", "夜景", "浪漫"]},
            {"sub_category": "甜品下午茶", "name": "甜里·下午茶", "profile": "friends_lively", "tags": ["女生友好", "拍照", "甜品"]},
            {"sub_category": "日式定食", "name": "和风寿喜锅定食", "profile": "friends_lively", "tags": ["少辣", "安静", "约会"]},
            {"sub_category": "融合菜", "name": "融·精致融合菜", "profile": "friends_lively", "tags": ["高体验", "出片", "预约"]},
            {"sub_category": "东北菜", "name": "老四季东北菜", "profile": "friends_lively", "tags": ["多人", "高性价比", "热闹"]},
            {"sub_category": "东北菜", "name": "东北大板·家常东北菜", "profile": "friends_lively", "tags": ["多人", "高性价比", "热闹"]},
            {"sub_category": "韩餐烤肉", "name": "韩宫烤肉", "profile": "friends_lively", "tags": ["朋友", "热闹", "烤肉"]},
            {"sub_category": "披萨炸鸡", "name": "炸鸡汉堡社", "profile": "friends_lively", "tags": ["朋友", "年轻人", "低决策成本"]},
            {"sub_category": "火锅", "name": "串串小馆·清汤可选", "profile": "friends_lively", "tags": ["热闹", "可选微辣", "不辣锅"]},
            {"sub_category": "烤鱼", "name": "夜猫子烤鱼", "profile": "friends_lively", "tags": ["夜间", "聚会", "热闹"]},
            {"sub_category": "猪肚鸡", "name": "粤式打边炉·猪肚鸡", "profile": "friends_lively", "tags": ["少辣替代火锅", "聚餐", "温和"]},
            {"sub_category": "亲子餐厅", "name": "小象亲子餐厅", "profile": "kids_friendly", "tags": ["3-8岁", "亲子", "儿童"]},
            {"sub_category": "儿童套餐友好", "name": "儿童套餐友好餐厅", "profile": "kids_friendly", "tags": ["3-10岁", "亲子", "清淡"]},
            {"sub_category": "商场儿童友好", "name": "商场儿童友好餐厅", "profile": "kids_friendly", "tags": ["少走路", "室内", "亲子"]},
            {"sub_category": "烘焙轻食亲子", "name": "烘焙轻食亲子餐厅", "profile": "kids_friendly", "tags": ["下午茶", "轻食", "亲子"]},
            {"sub_category": "咖啡简餐", "name": "漫咖啡·简餐", "profile": "family_mild", "tags": ["轻量", "放松", "安静"]},
            {"sub_category": "日式拉面乌冬", "name": "一乐拉面·乌冬", "profile": "family_mild", "tags": ["单人", "快速", "少辣"]},
            {"sub_category": "面包烘焙简餐", "name": "面包研究所·烘焙简餐", "profile": "family_mild", "tags": ["下午轻食", "单人", "烘焙"]},
            {"sub_category": "粉面饭轻餐", "name": "粉面小铺", "profile": "family_mild", "tags": ["预算低", "时间短", "单人"]},
        ]
    )

    for i, plan in enumerate(restaurant_plan):
        sub_category = plan["sub_category"]
        district = random.choice(hub_names)
        hub_x, hub_y = hubs[district]
        loc = generate_location_near_hub(hub_x, hub_y, district)
        business_hours = random.choice(["10:00-22:00", "11:00-22:30", "09:30-21:30"])
        indoor = False if sub_category in ("景观餐厅",) else True
        tags = _sanitize_mock_list(list(plan.get("tags") or []))
        review_keywords = _sanitize_mock_list(_keywords_for_profile(
            category="restaurant",
            profile=str(plan["profile"]),
            indoor=bool(indoor),
            sub_category=sub_category,
            delivery_supported=False,
        ))
        combos: list[dict] = []
        is_western = sub_category == "西餐"

        def _build_low_price_combo(*, people_expr: str, title_style: str, slots: list[str]) -> dict:
            c = _build_combo(
                sub_category=sub_category,
                people_expr=people_expr,
                title_style=title_style,
                slots=slots,
                is_western=is_western,
            )
            c["price"] = float(round(random.uniform(28.0, 58.0), 2))
            if c.get("duration_mins", 60) > 90:
                c["duration_mins"] = int(max(60, int(c.get("duration_mins") or 60) - 20))
            return c

        if _is_strict_afternoon_tea_restaurant(sub_category):
            combos += [
                _build_combo(sub_category=sub_category, people_expr="1人", title_style="1人咖啡+甜点组合", slots=["afternoon_tea"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人下午茶甜点拼盘", slots=["afternoon_tea"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="2大1小亲子下午茶点心", slots=["afternoon_tea"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人下午茶分享拼盘", slots=["afternoon_tea"], is_western=is_western),
                _build_low_price_combo(people_expr="双人", title_style="双人下午茶性价比套餐", slots=["afternoon_tea"]),
            ]
        elif plan["profile"] == "family_mild":
            combos += [
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人清淡分享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="2大1小家庭套餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人家庭聚餐", slots=["dinner"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人家常共享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2大2小", title_style="2大2小家庭聚餐", slots=["lunch", "dinner"], is_western=is_western),
            ]
        elif plan["profile"] == "couple_photo" or plan["profile"] == "solo_light":
            # These are legacy profiles, now mapped to family or friends in tags
            combos += [
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人推荐餐", slots=["dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人分享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="六人", title_style="六人聚会餐", slots=["lunch"], is_western=is_western),
            ]
            combos += [
                _build_low_price_combo(people_expr="2-4人", title_style="2-4人小份共享", slots=["dinner"]),
                _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="家庭套餐", slots=["dinner"], is_western=is_western),
            ]
        elif plan["profile"] == "friends_lively":
            combos += [
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人欢聚畅吃餐", slots=["dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人高性价比聚会餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="六人", title_style="六人热闹派对餐", slots=["dinner", "late_night"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人共享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_low_price_combo(people_expr="3-5人", title_style="3-5人平价便饭", slots=["lunch", "dinner", "late_night"]),
            ]
        elif plan["profile"] == "kids_friendly":
            combos += [
                _build_combo(sub_category=sub_category, people_expr="1大1小", title_style="1大1小儿童友好套餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="2大1小亲子家庭餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人亲友分享餐", slots=["dinner"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人家庭共享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_low_price_combo(people_expr="2大1小", title_style="2大1小家常便饭", slots=["lunch", "dinner"]),
            ]
        else:
            combos += [
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人分享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人随享套餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人随享轻食", slots=["lunch", "dinner"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人共享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_low_price_combo(people_expr="3-5人", title_style="3-5人平价便饭", slots=["lunch", "dinner"]),
            ]

        if len(combos) != 5:
            combos = combos[:5]

        restaurant = {
            "id": f"restaurant_{i+1:03d}",
            "name": f"{plan['name']}({district})",
            "category": "restaurant",
            "sub_category": sub_category,
            "district": district,
            "address": loc["address"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "business_hours": business_hours,
            "indoor": bool(indoor),
            "review_keywords": review_keywords,
            "rating": float(round(random.uniform(4.2, 5.0), 1)),
            "combos": [
                {
                    "combo_id": f"combo_{i+1:03d}_{j+1}",
                    "name": c["name"],
                    "price": c["price"],
                    "description": c["description"],
                    "features": c["features"],
                    "duration_mins": c["duration_mins"],
                    "duration_std_dev": c["duration_std_dev"],
                    "suitable_time_slots": c["suitable_time_slots"],
                    "requires_booking": bool(c.get("requires_booking") is True),
                }
                for j, c in enumerate(combos)
            ],
            "tags": tags,
        }
        for combo in restaurant["combos"]:
            if combo.get("combo_id") in DEMO_FULL_COMBO_IDS or combo.get("combo_id") in DEMO_BACKUP_COMBO_IDS:
                combo["requires_booking"] = True
        restaurant = _ensure_profile_fields(
            item=restaurant,
            category="restaurant",
            profile=str(plan["profile"]),
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
            indoor=bool(indoor),
        )
        restaurant = _ensure_restaurant_child_fields(
            item=restaurant,
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
            indoor=bool(indoor),
        )
        mock_db["restaurants"].append(_sanitize_mock_dict(restaurant))
        
    activity_plan: list[dict] = (
        [
            {"sub_category": "独立书店", "name": "纸上时光·独立书店", "profile": "family_mild", "indoor": True, "is_free": True, "tags": ["安静", "低预算"]},
            {"sub_category": "独立书店", "name": "巷口书店", "profile": "family_mild", "indoor": True, "is_free": True, "tags": ["安静", "低预算"]},
            {"sub_category": "咖啡书房", "name": "静读咖啡书房", "profile": "family_mild", "indoor": True, "is_free": False, "tags": ["学习", "放松"]},
            {"sub_category": "小型展览", "name": "小城艺术空间", "profile": "family_mild", "indoor": True, "is_free": False, "tags": ["轻文化", "安静"]},
            {"sub_category": "美术馆", "name": "城市美术馆", "profile": "family_mild", "indoor": True, "is_free": False, "tags": ["拍照", "放松"]},
            {"sub_category": "安静手作体验", "name": "治愈手作工坊", "profile": "family_mild", "indoor": True, "is_free": False, "tags": ["治愈", "轻互动"]},
            {"sub_category": "沉浸式展览", "name": "光影沉浸式展", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["拍照", "出片"]},
            {"sub_category": "陶艺手作", "name": "双人陶艺工坊", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["互动", "纪念感"]},
            {"sub_category": "香薰手作", "name": "香气研究所·香薰DIY", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["互动", "纪念感"]},
            {"sub_category": "私人影院", "name": "小众私人影院", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["雨天", "晚间"]},
            {"sub_category": "夜景观景点", "name": "城市天台观景点", "profile": "friends_lively", "indoor": False, "is_free": True, "tags": ["夜景", "浪漫"]},
            {"sub_category": "复古街区", "name": "复古创意街区", "profile": "friends_lively", "indoor": False, "is_free": True, "tags": ["散步", "拍照"]},
            {"sub_category": "花艺体验", "name": "花艺手作体验馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["情绪价值", "手作"]},
            {"sub_category": "室内儿童乐园", "name": "星球室内儿童乐园", "profile": "family_3_6", "indoor": True, "is_free": False, "tags": ["少走路", "安全"]},
            {"sub_category": "室内儿童乐园", "name": "小熊室内儿童乐园", "profile": "family_3_6", "indoor": True, "is_free": False, "tags": ["少走路", "安全"]},
            {"sub_category": "亲子绘本馆", "name": "绘本星球亲子馆", "profile": "family_3_6", "indoor": True, "is_free": False, "tags": ["安静", "教育"]},
            {"sub_category": "儿童烘焙DIY", "name": "小小烘焙师DIY", "profile": "family_3_6", "indoor": True, "is_free": False, "tags": ["参与感", "亲子"]},
            {"sub_category": "商场亲子互动区", "name": "商场亲子互动区", "profile": "family_3_6", "indoor": True, "is_free": True, "tags": ["兜底", "室内"]},
            {"sub_category": "儿童剧小剧场", "name": "木偶剧小剧场", "profile": "family_3_6", "indoor": True, "is_free": False, "tags": ["轻体验", "亲子"]},
            {"sub_category": "科技馆", "name": "城市科技馆", "profile": "family_7_10", "indoor": True, "is_free": False, "tags": ["教育", "互动"]},
            {"sub_category": "亲子手工DIY", "name": "亲子陶艺手工DIY", "profile": "family_7_10", "indoor": True, "is_free": False, "tags": ["动手", "亲子"]},
            {"sub_category": "儿童运动馆", "name": "蹦床运动馆(低强度区)", "profile": "family_7_10", "indoor": True, "is_free": False, "tags": ["放电", "室内"]},
            {"sub_category": "益智桌游拼搭空间", "name": "拼搭桌游空间", "profile": "family_7_10", "indoor": True, "is_free": False, "tags": ["益智", "互动"]},
            {"sub_category": "自然教育小馆", "name": "自然教育小型博物馆", "profile": "family_7_10", "indoor": True, "is_free": False, "tags": ["周末学习", "探索"]},
            {"sub_category": "VR体验馆", "name": "星际VR体验馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["刺激", "朋友"]},
            {"sub_category": "密室逃脱(轻恐)", "name": "沉浸式密室(轻恐/非恐)", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["11+", "刺激"]},
            {"sub_category": "剧本杀(轻量本)", "name": "轻量剧本杀馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["13+", "沉浸"]},
            {"sub_category": "保龄球/台球/飞镖", "name": "保龄球台球飞镖馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["运动", "朋友"]},
            {"sub_category": "电玩城/街机厅", "name": "电玩城街机厅", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["青少年", "解压"]},
            {"sub_category": "桌游馆", "name": "桌游馆A", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["低排队", "可控时长"]},
            {"sub_category": "桌游馆", "name": "桌游馆B", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["低排队", "可控时长"]},
            {"sub_category": "KTV", "name": "周末KTV", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["晚间", "热闹"]},
            {"sub_category": "密室逃脱", "name": "密室逃脱馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["刺激", "朋友"]},
            {"sub_category": "剧本杀", "name": "剧本杀馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["长时段", "聚会"]},
            {"sub_category": "保龄球/台球/飞镖", "name": "台球飞镖馆", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["活动感", "聚会"]},
            {"sub_category": "Livehouse/清吧", "name": "清吧轻音乐Live", "profile": "friends_lively", "indoor": True, "is_free": False, "tags": ["晚间", "年轻人"]},
            {"sub_category": "商场综合体", "name": "大型商场综合体", "profile": "universal", "indoor": True, "is_free": True, "tags": ["雨天", "室内"]},
            {"sub_category": "城市公园/湖边步道", "name": "城市公园湖边步道", "profile": "universal", "indoor": False, "is_free": True, "tags": ["低预算", "天气好"]},
            {"sub_category": "大型书城", "name": "大型书城/商场书店", "profile": "universal", "indoor": True, "is_free": True, "tags": ["单人", "亲子", "情侣"]},
            {"sub_category": "综合娱乐中心", "name": "综合娱乐中心", "profile": "universal", "indoor": True, "is_free": False, "tags": ["多选项", "兜底"]},
        ]
    )

    def _build_packages(*, sub_category: str, is_free: bool, profile: str, idx: int) -> list[dict]:
        rng = random.Random(10000 + int(idx))

        def _base_duration_mins() -> int:
            duration = 60
            if any(k in sub_category for k in ("剧本杀", "密室")):
                duration = 120
            if any(k in sub_category for k in ("儿童乐园", "公园")):
                duration = 150
            if any(k in sub_category for k in ("KTV",)):
                duration = 180
            if any(k in sub_category for k in ("科技馆", "美术馆", "展览")):
                duration = 120
            return duration

        def _mk(
            *,
            k: int,
            name: str,
            price: float,
            description: str,
            features: str,
            requires_booking: bool,
            available_stock: int,
            duration_mins: int,
            duration_std_dev: float,
            start_time: str | None = None,
        ) -> dict:
            if start_time == "AUTO":
                start_time = _start_time(name, description)
                
            return {
                "package_id": f"package_{idx:03d}_{k}",
                "name": name,
                "price": float(round(price, 2)),
                "description": description,
                "features": features,
                "requires_booking": bool(requires_booking),
                "available_stock": int(available_stock),
                "duration_mins": int(duration_mins),
                "duration_std_dev": float(round(duration_std_dev, 1)),
                "start_time": start_time,
            }

        base_duration = _base_duration_mins()
        requires_booking_base = sub_category not in ("电玩城/街机厅", "商场亲子互动区")

        if is_free:
            return [
                _mk(
                    k=1,
                    name="自由入场体验",
                    price=0.0,
                    description="免费开放，随时可进",
                    features="无需预约，灵活度高。",
                    requires_booking=False,
                    available_stock=9999,
                    duration_mins=base_duration,
                    duration_std_dev=30.0,
                    start_time=None,
                ),
                _mk(
                    k=2,
                    name="周末定时讲解/互动(免费)",
                    price=0.0,
                    description="场馆/公园内定时的免费互动活动",
                    features="有引导员带领，适合家庭/朋友参与。",
                    requires_booking=True,
                    available_stock=20,
                    duration_mins=max(30, base_duration - 30),
                    duration_std_dev=10.0,
                    start_time="14:00",
                ),
            ]

        start_times = ["14:00", "15:00", "16:30", "18:00", "19:00", "20:00"]

        def _price(lo: float, hi: float) -> float:
            return float(rng.uniform(lo, hi))

        def _stock(lo: int, hi: int) -> int:
            return int(rng.randint(lo, hi))

        def _std(options: list[float]) -> float:
            return float(rng.choice(options))

        def _start_time(name: str, desc: str) -> str | None:
            text = (name + desc).lower()
            if '演出' in text or '话剧' in text or '音乐会' in text:
                return rng.choice(start_times)
            return None

        if profile in ("family_3_6", "kids_friendly"):
            return [
                _mk(
                    k=1,
                    name="1大1小亲子轻体验",
                    price=_price(39.0, 128.0),
                    description="更轻量更短时的亲子体验，避免孩子疲惫",
                    features="节奏更友好，适合带娃不费脑。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 420),
                    duration_mins=max(45, base_duration - 30),
                    duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="2大1小亲子标准体验",
                    price=_price(79.0, 188.0),
                    description="更完整的亲子项目内容，适合家庭一起参与",
                    features="更适合周末安排，孩子更容易投入。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 320),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="2大2小家庭畅玩",
                    price=_price(99.0, 238.0),
                    description="更适合多孩子家庭的畅玩方案，时长更足",
                    features="更省心，适合把孩子电量放空。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 260),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
            ]

        if profile == "couple_photo":
            return [
                _mk(
                    k=1,
                    name="双人互动体验",
                    price=_price(79.0, 198.0),
                    description="适合两人一起体验的互动项目，包含基础素材/时长",
                    features="互动感更强，更适合作为约会的一站。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(40, 520),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="双人浪漫升级体验",
                    price=_price(129.0, 268.0),
                    description="升级内容与更长时长，适合慢慢玩出仪式感",
                    features="氛围更到位，适合纪念日或想认真约一次。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 320),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="双人拍照打卡套餐",
                    price=_price(99.0, 228.0),
                    description="包含更适合拍照的玩法与路线建议",
                    features="更出片，适合把照片当纪念收藏。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 420),
                    duration_mins=base_duration + 15,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
            ]

        if profile == "family_7_10":
            return [
                _mk(
                    k=1,
                    name="1大1小亲子动手体验",
                    price=_price(49.0, 138.0),
                    description="更适合大孩子参与的轻互动体验，动手感更强",
                    features="参与感更足，适合亲子一起上手。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 420),
                    duration_mins=max(45, base_duration - 30),
                    duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="2大1小亲子标准体验",
                    price=_price(79.0, 188.0),
                    description="更完整的亲子互动内容，兼顾体验感与节奏",
                    features="更适合周末安排，孩子更容易投入。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 320),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="2大2小家庭畅玩",
                    price=_price(99.0, 238.0),
                    description="更适合家庭一起投入更长时间体验的畅玩方案",
                    features="更省心，适合把孩子电量放空。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 260),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
            ]

        if profile == "family_mild":
            return [
                _mk(
                    k=1,
                    name="1大1小轻松体验",
                    price=_price(39.0, 118.0),
                    description="轻量体验项目，适合临时起意安排一段轻松时光",
                    features="节奏舒适，适合不想太折腾的亲子出行。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(35, 460),
                    duration_mins=max(45, base_duration - 15),
                    duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="2大1小标准体验",
                    price=_price(69.0, 168.0),
                    description="更完整的家庭向体验内容，兼顾轻松和参与感",
                    features="更适合周末安排，整体节奏稳定。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 360),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="2大2小周末畅玩",
                    price=_price(89.0, 218.0),
                    description="适合一家人花更长时间慢慢玩的周末方案",
                    features="更省心，适合家庭一起消磨半天。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 260),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
            ]

        if profile == "teen_11_17":
            return [
                _mk(
                    k=1,
                    name="2-4人标准体验",
                    price=_price(69.0, 158.0),
                    description="适合小团体结伴体验，玩法更均衡",
                    features="更适合一起上手，体验强度适中。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 420),
                    duration_mins=max(45, base_duration - 15),
                    duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="3-5人进阶挑战",
                    price=_price(99.0, 228.0),
                    description="更强调配合与挑战的玩法，适合多人一起玩",
                    features="更有参与感，适合把气氛带起来。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 280),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="4人联机畅玩",
                    price=_price(109.0, 268.0),
                    description="更适合多人联机/合作的玩法内容，时长更充足",
                    features="更解压，适合结伴一起爽玩。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 240),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
            ]

        if profile == "friends_lively" or profile == "universal":
            return [
                _mk(
                    k=1,
                    name="双人搭子体验" if profile == "friends_lively" else "双人轻体验",
                    price=_price(59.0, 158.0),
                    description="适合两个人结伴体验的轻量方案，进入门槛更低",
                    features="更适合兄弟闺蜜搭子局，轻松不尴尬。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 460),
                    duration_mins=max(45, base_duration - 15),
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=2,
                    name="三人小聚体验" if profile == "friends_lively" else "三人小聚体验",
                    price=_price(79.0, 188.0),
                    description="适合小团体结伴体验，氛围更自然，互动更轻松",
                    features="更容易成局，适合朋友临时约一场。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(24, 360),
                    duration_mins=base_duration,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
                _mk(
                    k=3,
                    name="四人欢聚畅玩" if profile == "friends_lively" else "四人畅玩体验",
                    price=_price(99.0, 228.0),
                    description="更适合四人一起玩的畅玩方案，内容更丰富",
                    features="更热闹但不费脑，适合组局。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 320),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time="AUTO",
                ),
            ]

    for i, plan in enumerate(activity_plan):
        district = random.choice(hub_names)
        hub_x, hub_y = hubs[district]
        loc = generate_location_near_hub(hub_x, hub_y, district)
        sub_category = plan["sub_category"]
        profile = plan["profile"]
        indoor = bool(plan["indoor"])
        is_free = bool(plan["is_free"])
        tags = _sanitize_mock_list(list(plan.get("tags") or []))
        business_hours = random.choice(["10:00-22:00", "09:00-22:00", "10:00-21:30"])
        if any(k in sub_category for k in ("夜景", "Livehouse", "清吧")):
            business_hours = random.choice(["18:00-23:30", "19:00-24:00"])
        review_keywords = _sanitize_mock_list(_keywords_for_profile(
            category="activity",
            profile=profile,
            indoor=indoor,
            sub_category=sub_category,
            delivery_supported=False,
        ))

        venue = {
            "id": f"activity_{i+1:03d}",
            "name": f"{plan['name']}({district})",
            "category": "activity",
            "sub_category": sub_category,
            "district": district,
            "address": loc["address"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "business_hours": business_hours,
            "indoor": indoor,
            "review_keywords": review_keywords,
            "is_free": is_free,
            "rating": float(round(random.uniform(4.0, 5.0), 1)),
            "reviews_count": int(random.randint(100, 20000)),
            "tags": tags,
            "packages": _build_packages(sub_category=sub_category, is_free=is_free, profile=profile, idx=i + 1),
        }
        venue = _ensure_profile_fields(
            item=venue,
            category="activity",
            profile=profile,
            sub_category=sub_category,
            tags=tags,
            review_keywords=review_keywords,
            indoor=indoor,
        )
        mock_db["activity_venues"].append(_sanitize_mock_dict(venue))
        
    # 3. 礼品店
    gift_plan: list[dict] = (
        [
            {"sub_category": "鲜花店", "name": "花点时间·鲜花店", "profile": "couple_atmosphere", "delivery": True, "tags": ["鲜花", "约会", "纪念日"]},
            {"sub_category": "鲜花店", "name": "花语花店", "profile": "couple_atmosphere", "delivery": True, "tags": ["鲜花", "浪漫"]},
            {"sub_category": "永生花", "name": "永生花小花束", "profile": "couple_atmosphere", "delivery": True, "tags": ["永生花", "可保存"]},
            {"sub_category": "香薰蜡烛", "name": "香薰蜡烛礼品", "profile": "couple_atmosphere", "delivery": True, "tags": ["香薰", "氛围感"]},
            {"sub_category": "手工巧克力", "name": "手工巧克力工坊", "profile": "couple_atmosphere", "delivery": True, "tags": ["巧克力", "惊喜"]},
            {"sub_category": "小蛋糕店", "name": "小蛋糕店A", "profile": "birthday_friends", "delivery": True, "tags": ["蛋糕", "庆生"]},
            {"sub_category": "小蛋糕店", "name": "小蛋糕店B", "profile": "birthday_friends", "delivery": True, "tags": ["蛋糕", "朋友聚会"]},
            {"sub_category": "甜品礼盒", "name": "甜品礼盒店", "profile": "birthday_friends", "delivery": True, "tags": ["甜品", "礼盒"]},
            {"sub_category": "奶茶/咖啡团单", "name": "奶茶咖啡团单", "profile": "birthday_friends", "delivery": True, "tags": ["奶茶", "咖啡", "低成本惊喜"]},
            {"sub_category": "儿童玩具店", "name": "儿童玩具店", "profile": "kids", "delivery": True, "tags": ["玩具", "3-6岁"]},
            {"sub_category": "益智玩具/拼图", "name": "益智拼图玩具", "profile": "kids", "delivery": True, "tags": ["拼图", "7-10岁"]},
            {"sub_category": "毛绒玩具", "name": "毛绒玩具屋", "profile": "kids", "delivery": True, "tags": ["毛绒", "可爱"]},
            {"sub_category": "文具/手账小礼物", "name": "文具手账小礼物", "profile": "kids", "delivery": True, "tags": ["文具", "手账"]},
            {"sub_category": "文创礼品店", "name": "文创礼品店", "profile": "culture", "delivery": True, "tags": ["文创", "展览后"]},
            {"sub_category": "盲盒/潮玩", "name": "潮玩盲盒店", "profile": "culture", "delivery": False, "tags": ["盲盒", "潮玩"]},
            {"sub_category": "明信片/纪念品", "name": "城市明信片纪念品", "profile": "culture", "delivery": True, "tags": ["明信片", "纪念品"]},
        ]
    )

    def _build_gifts(*, sub_category: str, profile: str, tags: list[str]) -> list[dict]:
        t = " ".join(tags or [])

        def _ensure6(items: list[dict]) -> list[dict]:
            out = list(items)
            while len(out) < 6:
                out.append(
                    {
                        "name": "实用小礼物",
                        "price": 29.9,
                        "desc": "小礼物不贵但很有心意，适合随手带走",
                        "features": "低决策成本，基本不踩雷。",
                        "stock": 120,
                    }
                )
            return out[:6]

        if profile == "couple_atmosphere":
            if sub_category in ("鲜花店", "永生花"):
                return _ensure6(
                    [
                        {"name": "单支红玫瑰精美包装", "price": 39.0, "desc": "单支红玫瑰+精美包装，适合日常小惊喜", "features": "轻负担但很有仪式感。", "stock": 120},
                        {"name": "迷你花束(小束)", "price": 49.0, "desc": "小束花束+贺卡，适合临时加一份惊喜", "features": "拿着拍照也很好看。", "stock": 100},
                        {"name": "19朵混搭花束", "price": 169.0, "desc": "19朵混搭花束+贺卡+小彩灯", "features": "出片率更高，氛围感更强。", "stock": 40},
                        {"name": "永生花小礼盒", "price": 199.0, "desc": "永生花礼盒，可保存更久", "features": "更适合做纪念。", "stock": 30},
                        {"name": "香槟色花束(中束)", "price": 129.0, "desc": "中束花束+丝带包装，颜色更高级", "features": "更显质感，适合拍照。", "stock": 50},
                        {"name": "手写贺卡服务", "price": 19.9, "desc": "附赠手写贺卡与封蜡贴", "features": "小小加成但很加分。", "stock": 999},
                    ]
                )
            if sub_category == "香薰蜡烛":
                return _ensure6(
                    [
                        {"name": "小样香薰蜡烛(1支)", "price": 39.9, "desc": "一支小样香薰蜡烛，香味清新", "features": "低价但很有氛围。", "stock": 120},
                        {"name": "无火香薰扩香套装", "price": 59.9, "desc": "白茶/蓝风铃香型，含扩香藤条与精油", "features": "提升房间氛围感的入门款。", "stock": 100},
                        {"name": "香薰蜡烛礼盒(双支)", "price": 88.0, "desc": "两支香薰蜡烛+火柴+礼盒包装", "features": "送礼更体面。", "stock": 80},
                        {"name": "香薰精油补充装(2瓶)", "price": 79.0, "desc": "两瓶精油补充装，持香更久", "features": "更适合长期使用。", "stock": 90},
                        {"name": "氛围感香薰礼盒", "price": 139.0, "desc": "扩香+蜡烛+小摆件组合礼盒", "features": "仪式感更强，包装更好看。", "stock": 40},
                        {"name": "暖光小夜灯(礼物装)", "price": 69.0, "desc": "暖光小夜灯，适合卧室/桌面", "features": "氛围感拉满的小物件。", "stock": 70},
                    ]
                )
            if sub_category == "手工巧克力":
                return _ensure6(
                    [
                        {"name": "巧克力小方块(6颗)", "price": 39.9, "desc": "6颗小方块巧克力组合", "features": "低成本但很讨喜。", "stock": 120},
                        {"name": "可可脆片巧克力棒(4支)", "price": 58.0, "desc": "4支巧克力棒，带可可脆片口感", "features": "随手送也不尴尬。", "stock": 120},
                        {"name": "手工夹心巧克力礼盒(12颗)", "price": 128.0, "desc": "12颗手工夹心巧克力，多口味搭配", "features": "更适合认真准备的礼物。", "stock": 60},
                        {"name": "高可可含量黑巧礼盒", "price": 99.0, "desc": "高可可含量黑巧礼盒，口感更醇", "features": "更显高级，甜度更克制。", "stock": 70},
                        {"name": "巧克力玫瑰花束", "price": 169.0, "desc": "巧克力组成的花束造型礼物", "features": "好看又能吃，惊喜感更强。", "stock": 30},
                        {"name": "礼物包装升级服务", "price": 19.9, "desc": "升级礼物包装与丝带", "features": "更有仪式感。", "stock": 999},
                    ]
                )

        if profile == "birthday_friends":
            if sub_category in ("小蛋糕店", "甜品礼盒"):
                return _ensure6(
                    [
                        {"name": "半熟芝士(一盒5枚)", "price": 38.0, "desc": "招牌半熟芝士，入口即化", "features": "小成本但很有幸福感。", "stock": 120},
                        {"name": "生日蜡烛+帽子小套装", "price": 19.9, "desc": "蜡烛+生日帽+小拉旗", "features": "氛围立刻到位。", "stock": 300},
                        {"name": "小甜品礼盒(4份)", "price": 98.0, "desc": "4份小甜品组合，口味搭配更均衡", "features": "分享更方便，适合朋友小聚。", "stock": 80},
                        {"name": "6英寸生日蛋糕", "price": 168.0, "desc": "6英寸奶油蛋糕，附蜡烛刀叉", "features": "3-4人小型庆生刚刚好。", "stock": 40},
                        {"name": "8英寸水果蛋糕", "price": 198.0, "desc": "8英寸水果蛋糕，适合多人分享", "features": "更适合朋友聚会。", "stock": 25},
                        {"name": "庆生甜品拼盘", "price": 128.0, "desc": "甜品拼盘+小卡片，适合摆拍", "features": "仪式感更强，照片更好看。", "stock": 50},
                    ]
                )
            if sub_category == "奶茶/咖啡团单":
                return _ensure6(
                    [
                        {"name": "单杯奶茶加料券", "price": 19.9, "desc": "单杯加料券，可选珍珠/椰果等", "features": "低成本的小惊喜。", "stock": 999},
                        {"name": "双杯奶茶团单", "price": 49.9, "desc": "两杯奶茶任选", "features": "省事又体面。", "stock": 999},
                        {"name": "四杯咖啡团单", "price": 99.0, "desc": "四杯咖啡任选", "features": "聚会补给很省心。", "stock": 999},
                        {"name": "六杯奶茶聚会团单", "price": 139.0, "desc": "六杯奶茶任选，适合多人聚会", "features": "人多也不怕不够喝。", "stock": 999},
                        {"name": "蛋糕券(小份)", "price": 39.9, "desc": "小份蛋糕兑换券，方便搭配饮品", "features": "更适合临时加一份甜。", "stock": 999},
                        {"name": "聚会零食小礼包", "price": 59.0, "desc": "零食小礼包，适合配奶茶咖啡", "features": "边聊边吃更开心。", "stock": 200},
                    ]
                )

        if profile == "kids":
            return _ensure6(
                [
                    {"name": "儿童贴纸+涂鸦本套装", "price": 19.9, "desc": "涂鸦本+贴纸，适合安静时间", "features": "上手简单，孩子更专注。", "stock": 200},
                    {"name": "迷你积木小套装", "price": 39.9, "desc": "迷你积木套装，适合动手搭建", "features": "作为小奖励很合适。", "stock": 150},
                    {"name": "儿童益智拼图", "price": 69.0, "desc": "适合7-10岁拼图，难度适中", "features": "更有成就感，适合亲子一起拼。", "stock": 120},
                    {"name": "毛绒玩具(中号)", "price": 59.9, "desc": "中号毛绒玩具，柔软亲肤", "features": "孩子更容易喜欢，抱着很安心。", "stock": 120},
                    {"name": "文具手账礼盒", "price": 68.0, "desc": "手账本+贴纸+彩笔组合", "features": "实用又好看，适合送小朋友。", "stock": 100},
                    {"name": "益智桌游(亲子版)", "price": 128.0, "desc": "亲子版桌游，规则简单易上手", "features": "更适合一家人一起玩。", "stock": 60},
                ]
            )

        if sub_category == "盲盒/潮玩" or ("盲盒" in t) or ("潮玩" in t):
            return _ensure6(
                [
                    {"name": "盲盒(单盒)", "price": 69.0, "desc": "热门系列盲盒，款式随机", "features": "拆盒瞬间最上头。", "stock": 300},
                    {"name": "盲盒双盒装", "price": 128.0, "desc": "两盒盲盒组合装，款式随机", "features": "更适合一起拆。", "stock": 180},
                    {"name": "盲盒三盒装", "price": 188.0, "desc": "三盒装组合，款式随机", "features": "拆得更过瘾。", "stock": 120},
                    {"name": "盲盒端盒(6个)", "price": 399.0, "desc": "整盒未拆封，适合收藏", "features": "开盒仪式感更强。", "stock": 25},
                    {"name": "潮玩展示收纳盒", "price": 49.9, "desc": "透明展示收纳盒，防尘更好看", "features": "摆出来更有成就感。", "stock": 200},
                    {"name": "潮玩钥匙扣挂件", "price": 29.9, "desc": "潮玩钥匙扣挂件，随身带着更开心", "features": "低成本但很可爱。", "stock": 240},
                ]
            )

        return _ensure6(
            [
                {"name": "城市明信片套装(10张)", "price": 39.0, "desc": "10张城市明信片，含贴纸", "features": "纪念感很强，适合带走。", "stock": 200},
                {"name": "文创贴纸手账套装", "price": 29.9, "desc": "贴纸+胶带组合，适合记录生活", "features": "低成本但很实用。", "stock": 220},
                {"name": "文创小摆件", "price": 59.0, "desc": "桌面小摆件，适合送礼", "features": "不贵但有心意。", "stock": 150},
                {"name": "复古手帐本礼盒", "price": 68.0, "desc": "笔记本+羽毛笔+和纸胶带", "features": "颜值更高，送礼更体面。", "stock": 120},
                {"name": "城市纪念徽章套装", "price": 49.0, "desc": "纪念徽章套装，可别在包上", "features": "小而精致，适合当伴手礼。", "stock": 180},
                {"name": "明信片邮票贴纸套装", "price": 19.9, "desc": "邮票贴纸+装饰贴，适合写信", "features": "细节更有趣。", "stock": 260},
            ]
        )

    for i, plan in enumerate(gift_plan):
        district = random.choice(hub_names)
        hub_x, hub_y = hubs[district]
        loc = generate_location_near_hub(hub_x, hub_y, district)
        sub_category = plan["sub_category"]
        delivery_supported = bool(plan["delivery"])
        delivery_time_mins = int(random.choice([30, 45, 60])) if delivery_supported else None
        delivery_time_std = float(random.choice([5.0, 8.0, 10.0, 15.0])) if delivery_supported else None
        business_hours = random.choice(["10:00-21:00", "10:00-22:00", "11:00-20:30"])
        indoor = True
        plan_tags = _sanitize_mock_list(list(plan.get("tags") or []))
        review_keywords = _sanitize_mock_list(_keywords_for_profile(
            category="gift_shop",
            profile=str(plan["profile"]),
            indoor=indoor,
            sub_category=sub_category,
            delivery_supported=delivery_supported,
        ))

        gifts_raw = _build_gifts(
            sub_category=sub_category,
            profile=str(plan["profile"]),
            tags=plan_tags,
        )
        gifts = []
        for j, g in enumerate(gifts_raw):
            recv_mins, recv_std = _infer_receive_duration_mins(g["name"], plan_tags)
            gifts.append(
                {
                    "gift_id": f"gift_{i+1:03d}_{j+1}",
                    "name": g["name"],
                    "price": float(g["price"]),
                    "receive_duration_mins": int(recv_mins),
                    "receive_duration_std_dev": float(recv_std),
                    "description": g.get("desc", ""),
                    "features": g.get("features", ""),
                    "stock": int(g.get("stock") or 50),
                }
            )

        shop = {
            "id": f"gift_shop_{i+1:03d}",
            "name": f"{plan['name']}({district})",
            "category": "gift_shop",
            "sub_category": sub_category,
            "district": district,
            "address": loc["address"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "business_hours": business_hours,
            "indoor": indoor,
            "review_keywords": review_keywords,
            "rating": float(round(random.uniform(4.5, 5.0), 1)),
            "tags": plan_tags,
            "gifts": gifts,
            "delivery_time_mins": delivery_time_mins,
            "delivery_time_std_dev": delivery_time_std,
            "delivery_radius_km": 5.0,
        }
        shop = _ensure_profile_fields(
            item=shop,
            category="gift_shop",
            profile=str(plan["profile"]),
            sub_category=sub_category,
            tags=plan_tags,
            review_keywords=review_keywords,
            indoor=indoor,
        )
        shop = _ensure_gift_shop_special_fields(
            item=shop,
            sub_category=sub_category,
            tags=plan_tags,
            review_keywords=review_keywords,
        )
        mock_db["gift_shops"].append(_sanitize_mock_dict(shop))
        
    return mock_db


def _load_catalog_json(catalog_dir: str, filename: str) -> list[dict] | None:
    file_path = os.path.join(catalog_dir, filename)
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"catalog must be list: {file_path}")
    return data



def _calc_seating_risk_prob(rating: float) -> float:
    if rating < 3.0:
        return 0.1
    prob = 0.1 + ((rating - 3.0) / 2.0) * 0.8
    return round(min(0.95, prob), 2)

if __name__ == "__main__":
    from closedloop.core.config import REPO_ROOT_DIR, get_config
    from closedloop.core.logger import LoggerManager, logger

    random.seed(42) 
    config = get_config()
    LoggerManager.setup(config)

    def _resolve_dir(v: str) -> str:
        if not v:
            return ""
        if os.path.isabs(v):
            return os.path.abspath(v)
        return os.path.abspath(os.path.join(REPO_ROOT_DIR, v))

    data = generate_mock_db()

    # --- Apply seating risk prob and adjust requires_booking ---
    for rest in data.get("restaurants", []):
        rating = float(rest.get("rating", 0.0))
        prob = _calc_seating_risk_prob(rating)
        for combo in rest.get("combos", []):
            if combo.get("requires_booking"):
                if random.random() < prob:
                    combo["requires_booking"] = True
                    combo["seating_risk_prob"] = prob
                else:
                    combo["requires_booking"] = False
                    combo.pop("seating_risk_prob", None)
            else:
                combo.pop("seating_risk_prob", None)

    for act in data.get("activity_venues", []):
        sub_cat = act.get("sub_category", "")
        # 免票公共场所
        is_free_public = sub_cat in ("城市公园/湖边步道", "大型书城", "商场综合体", "商场亲子互动区", "复古街区")
        rating = float(act.get("rating", 0.0))
        prob = _calc_seating_risk_prob(rating)
        
        for pkg in act.get("packages", []):
            if is_free_public:
                pkg["requires_booking"] = False
                pkg.pop("seating_risk_prob", None)
            else:
                if pkg.get("requires_booking"):
                    if random.random() < prob:
                        pkg["requires_booking"] = True
                        pkg["seating_risk_prob"] = prob
                    else:
                        pkg["requires_booking"] = False
                        pkg.pop("seating_risk_prob", None)
                else:
                    pkg.pop("seating_risk_prob", None)

    # --- End modification ---

    mock_db_dir = _resolve_dir(config.data.MOCK_DB_REPO_DIR)
    os.makedirs(mock_db_dir, exist_ok=True)

    with open(os.path.join(mock_db_dir, "restaurants.json"), "w", encoding="utf-8") as f:
        json.dump(data["restaurants"], f, ensure_ascii=False, indent=2)
    with open(os.path.join(mock_db_dir, "activities.json"), "w", encoding="utf-8") as f:
        json.dump(data["activity_venues"], f, ensure_ascii=False, indent=2)
    with open(os.path.join(mock_db_dir, "add_ons.json"), "w", encoding="utf-8") as f:
        json.dump(data["gift_shops"], f, ensure_ascii=False, indent=2)

    reservations = generate_reservations_from_mock_db(data)
    with open(os.path.join(mock_db_dir, "reservations.json"), "w", encoding="utf-8") as f:
        json.dump(reservations, f, ensure_ascii=False, indent=2)

    logger.info("phase=mock_data_generator | result=generated_mock_db_files")
