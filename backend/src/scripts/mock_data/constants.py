import os
import json
import math
import random
import re
import sys
from typing import List, Dict, Any, Optional

MOCK_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("单人/双人", "轻量双人"),
    ("单人 / 双人", "轻量双人"),
    ("情侣约会", "朋友小聚"),
    ("浪漫约会", "仪式感小聚"),
    ("安静约会", "安静小聚"),
    ("下午约会", "下午小聚"),
    ("适合约会", "适合小聚"),
    ("情侣", "朋友"),
    ("约会", "小聚"),
    ("闺蜜", "朋友"),
    ("兄弟", "朋友"),
    ("浪漫", "氛围感"),
    ("适合单人", "适合轻量体验"),
    ("单人", "轻量"),
    ("一人食", "轻量餐"),
    ("一人", "轻量"),
    ("独处", "低打扰"),
    ("工作餐", "便捷餐"),
    ("solo", "friends"),
    ("couple", "friends"),
    ("teen", "friends"),
)

DEMO_FULL_COMBO_IDS = {"combo_024_3"}
DEMO_BACKUP_COMBO_IDS = {"combo_025_3", "combo_026_3"}
DEMO_SOLD_OUT_PACKAGE_IDS: set[str] = set()


def _sanitize_mock_text(value: str) -> str:
    """清洗非主线群体词，避免生成数据污染 family/friends 决策。"""
    out = value
    for old, new in MOCK_TEXT_REPLACEMENTS:
        out = out.replace(old, new)
    return out


def _sanitize_mock_list(values: list[str] | None) -> list[str]:
    """清洗字符串列表并去重。"""
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        cleaned = _sanitize_mock_text(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _sanitize_mock_dict(value: Any) -> Any:
    """递归清洗 Mock DB 输出对象中的展示文本。"""
    if isinstance(value, str):
        return _sanitize_mock_text(value)
    if isinstance(value, list):
        return [_sanitize_mock_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_mock_dict(v) for k, v in value.items()}
    return value

def _infer_receive_duration_mins(name: str, tags: list[str] | None) -> tuple[int, float]:
    n = name or ""
    t = " ".join(tags or [])
    if "蛋糕" in n or "蛋糕" in t:
        return 35, 8.0
    if "甜品" in n or "芝士" in n or "甜品" in t:
        return 20, 5.0
    if "鲜花" in t or "花艺" in n or "玫瑰" in n:
        return 10, 3.0
    return 12, 3.0

# =====================================================================
# 1. 核心数学库：高斯分布与商圈生成
# =====================================================================

def generate_hub_locations() -> dict[str, tuple[float, float]]:
    hubs = {}
    hub_configs = {
        "CBD核心商圈": (2.0, 4.5),
        "老城文化街区": (1.5, 4.0),
        "大学城商圈": (3.0, 5.5),
        "高新科技园": (3.5, 6.0),
    }
    
    for name, (min_r, max_r) in hub_configs.items():
        theta = random.uniform(0, 2 * math.pi)
        r = random.uniform(min_r, max_r)
        hubs[name] = (r * math.cos(theta), r * math.sin(theta))
        
    return hubs

def generate_location_near_hub(hub_x: float, hub_y: float, hub_name: str, sigma: float = 1.0) -> dict[str, Any]:
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
        "address": f"{hub_name}某商场{random.randint(1, 8)}F {random.randint(1, 999)}号铺",
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
        {"name": "单人工作餐冒菜", "price": 38.0, "desc": "牛油底料冒菜+现炸酥肉小份+冰粉+米饭", "features": "适合单人解馋，带来地道川味体验", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "双人浪漫约会餐", "price": 168.0, "desc": "经典红白鸳鸯锅底+特级雪花肥牛+手工虾滑+鲜毛肚+时蔬拼盘+酸梅汤2杯", "features": "专为情侣约会设计，精选鲜切食材，地道川味让你们的约会充满热辣激情！", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "温馨三口之家套餐", "price": 218.0, "desc": "番茄锅底+特级肥牛+虾滑+午餐肉+菌菇拼盘+手工面+儿童蒸蛋+大瓶鲜榨果汁", "features": "适合带小孩的家庭，营养番茄锅底搭配丰富肉类，老少皆宜。", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "青年四人欢聚套餐", "price": 288.0, "desc": "牛油红锅+脆毛肚+现炸酥肉+麻辣牛肉+鸭肠+时蔬拼盘+大窑4瓶", "features": "适合年轻朋友聚餐，招牌菜品一网打尽，越吃越过瘾！", "dur": 120, "std": 30, "slots": ["dinner", "late_night"]},
        {"name": "八人豪华包厢宴", "price": 888.0, "desc": "全牛宴拼盘+海鲜拼盘+极品毛肚+多种招牌小吃+精酿啤酒半打", "features": "高端包厢聚餐首选，奢华全牛宴与海鲜的碰撞，尽享尊贵。", "dur": 150, "std": 30, "slots": ["dinner"]}
    ]},
    {"name": "眉州东坡(亲子主题店)", "rating": 4.6, "tags": ["川菜", "家庭", "亲子", "老字号"], "combos": [
        {"name": "单人东坡肉盖饭", "price": 45.0, "desc": "招牌东坡肉+时令炒蔬+排骨汤+米饭", "features": "工作餐首选，招牌东坡肉肥而不腻。", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "2大1小温馨家庭餐(含儿童玩具)", "price": 188.0, "desc": "糖醋里脊+宫保鸡丁+清炒时蔬+鲜美鸡汤+儿童熊猫包点+米饭3份", "features": "专为三口之家定制，附赠精美儿童玩具，让孩子开心，家长省心。", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "三口之家周末欢聚宴", "price": 258.0, "desc": "东坡肘子+烤鸭半套+松仁玉米+砂锅鸡汤+特色小笼包", "features": "适合家庭周末大餐，经典名菜齐聚，营养均衡且极具仪式感。", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "1大1小营养儿童专属套餐", "price": 58.0, "desc": "主菜：鲜虾滑蛋、肉末蒸菜；汤品：南瓜浓汤；饮品：儿童果汁", "features": "1大1小轻松吃得营养又省心，清淡口味更友好。", "dur": 45, "std": 10, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "凑凑火锅·茶憩", "rating": 4.7, "tags": ["火锅", "奶茶", "打卡"], "combos": [
        {"name": "单人解馋小火锅", "price": 88.0, "desc": "台式麻辣小锅+精选肥牛+蔬菜拼盘+大红袍奶茶1杯", "features": "一人食也精致，火锅配奶茶的双倍快乐。", "dur": 60, "std": 10, "slots": ["lunch", "dinner", "late_night"]},
        {"name": "凑凑下午茶套餐", "price": 58.0, "desc": "大红袍奶茶2杯+台式精致甜点拼盘", "features": "闺蜜下午茶首选，环境优雅，出片率极高。", "dur": 45, "std": 15, "slots": ["afternoon_tea"]},
        {"name": "家庭欢乐火锅", "price": 268.0, "desc": "花胶鸡养颜锅+海鲜拼盘+黑猪肉片+蔬菜大拼+奶茶3杯", "features": "滋补养颜的花胶鸡锅，适合全家共享的健康火锅。", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "闺蜜四人局", "price": 328.0, "desc": "台式麻辣锅+和牛片+海鲜拼盘+爆浆牛丸+奶茶4杯", "features": "姐妹聚会必点，边吃火锅边喝奶茶，畅聊不设限。", "dur": 150, "std": 30, "slots": ["dinner", "late_night"]}
    ]},
    {"name": "蓝蛙西餐厅(亲子餐厅)", "rating": 4.5, "tags": ["西餐", "轻食", "汉堡", "亲子"], "combos": [
        {"name": "单人减脂轻食碗", "price": 68.0, "desc": "烟熏三文鱼藜麦沙拉+牛油果+低脂黑咖啡", "features": "健身达人首选，低卡高蛋白，美味无负担。", "dur": 40, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "2大1小迷你汉堡套餐", "price": 188.0, "desc": "招牌牛肉堡*2+儿童迷你鸡肉堡+炸薯条拼盘+软饮3杯", "features": "专为带娃家庭准备的汉堡狂欢，赠送儿童气球与涂鸦纸。", "dur": 60, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "家庭健康轻食餐", "price": 238.0, "desc": "考鸡肉牛油果沙拉+蘑菇培根意面+烤春鸡半只+鲜榨果汁3杯", "features": "轻负担的家庭聚餐，营养丰富，健康饮食的完美选择。", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "儿童趣味意面套餐", "price": 68.0, "desc": "番茄肉酱趣味通心粉+鲜果切+热牛奶", "features": "可爱的造型与酸甜口味，让挑食宝宝也能大快朵颐。", "dur": 45, "std": 10, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "王品牛排", "rating": 4.8, "tags": ["牛排", "庆生", "服务好"], "combos": [
        {"name": "单人尊享位上套餐", "price": 298.0, "desc": "经典台塑牛排+法式蘑菇浓汤+鲜果沙拉+焦糖布丁+餐后红茶", "features": "极致的单人西餐体验，感受王品独有的尊贵服务。", "dur": 90, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "情侣浪漫双人餐", "price": 588.0, "desc": "海陆双拼牛排2份+法式鹅肝+鱼子酱沙拉+玫瑰红酒2杯", "features": "浪漫约会天花板，提供撒花瓣与拍照服务，纪念日首选。", "dur": 120, "std": 15, "slots": ["dinner"]},
        {"name": "三口之家庆生宴", "price": 358.0, "desc": "台塑牛排+深海鳕鱼排+儿童迷你牛排+生日蛋糕+无酒精起泡酒", "features": "温馨家庭庆生，免费布置桌面并赠送合影相框。", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "四人臻选牛排套餐", "price": 458.0, "desc": "精选牛排4份+黑松露带子+凯撒沙拉+精选红酒1瓶", "features": "适合高端商务或家庭聚餐，尊享极致味蕾盛宴。", "dur": 150, "std": 20, "slots": ["dinner"]}
    ]},
    {"name": "胡大饭馆", "rating": 4.8, "tags": ["小龙虾", "宵夜", "青年"], "combos": [
        {"name": "双人深夜食堂", "price": 198.0, "desc": "麻辣小龙虾1.5斤+香辣蟹1份+烤馒头片+拍黄瓜+大扎啤", "features": "情侣或兄弟的深夜慰藉，经典麻辣口味引爆味蕾。", "dur": 90, "std": 20, "slots": ["dinner", "late_night"]},
        {"name": "三人微辣夜宵", "price": 268.0, "desc": "蒜蓉小龙虾2斤+烤肉筋半打+凉拌毛豆+招牌炒饭", "features": "不太能吃辣群体的福音，浓郁蒜香同样让人欲罢不能。", "dur": 120, "std": 30, "slots": ["dinner", "late_night"]},
        {"name": "四人麻辣小龙虾局", "price": 388.0, "desc": "麻辣小龙虾3斤+烤串拼盘20串+麻辣鸭头+大扎啤4杯", "features": "夏日夜宵王者，四人酣畅淋漓的剥虾大局。", "dur": 150, "std": 30, "slots": ["dinner", "late_night"]}
    ]},
    {"name": "点都德", "rating": 4.7, "tags": ["粤菜", "点心", "全天候"], "combos": [
        {"name": "单人早茶尝鲜", "price": 58.0, "desc": "金牌虾饺皇+荔湾艇仔粥+蜜汁叉烧包", "features": "一壶清茶三件点心，体验地道老广的早茶文化。", "dur": 45, "std": 10, "slots": ["breakfast", "lunch"]},
        {"name": "双人经典叹茶", "price": 138.0, "desc": "红米肠+百合酱凤爪+陈皮排骨+一壶普洱茶", "features": "两人闲聊的绝佳选择，招牌点心一次尝遍。", "dur": 90, "std": 30, "slots": ["breakfast", "lunch", "afternoon_tea"]},
        {"name": "家庭广式晚餐", "price": 218.0, "desc": "深井烧鹅双拼+干炒牛河+白灼菜心+流沙包+老火靓汤", "features": "适合全家老小的广式正餐，口味温和，营养滋补。", "dur": 90, "std": 15, "slots": ["dinner"]},
        {"name": "四人饮茶闲聊", "price": 268.0, "desc": "虾饺皇+红米肠+凤爪+排骨+蛋挞+皮蛋瘦肉粥+铁观音", "features": "朋友小聚，边喝茶边吃点心，惬意消磨时光。", "dur": 120, "std": 45, "slots": ["lunch", "afternoon_tea"]}
    ]},
    {"name": "外婆家(家庭体验店)", "rating": 4.4, "tags": ["家常菜", "温馨", "亲子"], "combos": [
        {"name": "单人外婆便当", "price": 28.0, "desc": "外婆红烧肉+炒青菜+紫菜蛋花汤+米饭", "features": "实惠暖心的工作餐，吃出外婆家的味道。", "dur": 30, "std": 5, "slots": ["lunch", "dinner"]},
        {"name": "双人回忆套餐", "price": 98.0, "desc": "外婆红烧肉+蒜蓉粉丝虾+麻婆豆腐+米饭2份", "features": "性价比极高的双人餐，经典家常菜满满都是回忆。", "dur": 60, "std": 10, "slots": ["lunch", "dinner"]},
        {"name": "2大1小外婆红烧肉套餐", "price": 138.0, "desc": "招牌红烧肉+清蒸鲈鱼+葱油娃娃菜+米饭3份", "features": "经典江南口味，鱼肉细嫩无刺，特别适合小朋友。", "dur": 60, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "三口之家营养鲜鱼套餐", "price": 158.0, "desc": "松鼠桂鱼+西红柿炒鸡蛋+外婆菜软饼+排骨瓦罐汤", "features": "酸甜开胃的松鼠桂鱼搭配家常美味，家庭聚餐不二之选。", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "四人大满足", "price": 208.0, "desc": "红烧肉+茶香鸡+宋嫂鱼羹+干煸四季豆+小笼包", "features": "四人超值欢聚餐，菜品丰富多样，聚餐氛围感拉满。", "dur": 90, "std": 20, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "比格披萨(亲子狂欢店)", "rating": 4.2, "tags": ["披萨", "自助", "平价", "亲子"], "combos": [
        {"name": "单人工作日自助", "price": 69.0, "desc": "单人全场披萨、意面、小吃、沙拉、饮料畅吃", "features": "打工人碳水快乐餐，无限量畅吃，性价比之王。", "dur": 90, "std": 15, "slots": ["lunch", "dinner"]},
        {"name": "2大1小家庭自助(含儿童烘焙体验)", "price": 188.0, "desc": "两位成人+一位儿童畅吃+儿童专属手工披萨DIY材料包", "features": "吃玩结合！孩子可以自己动手做披萨，好吃又好玩。", "dur": 120, "std": 20, "slots": ["lunch", "dinner"]},
        {"name": "四人畅吃派对", "price": 276.0, "desc": "四位成人全场自助畅吃+专属留位服务", "features": "学生党聚会、宿舍团建的绝佳去处，气氛热烈。", "dur": 120, "std": 30, "slots": ["lunch", "dinner"]}
    ]},
    {"name": "漫咖啡(休闲书吧店)", "rating": 4.6, "tags": ["咖啡", "下午茶", "休闲", "书吧"], "combos": [
        {"name": "单人安静办公套餐", "price": 48.0, "desc": "手冲咖啡1壶+经典巴斯克蛋糕1块", "features": "提供安静氛围与电源插座，适合带电脑的年轻人独处。", "dur": 90, "std": 20, "slots": ["lunch", "afternoon_tea", "dinner"]},
        {"name": "双人慵懒下午茶", "price": 108.0, "desc": "冰滴咖啡2杯+提拉米苏+水果松饼拼盘", "features": "全景落地窗旁，情侣或闺蜜看书聊天的绝佳角落。", "dur": 120, "std": 30, "slots": ["afternoon_tea"]},
        {"name": "儿童松饼欢乐套餐", "price": 88.0, "desc": "香蕉巧克力松饼大份+鲜榨橙汁2杯+手工小熊饼干", "features": "松软可口的甜点与果汁，让孩子乖乖坐着享受甜蜜时光。", "dur": 60, "std": 15, "slots": ["afternoon_tea", "dinner"]},
        {"name": "四人圆桌围读套餐", "price": 188.0, "desc": "大壶花果茶2壶+巨型蜂蜜厚多士+各类精美小蛋糕", "features": "适合小组讨论、读书会或桌游，空间宽敞氛围轻松。", "dur": 150, "std": 45, "slots": ["afternoon_tea", "dinner"]}
    ]},
    {"name": "隐溪茶楼(新中式茶馆)", "rating": 4.8, "tags": ["茶馆", "新中式", "打卡", "静谧"], "combos": [
        {"name": "单人静心品茗", "price": 68.0, "desc": "明前龙井1壶+绿豆糕+坚果小拼盘", "features": "独立私密小包间，适合一个人静心阅读或放空。", "dur": 90, "std": 15, "slots": ["lunch", "afternoon_tea", "dinner"]},
        {"name": "青年围炉煮茶(双人)", "price": 168.0, "desc": "炭火白茶1壶+烤橘子+烤板栗+烤柿子+红枣+中式糕点", "features": "极具出片率的新中式网红玩法，体验慢生活与人间烟火气。", "dur": 120, "std": 30, "slots": ["afternoon_tea", "dinner"]},
        {"name": "三口之家精致茶点", "price": 228.0, "desc": "养生大红袍1壶+儿童鲜榨果汁+中式象形点心拼盘(兔子/核桃造型)+新鲜水果", "features": "寓教于乐的国风体验，可爱的象形点心深受小朋友喜爱。", "dur": 120, "std": 20, "slots": ["afternoon_tea"]},
        {"name": "四人国风茶会局", "price": 318.0, "desc": "顶级正山小种/金骏眉双拼+全套茶点九宫格+特色小食", "features": "闺蜜聚会或商务洽谈的高端场所，穿汉服打卡有惊喜。", "dur": 150, "std": 30, "slots": ["afternoon_tea", "dinner"]}
    ]}
]
VENUE_TEMPLATES = [
    # --- 新增：短时/碎片化活动 ---
    {"name": "大玩家室内机动游戏厅", "cat": "休闲娱乐", "is_free": False, "tags": ["电玩", "抓娃娃", "短时"], "packages": [
        {"name": "单人50枚游戏币(抓娃娃)", "price": 39.9, "desc": "包含50枚游戏币，主打抓娃娃区与推币机，高爆率", "features": "适合学生党和情侣的碎片时间解压，体验满载而归的成就感！", "dur": 30, "std": 10},
        {"name": "情侣150枚游戏币特惠", "price": 99.0, "desc": "150枚游戏币，可畅玩双人跳舞机、摩托赛车、射击等机台", "features": "情侣约会互动好去处，双人合作游戏增进感情。", "dur": 90, "std": 30},
        {"name": "四人300币狂欢大礼包", "price": 188.0, "desc": "300枚游戏币，四人联机赛车、推币机、大乱斗包机体验", "features": "死党聚会必选，超多游戏币让你们玩到尽兴不心疼。", "dur": 120, "std": 45}
    ]},
    {"name": "咔嚓咔嚓自拍馆", "cat": "休闲娱乐", "is_free": False, "tags": ["拍照", "大头贴", "短时"], "packages": [
        {"name": "单人/双人韩式大头贴", "price": 35.0, "desc": "15分钟拍摄时间，含2张实体相纸与电子底片，立等可取", "features": "逛街途中的可爱记录，韩式滤镜一秒变身爱豆。", "dur": 20, "std": 5},
        {"name": "四人闺蜜换装自拍(半小时)", "price": 128.0, "desc": "30分钟包间自拍，提供JK制服/复古洋装换装，含4张实体相纸", "features": "闺蜜们的欢乐秀场，海量道具与服装，出片率100%。", "dur": 45, "std": 10}
    ]},
    {"name": "星际VR体验舱", "cat": "休闲娱乐", "is_free": False, "tags": ["VR", "短时", "刺激"], "packages": [
        {"name": "单人《过山车》VR体验", "price": 45.0, "desc": "10分钟极限失重VR过山车体验，配备动感座椅与风效", "features": "胆小者慎入！最真实的失重感，释放压力的绝佳选择。", "dur": 15, "std": 2},
        {"name": "双人《丧尸危机》VR射击", "price": 88.0, "desc": "15分钟双人联机防守射击，沉浸式丧尸围城体验", "features": "情侣/兄弟默契大考验，背靠背迎击尸潮，刺激爆表！", "dur": 20, "std": 5},
        {"name": "家庭/四人包舱半小时", "price": 198.0, "desc": "30分钟专属包舱，几十款儿童/射击/风景VR游戏任意轮换", "features": "适合家庭尝鲜体验，老少皆宜的虚拟现实之旅。", "dur": 30, "std": 5}
    ]},

    # --- 游乐园 / 主题乐园 ---
    {"name": "融创乐园", "cat": "游乐园", "is_free": False, "tags": ["刺激", "亲子", "大型"], "packages": [
        {"name": "成人单人欢乐套票", "price": 218.0, "desc": "全园通票，含过山车、大摆锤等30项大型游乐设施无限次畅玩", "features": "挑战极限，适合喜爱刺激与心跳的年轻玩家。", "dur": 480, "std": 60},
        {"name": "2大1小家庭通票", "price": 458.0, "desc": "两大一小全园通票，重点包含梦幻旋转木马、儿童攀爬区等温和项目", "features": "完美的家庭周末计划，让孩子在童话世界中尽情放电。", "dur": 480, "std": 90},
        {"name": "青年四人成团特惠", "price": 788.0, "desc": "四人同行套票，打卡四大镇园之宝过山车，赠送快速通行证1次", "features": "朋友组团刷项目首选，性价比高，尖叫连连。", "dur": 480, "std": 60}
    ]},
    
    # --- 密室 / 剧本杀 / 桌游 ---
    {"name": "X-cape 沉浸式机械密室", "cat": "密室逃脱", "is_free": False, "tags": ["机械", "烧脑", "无NPC"], "packages": [
        {"name": "《达芬奇的密码》双人", "price": 236.0, "desc": "90分钟纯机械解密，无恐怖元素，大量声光电逻辑谜题", "features": "智商碾压局！适合硬核推理爱好者与情侣合作解密。", "dur": 90, "std": 15, "start": "14:00"},
        {"name": "《盗墓迷影》四人组局", "price": 472.0, "desc": "100分钟中国风古墓探险，大型机械升降机关", "features": "身临其境的摸金校尉体验，团队协作解开千年古墓之谜。", "dur": 100, "std": 20, "start": "16:30"},
        {"name": "《生化危机》四人微恐", "price": 512.0, "desc": "100分钟微恐解密，有单人搜证环节与轻微Jump Scare", "features": "又菜又爱玩的必选，氛围感拉满，肾上腺素狂飙。", "dur": 100, "std": 15, "start": "19:00"}
    ]},
    {"name": "剧好玩·全息投影剧本杀", "cat": "休闲娱乐", "is_free": False, "tags": ["剧本杀", "换装", "飙戏"], "packages": [
        {"name": "《九霄寒夜》古风四人车", "price": 552.0, "desc": "4-5小时情感演绎本，提供全套精美汉服妆造与全息投影场景", "features": "一秒穿越古代，沉浸式飙戏落泪，体验别样人生。", "dur": 300, "std": 45, "start": "18:00"},
        {"name": "硬核推理本(包场)", "price": 888.0, "desc": "不限时硬核还原本包场，提供零食饮料与专属DM全程扶车", "features": "推土机玩家的终极战场，逻辑严密，盘到天明。", "dur": 360, "std": 60, "start": "20:00"}
    ]},

    # --- 电影院 ---
    {"name": "万达影城(万达广场店)", "cat": "电影院", "is_free": False, "tags": ["IMAX", "商场内", "停车方便"], "packages": [
        {"name": "《沙丘2》IMAX 2D 10:00场", "price": 45.0, "desc": "早场特惠，IMAX巨幕影厅，极致视听震撼", "features": "影迷必看的史诗级巨幕体验，早场人少观影体验更佳。", "dur": 166, "std": 2, "start": "10:00"},
        {"name": "《飞驰人生3》双人套票", "price": 118.0, "desc": "黄金场次双人票，含大份爆米花与2杯可乐", "features": "情侣约会标配，边吃爆米花边享受欢乐喜剧。", "dur": 130, "std": 2, "start": "19:30"},
        {"name": "《功夫熊猫6》2大1小家庭票", "price": 128.0, "desc": "下午场动画主题厅，提供儿童增高坐垫", "features": "带娃轻松过周末，欢乐治愈的家庭亲子时光。", "dur": 100, "std": 5, "start": "15:00"},
        {"name": "《流浪地球3》四人套餐", "price": 228.0, "desc": "晚间黄金场4张连座票，国产科幻巨制", "features": "朋友组局看大片，共同见证震撼的科幻名场面。", "dur": 150, "std": 2, "start": "20:00"}
    ]},

    # --- 体育 / 运动 ---
    {"name": "极速卡丁车俱乐部", "cat": "体育运动", "is_free": False, "tags": ["竞速", "团建", "短时"], "packages": [
        {"name": "单人单节体验(8分钟)", "price": 128.0, "desc": "提供专业头盔与赛服，畅跑8-10圈室内专业赛道", "features": "体验贴地飞行的速度与激情，成为秋名山车神。", "dur": 30, "std": 5},
        {"name": "2大1小亲子套票", "price": 288.0, "desc": "双人卡丁车(家长带娃)一节 + 单人儿童车一节", "features": "培养孩子的赛车梦，安全又酷炫的亲子运动体验。", "dur": 45, "std": 10},
        {"name": "四人迷你大奖赛", "price": 588.0, "desc": "含8分钟练习赛+10圈正赛，颁发冠亚军奖牌", "features": "兄弟间的实力较量，谁是真正的车神赛道见分晓！", "dur": 90, "std": 15}
    ]},

    # --- 展览 / 博物馆 ---
    {"name": "省博物院", "cat": "博物馆", "is_free": True, "tags": ["历史", "免费", "室内"], "packages": [
        {"name": "基本陈列免费参观", "price": 0.0, "desc": "免费预约入馆，可参观青铜器、陶瓷等五大基本展厅", "features": "零成本的文化熏陶，适合一个人静静欣赏历史瑰宝。", "dur": 180, "std": 45},
        {"name": "人工讲解服务(适合家庭)", "price": 150.0, "desc": "资深讲解员带看2小时，深入解读镇馆之宝背后的故事", "features": "让文物活起来，极其适合带孩子的家庭，寓教于乐。", "dur": 120, "std": 10}
    ]}
]

GIFT_SHOP_TEMPLATES = [
    {"name": "花点时间·精品花艺", "tags": ["鲜花", "浪漫", "惊喜"], "delivery": {"mins": 60, "std": 15}, "gifts": [
        {"name": "单支红玫瑰精美包装", "price": 39.0, "desc": "厄瓜多尔进口红玫瑰，配满天星与高档黑色包装纸", "features": "小小的浪漫不经意间送出，适合日常小惊喜。", "stock": 50},
        {"name": "99朵红玫瑰花束", "price": 399.0, "desc": "99朵A级红玫瑰巨型花束，代表天长地久", "features": "求婚、纪念日大杀器，抱在怀里绝对吸睛！", "stock": 10},
        {"name": "向日葵清新混搭花篮", "price": 168.0, "desc": "3支向日葵搭配尤加利叶与洋桔梗，阳光活力", "features": "送朋友或探望长辈的最佳选择，寓意阳光向上。", "stock": 25}
    ]},
    {"name": "泡泡玛特 POP MART", "tags": ["潮玩", "盲盒", "青年"], "delivery": None, "gifts": [
        {"name": "Skullpanda 密林古堡盲盒端盒(12个)", "price": 828.0, "desc": "整盒未拆封12个，必出常规款，有概率开出隐藏款", "features": "土豪端盒玩法，不用猜不用摇，快乐直接拉满！", "stock": 5},
        {"name": "Dimoo 随机盲盒(单盒)", "price": 69.0, "desc": "Dimoo最新系列盲盒1个，款式随机", "features": "试试手气，拆开瞬间的未知感最让人上头。", "stock": 200}
    ]},
    {"name": "好利来蛋糕房", "tags": ["蛋糕", "庆生", "大众"], "delivery": {"mins": 45, "std": 10}, "gifts": [
        {"name": "6英寸经典黑森林蛋糕", "price": 168.0, "desc": "樱桃酒香夹心，外层铺满纯脂巧克力碎，附送蜡烛刀叉", "features": "经典永不过时，适合3-4人小型生日派对。", "stock": 15},
        {"name": "8英寸鲜奶水果蛋糕", "price": 198.0, "desc": "动物奶油搭配当季新鲜草莓、芒果等水果", "features": "老人小孩都爱吃的清甜口味，家庭庆生必备。", "stock": 10},
        {"name": "半熟芝士(一盒5枚)", "price": 38.0, "desc": "招牌半熟芝士，入口即化，奶香浓郁", "features": "超人气网红甜品，下午茶解馋绝佳伴侣。", "stock": 50}
    ]},
    {"name": "酷乐潮玩杂物社", "tags": ["礼品", "创意", "平价"], "delivery": {"mins": 30, "std": 10}, "gifts": [
        {"name": "恶搞搞怪抱枕", "price": 49.0, "desc": "单身狗/咸鱼造型超软毛绒抱枕，尺寸60cm", "features": "送给损友的搞怪礼物，实用又好笑。", "stock": 50},
        {"name": "创意减压发泄玩具套装", "price": 29.9, "desc": "捏捏乐、无限气泡纸、尖叫鸡三件套", "features": "打工人的解压神器，捏一捏烦恼全飞走。", "stock": 100},
        {"name": "文艺复古手帐本礼盒", "price": 68.0, "desc": "复古牛皮面笔记本+烫金羽毛笔+和纸胶带", "features": "送给文艺青年的高颜值礼盒，记录生活点滴。", "stock": 30}
    ]},
    {"name": "良品铺子 / 百草味", "tags": ["零食", "休闲", "伴手礼"], "delivery": {"mins": 30, "std": 5}, "gifts": [
        {"name": "巨型坚果大礼包", "price": 128.0, "desc": "包含夏威夷果、开心果、核桃等10袋坚果，总重1.5kg", "features": "追剧必备，过节走亲访友提着也有面子。", "stock": 50},
        {"name": "猪肉脯+辣条休闲零食包", "price": 68.0, "desc": "靖江猪肉脯、大面筋、魔芋爽等8款重口味零食", "features": "无辣不欢爱好者的福音，越嚼越香。", "stock": 80}
    ]},
    {"name": "名创优品 MINISO", "tags": ["生活", "玩偶", "平价"], "delivery": None, "gifts": [
        {"name": "三丽鸥联名公仔(中号)", "price": 59.9, "desc": "库洛米/美乐蒂正版授权毛绒公仔，约35cm", "features": "萌化少女心，抱在怀里安全感十足。", "stock": 30},
        {"name": "香薰精油无火藤条套装", "price": 39.9, "desc": "白茶/蓝风铃香型，含扩香藤条与100ml精油", "features": "提升房间格调的平价好物，清香宜人。", "stock": 50},
        {"name": "旅行分装瓶收纳包", "price": 19.9, "desc": "硅胶分装瓶3个+防水透明收纳袋", "features": "出差旅行必备实用小物件，登机无忧。", "stock": 100}
    ]}
]

# =====================================================================
# 3. 组装数据与导出
# =====================================================================

def _choose_restaurant_sub_category(tags: list[str]) -> str:
    t = " ".join(tags or [])
    if "粤" in t or "点心" in t:
        return "粤菜"
    if "火锅" in t:
        return "火锅"
    if "牛排" in t:
        return "西餐"
    if "小龙虾" in t or "宵夜" in t or "烧烤" in t:
        return "夜宵"
    if "咖啡" in t or "下午茶" in t or "茶馆" in t:
        return "下午茶"
    if "披萨" in t or "汉堡" in t or "轻食" in t:
        return "轻食"
    if "川菜" in t or "麻辣" in t:
        return "川菜"
    return "家常菜"


def _choose_gift_shop_sub_category(tags: list[str]) -> str:
    t = " ".join(tags or [])
    if "鲜花" in t or "氛围感" in t:
        return "鲜花"
    if "蛋糕" in t or "庆生" in t:
        return "蛋糕"
    if "潮玩" in t or "盲盒" in t or "玩偶" in t:
        return "潮玩"
    if "文创" in t or "手帐" in t or "复古" in t:
        return "文创"
    if "零食" in t:
        return "零食"
    return "礼品"


def _keywords_for_profile(*, category: str, profile: str, indoor: bool, sub_category: str, delivery_supported: bool) -> list[str]:
    base: list[str] = []
    if category == "restaurant":
        if profile == "family_mild":
            base += ["适合亲子", "口味清淡", "可做不辣", "空间宽敞", "饭点人多", "建议预约"]
        elif profile == "couple_photo":
            base += ["适合小聚", "适合拍照", "氛围感", "灯光舒服", "热门打卡", "建议预约"]
        elif profile == "friends_lively":
            base += ["适合朋友聚会", "热闹", "适合多人", "上菜快", "饭点排队", "建议预约"]
        elif profile == "kids_friendly":
            base += ["儿童友好", "适合3-6岁", "口味清淡", "有儿童座椅", "空间宽敞", "周末人多"]
        else:
            base += ["适合轻量体验", "环境安静", "出餐快", "性价比高", "不用排队", "可做不辣"]

        if sub_category:
            base.append(sub_category)

    elif category == "activity":
        if profile == "solo_quiet":
            base += ["适合轻量体验", "环境安静", "适合放松", "不拥挤", "适合避开人群", "室内" if indoor else "户外"]
        elif profile == "couple_photo":
            base += ["适合小聚", "适合拍照", "出片", "氛围感", "互动性强", "室内" if indoor else "户外"]
        elif profile == "family_3_6":
            base += ["适合亲子", "适合3-6岁", "儿童友好", "适合放电", "室内" if indoor else "户外", "周末人多"]
        elif profile == "family_7_10":
            base += ["适合亲子", "适合7-10岁", "寓教于乐", "轻运动", "室内" if indoor else "户外", "建议预约"]
        elif profile == "teen_11_17":
            base += ["适合朋友", "适合11-17岁", "刺激", "沉浸式体验", "室内" if indoor else "户外", "建议预约"]
        elif profile == "friends_lively":
            base += ["适合朋友聚会", "热闹", "互动", "解压", "室内" if indoor else "户外", "建议预约"]
        else:
            base += ["通用兜底", "适合散步", "不踩雷", "室内" if indoor else "户外", "交通方便", "随到随玩"]

        if sub_category:
            base.append(sub_category)

    else:
        if profile == "couple_atmosphere":
            base += ["适合小聚", "氛围感", "惊喜", "高级感", "可同城配送" if delivery_supported else "可自提"]
        elif profile == "birthday_friends":
            base += ["适合朋友聚会", "庆生", "有团购", "出品稳定", "可同城配送" if delivery_supported else "可自提"]
        elif profile == "kids":
            base += ["适合亲子", "儿童喜欢", "可爱", "适合送礼", "可同城配送" if delivery_supported else "可自提"]
        else:
            base += ["通用文创", "好看", "适合送礼", "打卡", "可同城配送" if delivery_supported else "可自提"]

        if sub_category:
            base.append(sub_category)

    out: list[str] = []
    seen: set[str] = set()
    for x in base:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _render_sectionalized_description(sub_category: str, raw_desc: str) -> str:
    desc = (raw_desc or "").strip()
    if not desc:
        return ""
    if "：" in desc and "；" in desc:
        return desc

    if any(k in sub_category for k in ("火锅", "夜宵", "烧烤")):
        return f"锅底：本店招牌锅底；荤菜：{desc}；素菜：时蔬拼盘；主食：米饭/面食；饮品：解腻饮品"
    if any(k in sub_category for k in ("下午茶", "咖啡", "茶")):
        return f"饮品：{desc}；甜品：当日甜点；小食：咸甜小食；加点：可选加点"
    if any(k in sub_category for k in ("西餐", "轻食", "Brunch")):
        return f"主菜：{desc}；配菜：沙拉/配菜；饮品：特调饮品；甜品：餐后甜点"

    return f"主菜：{desc}；配菜：时令配菜；汤品：暖汤；主食：米饭/面食；饮品：解腻饮品"


def _ensure_people_expr_in_name(name: str, *, default_people_expr: str) -> str:
    n = name or ""
    if re.search(r"(单人|一人|双人|两人|三人|四人|五人|六人|\d+人|\d+大\d+小|\d+大|\d+小|三口之家|四口之家)", n):
        return n
    return f"{default_people_expr}{n}"


def _infer_default_people_expr_for_combo(*, combo_name: str, restaurant_tags: list[str]) -> str:
    name = combo_name or ""
    tags_text = " ".join(restaurant_tags or [])
    if re.search(r"\d+\s*大\s*\d+\s*小", name):
        return "2大1小"
    if any(k in name for k in ("儿童", "亲子", "宝宝")) or any(k in tags_text for k in ("亲子", "儿童", "家庭")):
        return "2大1小"
    if any(k in name for k in ("轻量", "便捷餐", "便当")) or "轻量" in tags_text:
        return "双人"
    if any(k in name for k in ("四", "多人", "聚会", "团建", "派对")) or any(k in tags_text for k in ("聚会", "热闹")):
        return "四人"
    return "双人"


def _render_sections(sections: dict[str, list[str]]) -> str:
    parts: list[str] = []
    for k, items in sections.items():
        if not items:
            continue
        parts.append(f"{k}：" + "、".join(items))
    return "；".join(parts)


