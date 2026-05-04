import os
import json
import math
import random
from typing import List, Dict, Any, Optional

# =====================================================================
# 1. 核心数学库：高斯分布与商圈生成
# =====================================================================

def generate_hub_locations() -> dict[str, tuple[float, float]]:
    hubs = {}
    hub_configs = {
        "CBD核心商圈": (3, 6),
        "老城文化街区": (2, 5),
        "大学城商圈": (5, 9),
        "滨江风景区": (4, 8),
        "高新科技园": (6, 11)
    }
    
    for name, (min_r, max_r) in hub_configs.items():
        theta = random.uniform(0, 2 * math.pi)
        r = random.uniform(min_r, max_r)
        hubs[name] = (r * math.cos(theta), r * math.sin(theta))
        
    return hubs

def generate_location_near_hub(hub_x: float, hub_y: float, hub_name: str, sigma: float = 1.5) -> dict[str, Any]:
    while True:
        dx = random.gauss(0, sigma)
        dy = random.gauss(0, sigma)
        final_x = round(hub_x + dx, 3)
        final_y = round(hub_y + dy, 3)
        dist_to_center = round(math.sqrt(final_x**2 + final_y**2), 2)
        if dist_to_center <= 12.0:
            break
    return {
        "latitude": final_x,
        "longitude": final_y,
        "address": f"{hub_name}附近某街道{random.randint(1, 999)}号",
        "distance_to_center_km": dist_to_center,
        "zone_name": hub_name
    }

def generate_standalone_location() -> dict[str, Any]:
    while True:
        x = random.gauss(0, 4.0)
        y = random.gauss(0, 4.0)
        dist = math.sqrt(x**2 + y**2)
        if dist <= 12.0:
            break
    return {
        "latitude": round(x, 3),
        "longitude": round(y, 3),
        "address": f"市郊某偏远大道{random.randint(1, 999)}号",
        "distance_to_center_km": round(dist, 2),
        "zone_name": "独立区域"
    }

# =====================================================================
# 2. 实体数据模板（加入时间时长、标准差、适用时段、短时活动等）
# =====================================================================

RESTAURANT_TEMPLATES = [
    {"name": "蜀大侠火锅", "rating": 4.8, "tags": ["火锅", "聚餐", "热闹"], "combos": [
        {"name": "单人工作餐冒菜", "price": 38.0, "desc": "牛油底料冒菜+米饭", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "双人浪漫约会餐", "price": 168.0, "desc": "鸳鸯锅+肥牛+虾滑", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "温馨三口之家套餐", "price": 218.0, "desc": "番茄锅+虾滑+小吃", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "青年四人欢聚套餐", "price": 288.0, "desc": "红锅+毛肚+酥肉+大窑", "dur": 120, "std": 30, "slots": ["dinner", "late_night"]},
        {"name": "八人豪华包厢宴", "price": 888.0, "desc": "全牛宴拼盘+海鲜", "dur": 150, "std": 30, "slots": ["dinner"]}
    ]},
    {"name": "眉州东坡", "rating": 4.6, "tags": ["川菜", "家庭", "老字号"], "combos": [
        {"name": "单人东坡肉盖饭", "price": 45.0, "desc": "东坡肉+米饭", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "亲子三人套餐", "price": 188.0, "desc": "糖醋里脊+鸡汤+包点", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "双人经典套餐", "price": 158.0, "desc": "宫保鸡丁+麻婆豆腐", "dur": 60, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "经典四人同享餐", "price": 258.0, "desc": "东坡肘子+烤鸭半套", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "凑凑火锅·茶憩", "rating": 4.7, "tags": ["火锅", "奶茶", "打卡"], "combos": [
        {"name": "单人解馋小火锅", "price": 88.0, "desc": "吧台小锅+奶茶", "dur": 60, "std": 10, "slots": ["lunch", "dinner", "late_night"]},
        {"name": "凑凑下午茶套餐", "price": 58.0, "desc": "大红袍奶茶2杯+甜点", "dur": 45, "std": 15, "slots": ["afternoon_tea"]},
        {"name": "家庭欢乐火锅", "price": 268.0, "desc": "花胶鸡锅+海鲜拼盘", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "闺蜜四人局", "price": 328.0, "desc": "台式麻辣锅+奶茶4杯", "dur": 150, "std": 30, "slots": ["dinner", "late_night"]}
    ]},
    {"name": "蓝蛙 Wagas", "rating": 4.5, "tags": ["西餐", "轻食", "汉堡"], "combos": [
        {"name": "单人减脂轻食碗", "price": 68.0, "desc": "三文鱼沙拉+黑咖啡", "dur": 40, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "双人美式下午茶", "price": 128.0, "desc": "迷你汉堡*2+饮品", "dur": 60, "std": 15, "slots": ["afternoon_tea"]},
        {"name": "家庭健康轻食餐", "price": 238.0, "desc": "沙拉+烤鸡肉卷+意面", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "四人美式汉堡餐", "price": 318.0, "desc": "招牌牛肉堡*4+小吃", "dur": 90, "std": 20, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "王品牛排", "rating": 4.8, "tags": ["牛排", "庆生", "服务好"], "combos": [
        {"name": "单人尊享位上套餐", "price": 298.0, "desc": "台塑牛排+沙拉+汤", "dur": 90, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "情侣浪漫双人餐", "price": 588.0, "desc": "海陆双拼+玫瑰红酒", "dur": 120, "std": 15, "slots": ["dinner"]},
        {"name": "三口之家庆生宴", "price": 358.0, "desc": "海陆双拼牛排+儿童牛排", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "四人臻选牛排套餐", "price": 458.0, "desc": "经典台塑牛排+法式红酒", "dur": 150, "std": 20, "slots": ["dinner"]}
    ]},
    {"name": "胡大饭馆", "rating": 4.8, "tags": ["小龙虾", "宵夜", "青年"], "combos": [
        {"name": "双人深夜食堂", "price": 198.0, "desc": "小龙虾1.5斤+烤馒头片", "dur": 90, "std": 20, "slots": ["dinner", "late_night"]},
        {"name": "三人微辣夜宵", "price": 268.0, "desc": "蒜蓉小龙虾2斤+炒饭", "dur": 120, "std": 30, "slots": ["dinner", "late_night"]},
        {"name": "四人麻辣小龙虾局", "price": 388.0, "desc": "麻辣小龙虾3斤+大扎啤", "dur": 150, "std": 30, "slots": ["dinner", "late_night"]}
    ]},
    {"name": "点都德", "rating": 4.7, "tags": ["粤菜", "点心", "全天候"], "combos": [
        {"name": "单人早茶尝鲜", "price": 58.0, "desc": "虾饺皇+皮蛋瘦肉粥", "dur": 45, "std": 10, "slots": ["breakfast", "lunch"]},
        {"name": "双人经典叹茶", "price": 138.0, "desc": "红米肠+凤爪+一壶普洱", "dur": 90, "std": 30, "slots": ["breakfast", "lunch", "afternoon_tea"]},
        {"name": "家庭广式晚餐", "price": 218.0, "desc": "烧鹅双拼+干炒牛河", "dur": 90, "std": 15, "slots": ["dinner"]},
        {"name": "四人饮茶闲聊", "price": 268.0, "desc": "金牌虾饺皇+红米肠等", "dur": 120, "std": 45, "slots": ["lunch", "afternoon_tea"]}
    ]},
    {"name": "外婆家", "rating": 4.4, "tags": ["家常菜", "温馨"], "combos": [
        {"name": "单人外婆便当", "price": 28.0, "desc": "红烧肉+米饭", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "双人回忆套餐", "price": 98.0, "desc": "红烧肉+蒜蓉粉丝虾", "dur": 60, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "三口之家日常餐", "price": 138.0, "desc": "麻婆豆腐+糖醋排骨", "dur": 60, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "四人大满足", "price": 208.0, "desc": "红烧肉+茶香鸡+宋嫂鱼羹", "dur": 90, "std": 20, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "比格披萨自助", "rating": 4.2, "tags": ["披萨", "自助", "平价"], "combos": [
        {"name": "单人工作日自助", "price": 69.0, "desc": "单人畅吃", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "2大1小家庭自助", "price": 188.0, "desc": "两位成人+一位儿童畅吃", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "四人畅吃派对", "price": 276.0, "desc": "四位成人自助", "dur": 120, "std": 30, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "霸王茶姬 / 喜茶", "rating": 4.8, "tags": ["奶茶", "小憩"], "combos": [
        {"name": "伯牙绝弦单杯打包", "price": 20.0, "desc": "招牌原叶鲜奶茶", "dur": 15, "std": 5, "slots": ["lunch", "afternoon_tea", "dinner"]},
        {"name": "双人下午茶小憩", "price": 45.0, "desc": "奶茶2杯+小甜点", "dur": 45, "std": 15, "slots": ["afternoon_tea"]},
        {"name": "四人开黑奶茶套餐", "price": 80.0, "desc": "大杯招牌奶茶4杯", "dur": 20, "std": 10, "slots": ["afternoon_tea", "dinner", "late_night"]}
    ]}
]

VENUE_TEMPLATES = [
    # --- 新增：短时/碎片化活动 ---
    {"name": "大玩家室内机动游戏厅", "cat": "休闲娱乐", "is_free": False, "tags": ["电玩", "抓娃娃", "短时"], "packages": [
        {"name": "单人50枚游戏币(抓娃娃)", "price": 39.9, "desc": "适合碎片时间", "dur": 30, "std": 10},
        {"name": "情侣150枚游戏币特惠", "price": 99.0, "desc": "畅玩跳舞机、赛车", "dur": 90, "std": 30},
        {"name": "四人300币狂欢大礼包", "price": 188.0, "desc": "推币机、大乱斗", "dur": 120, "std": 45}
    ]},
    {"name": "咔嚓咔嚓自拍馆", "cat": "休闲娱乐", "is_free": False, "tags": ["拍照", "大头贴", "短时"], "packages": [
        {"name": "单人/双人韩式大头贴", "price": 35.0, "desc": "含2张实体相纸，立等可取", "dur": 20, "std": 5},
        {"name": "四人闺蜜换装自拍(半小时)", "price": 128.0, "desc": "提供JK/JK制服", "dur": 45, "std": 10}
    ]},
    {"name": "星际VR体验舱", "cat": "休闲娱乐", "is_free": False, "tags": ["VR", "短时", "刺激"], "packages": [
        {"name": "单人《过山车》VR体验", "price": 45.0, "desc": "极限失重体验", "dur": 15, "std": 2},
        {"name": "双人《丧尸危机》VR射击", "price": 88.0, "desc": "双人联机防守", "dur": 20, "std": 5},
        {"name": "家庭/四人包舱半小时", "price": 198.0, "desc": "任意游戏轮换玩", "dur": 30, "std": 5}
    ]},

    # --- 游乐园 / 主题乐园 ---
    {"name": "融创乐园", "cat": "游乐园", "is_free": False, "tags": ["刺激", "亲子", "大型"], "packages": [
        {"name": "成人单人欢乐套票", "price": 218.0, "desc": "含过山车等30项", "dur": 480, "std": 60},
        {"name": "2大1小家庭通票", "price": 458.0, "desc": "含儿童区", "dur": 480, "std": 90},
        {"name": "青年四人成团特惠", "price": 788.0, "desc": "四大过山车", "dur": 480, "std": 60}
    ]},
    
    # --- 密室 / 剧本杀 / 桌游 ---
    {"name": "X-cape 沉浸式机械密室", "cat": "密室逃脱", "is_free": False, "tags": ["机械", "烧脑", "无NPC"], "packages": [
        {"name": "《达芬奇的密码》双人", "price": 236.0, "desc": "纯机械解密", "dur": 90, "std": 15, "start": "14:00"},
        {"name": "《盗墓迷影》四人组局", "price": 472.0, "desc": "中国风机关", "dur": 100, "std": 20, "start": "16:30"},
        {"name": "《生化危机》四人微恐", "price": 512.0, "desc": "微恐解密", "dur": 100, "std": 15, "start": "19:00"}
    ]},
    {"name": "剧好玩·全息投影剧本杀", "cat": "休闲娱乐", "is_free": False, "tags": ["剧本杀", "换装", "飙戏"], "packages": [
        {"name": "《九霄寒夜》古风四人车", "price": 552.0, "desc": "含汉服妆造", "dur": 300, "std": 45, "start": "18:00"},
        {"name": "硬核推理本(包场)", "price": 888.0, "desc": "硬核推理不限时", "dur": 360, "std": 60, "start": "20:00"}
    ]},

    # --- 电影院 ---
    {"name": "万达影城(万达广场店)", "cat": "电影院", "is_free": False, "tags": ["IMAX", "商场内", "停车方便"], "packages": [
        {"name": "《沙丘2》IMAX 2D 10:00场", "price": 45.0, "desc": "早场", "dur": 166, "std": 2, "start": "10:00"},
        {"name": "《飞驰人生3》双人套票", "price": 118.0, "desc": "含爆米花", "dur": 130, "std": 2, "start": "19:30"},
        {"name": "《功夫熊猫6》2大1小家庭票", "price": 128.0, "desc": "动画主题厅", "dur": 100, "std": 5, "start": "15:00"},
        {"name": "《流浪地球3》四人套餐", "price": 228.0, "desc": "4张票", "dur": 150, "std": 2, "start": "20:00"}
    ]},

    # --- 体育 / 运动 ---
    {"name": "极速卡丁车俱乐部", "cat": "体育运动", "is_free": False, "tags": ["竞速", "团建", "短时"], "packages": [
        {"name": "单人单节体验(8分钟)", "price": 128.0, "desc": "跑8-10圈", "dur": 30, "std": 5},
        {"name": "2大1小亲子套票", "price": 288.0, "desc": "双人车+儿童车", "dur": 45, "std": 10},
        {"name": "四人迷你大奖赛", "price": 588.0, "desc": "练习+正赛", "dur": 90, "std": 15}
    ]},

    # --- 展览 / 博物馆 ---
    {"name": "省博物院", "cat": "博物馆", "is_free": True, "tags": ["历史", "免费", "室内"], "packages": [
        {"name": "基本陈列免费参观", "price": 0.0, "desc": "需预约", "dur": 180, "std": 45},
        {"name": "人工讲解服务(适合家庭)", "price": 150.0, "desc": "讲解员带看", "dur": 120, "std": 10}
    ]}
]

GIFT_SHOP_TEMPLATES = [
    {"name": "花点时间·精品花艺", "tags": ["鲜花", "浪漫", "惊喜"], "delivery": {"mins": 60, "std": 15}, "gifts": [
        {"name": "单支红玫瑰精美包装", "price": 39.0, "stock": 50},
        {"name": "99朵红玫瑰花束", "price": 399.0, "stock": 10},
        {"name": "向日葵清新混搭花篮", "price": 168.0, "stock": 25}
    ]},
    {"name": "泡泡玛特 POP MART", "tags": ["潮玩", "盲盒", "青年"], "delivery": None, "gifts": [ # 不支持配送
        {"name": "Skullpanda 密林古堡盲盒端盒(12个)", "price": 828.0, "stock": 5},
        {"name": "Dimoo 随机盲盒(单盒)", "price": 69.0, "stock": 200}
    ]},
    {"name": "黑天鹅法式蛋糕房", "tags": ["蛋糕", "庆生", "高端"], "delivery": {"mins": 90, "std": 20}, "gifts": [
        {"name": "6英寸经典黑森林蛋糕", "price": 298.0, "stock": 15},
        {"name": "8英寸草莓鲜奶水果蛋糕", "price": 368.0, "stock": 10}
    ]},
    {"name": "Godiva 歌帝梵巧克力", "tags": ["巧克力", "零食", "送女友"], "delivery": {"mins": 45, "std": 10}, "gifts": [
        {"name": "经典金装巧克力礼盒(15颗)", "price": 328.0, "stock": 50},
        {"name": "心形松露巧克力铁盒", "price": 418.0, "stock": 20}
    ]},
    {"name": "Lego 乐高授权专卖店", "tags": ["玩具", "儿童", "送礼"], "delivery": None, "gifts": [ # 线下自提
        {"name": "乐高科技组：保时捷赛车", "price": 499.0, "stock": 8},
        {"name": "乐高经典创意散件大颗粒", "price": 299.0, "stock": 20}
    ]}
]

# =====================================================================
# 3. 组装数据与导出
# =====================================================================

def generate_mock_db() -> dict[str, Any]:
    hubs = generate_hub_locations()
    hub_names = list(hubs.keys())
    
    mock_db = {
        "restaurants": [],
        "activity_venues": [],
        "gift_shops": []
    }
    
    # 1. 餐厅
    # 为了生成 20 家，重复/循环使用模板
    for i in range(20):
        tpl = RESTAURANT_TEMPLATES[i % len(RESTAURANT_TEMPLATES)]
        if i % 5 == 0:
            loc = generate_standalone_location()
        else:
            hub_name = random.choice(hub_names)
            loc = generate_location_near_hub(hubs[hub_name][0], hubs[hub_name][1], hub_name)
            
        restaurant = {
            "restaurant_id": f"r_{i+1001}",
            "name": f"{tpl['name']} ({loc['zone_name']}店)" if loc['zone_name'] != "独立区域" else tpl["name"],
            "location": loc,
            "rating": tpl["rating"],
            "combos": [
                {
                    "combo_id": f"c_{i+1001}_{j+1}",
                    "name": c["name"],
                    "price": c["price"],
                    "description": c["desc"],
                    "duration_mins": c["dur"],
                    "duration_std_dev": float(c["std"]),
                    "suitable_time_slots": c["slots"]
                } for j, c in enumerate(tpl["combos"])
            ],
            "tags": tpl["tags"]
        }
        mock_db["restaurants"].append(restaurant)
        
    # 2. 活动场所
    for i in range(15):
        tpl = VENUE_TEMPLATES[i % len(VENUE_TEMPLATES)]
        if i % 4 == 0:
            loc = generate_standalone_location()
        else:
            hub_name = random.choice(hub_names)
            loc = generate_location_near_hub(hubs[hub_name][0], hubs[hub_name][1], hub_name)
            
        venue = {
            "venue_id": f"v_{i+1001}",
            "name": f"{tpl['name']} ({loc['zone_name']})" if loc['zone_name'] != "独立区域" else tpl["name"],
            "category": tpl["cat"],
            "location": loc,
            "is_free": tpl["is_free"],
            "rating": round(random.uniform(4.0, 5.0), 1),
            "reviews_count": random.randint(100, 20000),
            "operating_hours": "09:00-22:00",
            "tags": tpl["tags"],
            "packages": [
                {
                    "package_id": f"pkg_{i+1001}_{j+1}",
                    "name": p["name"],
                    "price": p["price"],
                    "description": p["desc"],
                    "requires_booking": True if not tpl["is_free"] else False,
                    "available_stock": random.randint(20, 500),
                    "duration_mins": p.get("dur", 60),
                    "duration_std_dev": float(p.get("std", 15.0)),
                    "start_time": p.get("start")
                } for j, p in enumerate(tpl["packages"])
            ]
        }
        mock_db["activity_venues"].append(venue)
        
    # 3. 礼品店
    for i in range(8):
        tpl = GIFT_SHOP_TEMPLATES[i % len(GIFT_SHOP_TEMPLATES)]
        hub_name = random.choice(hub_names)
        loc = generate_location_near_hub(hubs[hub_name][0], hubs[hub_name][1], hub_name)
        
        delivery_info = tpl["delivery"]
        
        shop = {
            "shop_id": f"s_{i+1001}",
            "name": tpl["name"],
            "location": loc,
            "rating": round(random.uniform(4.5, 5.0), 1),
            "tags": tpl["tags"],
            "gifts": [
                {
                    "gift_id": f"g_{i+1001}_{j+1}",
                    "name": g["name"],
                    "price": g["price"],
                    "stock": g["stock"]
                } for j, g in enumerate(tpl["gifts"])
            ],
            "delivery_time_mins": delivery_info["mins"] if delivery_info else None,
            "delivery_time_std_dev": float(delivery_info["std"]) if delivery_info else None
        }
        mock_db["gift_shops"].append(shop)
        
    return mock_db

if __name__ == "__main__":
    random.seed(42) 
    data = generate_mock_db()
    
    os.makedirs("mock_db", exist_ok=True)
    with open("mock_db/restaurants.json", "w", encoding="utf-8") as f:
        json.dump(data["restaurants"], f, ensure_ascii=False, indent=2)
    with open("mock_db/activities.json", "w", encoding="utf-8") as f:
        json.dump(data["activity_venues"], f, ensure_ascii=False, indent=2)
    with open("mock_db/add_ons.json", "w", encoding="utf-8") as f:
        json.dump(data["gift_shops"], f, ensure_ascii=False, indent=2)
    if not os.path.exists("mock_db/reservations.json"):
        with open("mock_db/reservations.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
            
    print("Successfully generated and saved split files to mock_db/ directory")