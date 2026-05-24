import os
import json
import math
import random
import re
import sys
from typing import List, Dict, Any, Optional

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
    if "鲜花" in t or "浪漫" in t:
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
            base += ["适合约会", "适合拍照", "氛围浪漫", "灯光舒服", "热门打卡", "建议预约"]
        elif profile == "friends_lively":
            base += ["适合朋友聚会", "热闹", "适合多人", "上菜快", "饭点排队", "建议预约"]
        elif profile == "kids_friendly":
            base += ["儿童友好", "适合3-6岁", "口味清淡", "有儿童座椅", "空间宽敞", "周末人多"]
        else:
            base += ["适合单人", "环境安静", "出餐快", "性价比高", "不用排队", "可做不辣"]

        if sub_category:
            base.append(sub_category)

    elif category == "activity":
        if profile == "solo_quiet":
            base += ["适合单人", "环境安静", "适合放松", "不拥挤", "适合避开人群", "室内" if indoor else "户外"]
        elif profile == "couple_photo":
            base += ["适合约会", "适合拍照", "出片", "氛围感", "互动性强", "室内" if indoor else "户外"]
        elif profile == "family_3_6":
            base += ["适合亲子", "适合3-6岁", "儿童友好", "适合放电", "室内" if indoor else "户外", "周末人多"]
        elif profile == "family_7_10":
            base += ["适合亲子", "适合7-10岁", "寓教于乐", "轻运动", "室内" if indoor else "户外", "建议预约"]
        elif profile == "teen_11_17":
            base += ["适合青少年", "适合11-17岁", "刺激", "沉浸式体验", "室内" if indoor else "户外", "建议预约"]
        elif profile == "friends_lively":
            base += ["适合朋友聚会", "热闹", "互动", "解压", "室内" if indoor else "户外", "建议预约"]
        else:
            base += ["通用兜底", "适合散步", "不踩雷", "室内" if indoor else "户外", "交通方便", "随到随玩"]

        if sub_category:
            base.append(sub_category)

    else:
        if profile == "couple_atmosphere":
            base += ["适合约会", "氛围感", "惊喜", "高级感", "可同城配送" if delivery_supported else "可自提"]
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
    if any(k in name for k in ("单人", "一人", "工作餐", "便当")) or "单人" in tags_text:
        return "单人"
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
    if any(k in text for k in ("浪漫", "约会", "纪念日", "景观", "花艺", "鲜花", "巧克力")):
        experience_tags.append("浪漫")
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

    matched = _matched_keywords(review_keywords, ("惊喜", "仪式感", "庆生", "约会", "氛围"))
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
    if is_western and any(k in title_style for k in ("情侣", "纪念日")):
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


def generate_mock_db() -> dict[str, Any]:
    hubs = generate_hub_locations()
    hub_names = list(hubs.keys())
    
    mock_db = {
        "restaurants": [],
        "activity_venues": [],
        "gift_shops": []
    }
    
    restaurant_plan: list[dict] = (
        [
            {"sub_category": "粤菜", "name": "点都德", "profile": "family_mild", "tags": ["少辣", "家庭", "亲子"]},
            {"sub_category": "茶餐厅", "name": "莲香茶餐厅", "profile": "family_mild", "tags": ["少辣", "家庭", "单人"]},
            {"sub_category": "粤菜", "name": "翠华茶餐厅", "profile": "family_mild", "tags": ["少辣", "家庭", "兜底"]},
            {"sub_category": "江浙菜", "name": "外婆家", "profile": "family_mild", "tags": ["少辣", "家庭", "安静"]},
            {"sub_category": "本帮菜", "name": "老上海本帮菜馆", "profile": "family_mild", "tags": ["少辣", "家庭", "安静约会"]},
            {"sub_category": "江浙菜", "name": "苏浙小馆", "profile": "family_mild", "tags": ["少辣", "家庭", "安静"]},
            {"sub_category": "家常菜", "name": "社区家常小馆", "profile": "family_mild", "tags": ["低预算", "家庭", "单人"]},
            {"sub_category": "社区小馆", "name": "巷口小馆", "profile": "family_mild", "tags": ["低预算", "家庭", "单人"]},
            {"sub_category": "连锁简餐", "name": "和府捞面·家庭简餐", "profile": "family_mild", "tags": ["亲子", "少走路", "兜底"]},
            {"sub_category": "商场家庭餐厅", "name": "商场家庭餐厅·轻简餐", "profile": "family_mild", "tags": ["亲子", "少走路", "室内"]},
            {"sub_category": "西餐", "name": "王品牛排", "profile": "couple_photo", "tags": ["纪念日", "情侣", "安静"]},
            {"sub_category": "西餐", "name": "蓝蛙西餐厅", "profile": "couple_photo", "tags": ["意面", "牛排", "约会"]},
            {"sub_category": "Brunch", "name": "Brunch Lab", "profile": "couple_photo", "tags": ["轻食", "下午约会", "拍照"]},
            {"sub_category": "景观餐厅", "name": "云顶露台景观餐厅", "profile": "couple_photo", "tags": ["拍照", "夜景", "浪漫"]},
            {"sub_category": "甜品下午茶", "name": "甜里·下午茶", "profile": "couple_photo", "tags": ["女生友好", "拍照", "甜品"]},
            {"sub_category": "日式定食", "name": "和风寿喜锅定食", "profile": "couple_photo", "tags": ["少辣", "安静", "约会"]},
            {"sub_category": "融合菜", "name": "融·精致融合菜", "profile": "couple_photo", "tags": ["高体验", "出片", "预约"]},
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
            {"sub_category": "咖啡简餐", "name": "漫咖啡·简餐", "profile": "solo_light", "tags": ["单人", "放松", "安静"]},
            {"sub_category": "日式拉面乌冬", "name": "一乐拉面·乌冬", "profile": "solo_light", "tags": ["单人", "快速", "少辣"]},
            {"sub_category": "面包烘焙简餐", "name": "面包研究所·烘焙简餐", "profile": "solo_light", "tags": ["下午轻食", "单人", "烘焙"]},
            {"sub_category": "粉面饭轻餐", "name": "粉面小铺", "profile": "solo_light", "tags": ["预算低", "时间短", "单人"]},
        ]
    )

    for i, plan in enumerate(restaurant_plan):
        sub_category = plan["sub_category"]
        district = random.choice(hub_names)
        hub_x, hub_y = hubs[district]
        loc = generate_location_near_hub(hub_x, hub_y, district)
        business_hours = random.choice(["10:00-22:00", "11:00-22:30", "09:30-21:30"])
        indoor = False if sub_category in ("景观餐厅",) else True
        tags = list(plan.get("tags") or [])
        review_keywords = _keywords_for_profile(
            category="restaurant",
            profile=str(plan["profile"]),
            indoor=bool(indoor),
            sub_category=sub_category,
            delivery_supported=False,
        )
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

        if plan["profile"] == "family_mild":
            combos += [
                _build_combo(sub_category=sub_category, people_expr="单人", title_style="单人工作日便饭", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人清淡分享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="2大1小家庭套餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人家庭聚餐", slots=["dinner"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人家常共享餐", slots=["lunch", "dinner"], is_western=is_western),
            ]
        elif plan["profile"] == "couple_photo":
            combos += [
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="情侣浪漫双人餐", slots=["dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="工作日双人约会餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="单人", title_style="单人轻松小食", slots=["lunch", "afternoon_tea"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="四人", title_style="四人庆生分享餐", slots=["dinner"], is_western=is_western),
            ]
            combos += [
                _build_low_price_combo(people_expr="2-4人", title_style="2-4人小份共享", slots=["afternoon_tea", "dinner"]),
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
            if len(combos) >= 2:
                combos[0] = _build_combo(sub_category=sub_category, people_expr="1大1小", title_style="1大1小下午茶亲子点心", slots=["afternoon_tea"], is_western=is_western)
                combos[1] = _build_combo(sub_category=sub_category, people_expr="2大1小", title_style="2大1小下午茶亲子点心", slots=["afternoon_tea"], is_western=is_western)
        else:
            combos += [
                _build_combo(sub_category=sub_category, people_expr="单人", title_style="单人快速轻餐", slots=["lunch", "dinner", "afternoon_tea"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人随享套餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_combo(sub_category=sub_category, people_expr="双人", title_style="双人下午轻食", slots=["afternoon_tea"], is_western=is_western),
            ]
            combos += [
                _build_combo(sub_category=sub_category, people_expr="2-4人", title_style="2-4人共享餐", slots=["lunch", "dinner"], is_western=is_western),
                _build_low_price_combo(people_expr="单人", title_style="单人平价便当", slots=["lunch", "dinner"]),
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
        mock_db["restaurants"].append(restaurant)
        
    activity_plan: list[dict] = (
        [
            {"sub_category": "独立书店", "name": "纸上时光·独立书店", "profile": "solo_quiet", "indoor": True, "is_free": True, "tags": ["安静", "低预算"]},
            {"sub_category": "独立书店", "name": "巷口书店", "profile": "solo_quiet", "indoor": True, "is_free": True, "tags": ["安静", "低预算"]},
            {"sub_category": "咖啡书房", "name": "静读咖啡书房", "profile": "solo_quiet", "indoor": True, "is_free": False, "tags": ["学习", "放松"]},
            {"sub_category": "小型展览", "name": "小城艺术空间", "profile": "solo_quiet", "indoor": True, "is_free": False, "tags": ["轻文化", "安静"]},
            {"sub_category": "美术馆", "name": "城市美术馆", "profile": "solo_quiet", "indoor": True, "is_free": False, "tags": ["拍照", "放松"]},
            {"sub_category": "安静手作体验", "name": "治愈手作工坊", "profile": "solo_quiet", "indoor": True, "is_free": False, "tags": ["治愈", "轻互动"]},
            {"sub_category": "沉浸式展览", "name": "光影沉浸式展", "profile": "couple_photo", "indoor": True, "is_free": False, "tags": ["拍照", "出片"]},
            {"sub_category": "陶艺手作", "name": "双人陶艺工坊", "profile": "couple_photo", "indoor": True, "is_free": False, "tags": ["互动", "纪念感"]},
            {"sub_category": "香薰手作", "name": "香气研究所·香薰DIY", "profile": "couple_photo", "indoor": True, "is_free": False, "tags": ["互动", "纪念感"]},
            {"sub_category": "私人影院", "name": "小众私人影院", "profile": "couple_photo", "indoor": True, "is_free": False, "tags": ["雨天", "晚间"]},
            {"sub_category": "夜景观景点", "name": "城市天台观景点", "profile": "couple_photo", "indoor": False, "is_free": True, "tags": ["夜景", "浪漫"]},
            {"sub_category": "复古街区", "name": "复古创意街区", "profile": "couple_photo", "indoor": False, "is_free": True, "tags": ["散步", "拍照"]},
            {"sub_category": "花艺体验", "name": "花艺手作体验馆", "profile": "couple_photo", "indoor": True, "is_free": False, "tags": ["情绪价值", "手作"]},
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
            {"sub_category": "VR体验馆", "name": "星际VR体验馆", "profile": "teen_11_17", "indoor": True, "is_free": False, "tags": ["刺激", "朋友"]},
            {"sub_category": "密室逃脱(轻恐)", "name": "沉浸式密室(轻恐/非恐)", "profile": "teen_11_17", "indoor": True, "is_free": False, "tags": ["11+", "刺激"]},
            {"sub_category": "剧本杀(轻量本)", "name": "轻量剧本杀馆", "profile": "teen_11_17", "indoor": True, "is_free": False, "tags": ["13+", "沉浸"]},
            {"sub_category": "保龄球/台球/飞镖", "name": "保龄球台球飞镖馆", "profile": "teen_11_17", "indoor": True, "is_free": False, "tags": ["运动", "朋友"]},
            {"sub_category": "电玩城/街机厅", "name": "电玩城街机厅", "profile": "teen_11_17", "indoor": True, "is_free": False, "tags": ["青少年", "解压"]},
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
            start_time: str | None,
        ) -> dict:
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
            if profile == "solo_quiet":
                return [
                    _mk(
                        k=1,
                        name="单人自由入场",
                        price=0.0,
                        description="自由入场体验，可随到随逛/随到随玩",
                        features="节奏更松弛，适合一个人放空或阅读。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration),
                        duration_std_dev=20.0,
                        start_time=None,
                    ),
                    _mk(
                        k=2,
                        name="单人安静时段(免票)",
                        price=0.0,
                        description="指定安静时段入场，环境更稳定",
                        features="更适合独处与低干扰体验。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration - 15),
                        duration_std_dev=15.0,
                        start_time=None,
                    ),
                ]

            if profile == "couple_photo":
                return [
                    _mk(
                        k=1,
                        name="双人散步打卡",
                        price=0.0,
                        description="自由路线打卡，可随到随拍",
                        features="更适合两人轻松聊天与拍照记录。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration),
                        duration_std_dev=20.0,
                        start_time=None,
                    ),
                    _mk(
                        k=2,
                        name="双人夜景拍照路线(免票)",
                        price=0.0,
                        description="推荐视角与拍照点位，适合慢慢走",
                        features="氛围更好，出片更稳定。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration + 15),
                        duration_std_dev=25.0,
                        start_time=None,
                    ),
                ]

            if profile in ("family_3_6", "family_7_10"):
                return [
                    _mk(
                        k=1,
                        name="2大1小免费入场",
                        price=0.0,
                        description="家庭友好入场规则，儿童可陪同体验",
                        features="更适合亲子一起消磨时间，省心省力。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration),
                        duration_std_dev=25.0,
                        start_time=None,
                    ),
                    _mk(
                        k=2,
                        name="亲子轻体验(免票)",
                        price=0.0,
                        description="更短更轻量的体验路线，避免孩子疲惫",
                        features="节奏更友好，适合带娃兜底。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(45, base_duration - 30),
                        duration_std_dev=20.0,
                        start_time=None,
                    ),
                ]

            if profile == "teen_11_17":
                return [
                    _mk(
                        k=1,
                        name="2-4人体验票",
                        price=0.0,
                        description="支持小团体一起体验，更适合结伴",
                        features="节奏更紧凑，适合短时间上手。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(45, base_duration - 15),
                        duration_std_dev=15.0,
                        start_time=None,
                    ),
                    _mk(
                        k=2,
                        name="3-5人挑战票(免票)",
                        price=0.0,
                        description="适合多人一起完成挑战的玩法路线",
                        features="更强调配合与互动，氛围更热烈。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration),
                        duration_std_dev=20.0,
                        start_time=None,
                    ),
                ]

            if profile == "friends_lively":
                return [
                    _mk(
                        k=1,
                        name="3-5人自由入场",
                        price=0.0,
                        description="无需预约，适合临时组局",
                        features="更适合朋友聚会，随到随玩。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration),
                        duration_std_dev=25.0,
                        start_time=None,
                    ),
                    _mk(
                        k=2,
                        name="4人小游戏挑战(免票)",
                        price=0.0,
                        description="推荐多人小游戏路线，简单上手",
                        features="互动更强，热闹但不费脑。",
                        requires_booking=False,
                        available_stock=9999,
                        duration_mins=max(60, base_duration - 15),
                        duration_std_dev=20.0,
                        start_time=None,
                    ),
                ]

            return [
                _mk(
                    k=1,
                    name="1-4人自由入场",
                    price=0.0,
                    description="自由入场体验，可随到随玩/随到随逛",
                    features="低决策成本，临时起意也很合适。",
                    requires_booking=False,
                    available_stock=9999,
                    duration_mins=max(60, base_duration),
                    duration_std_dev=20.0,
                    start_time=None,
                ),
                _mk(
                    k=2,
                    name="2-4人主题路线(免票)",
                    price=0.0,
                    description="推荐主题路线与玩法点位，按需选择",
                    features="更容易不踩雷，适合兜底安排。",
                    requires_booking=False,
                    available_stock=9999,
                    duration_mins=max(60, base_duration - 15),
                    duration_std_dev=20.0,
                    start_time=None,
                ),
            ]

        start_times = [None, "14:00", "15:00", "16:30", "18:00", "19:00", "20:00"]

        def _price(lo: float, hi: float) -> float:
            return float(rng.uniform(lo, hi))

        def _stock(lo: int, hi: int) -> int:
            return int(rng.randint(lo, hi))

        def _std(options: list[float]) -> float:
            return float(rng.choice(options))

        def _start_time() -> str | None:
            return rng.choice(start_times)

        if profile == "solo_quiet":
            return [
                _mk(
                    k=1,
                    name="单人标准体验",
                    price=_price(39.0, 128.0),
                    description="基础体验项目，包含入场与核心项目体验",
                    features="更适合一个人慢慢体验，节奏舒适。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(40, 500),
                    duration_mins=base_duration,
                    duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                    start_time=_start_time(),
                ),
                _mk(
                    k=2,
                    name="单人深度体验",
                    price=_price(79.0, 168.0),
                    description="进阶体验项目，包含更完整的内容与更长的体验时长",
                    features="更适合独处放松，体验更沉浸。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 320),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time=_start_time(),
                ),
                _mk(
                    k=3,
                    name="单人主题夜场",
                    price=_price(89.0, 188.0),
                    description="主题时段体验，氛围更稳定，适合晚间放松",
                    features="更适合一个人收尾一天的情绪与疲惫。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 220),
                    duration_mins=base_duration + 45,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time=_start_time(),
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
                    start_time=_start_time(),
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
                    start_time=_start_time(),
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
                    start_time=_start_time(),
                ),
            ]

        if profile in ("family_3_6", "family_7_10"):
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
                    start_time=_start_time(),
                ),
                _mk(
                    k=2,
                    name="2大1小亲子标准体验",
                    price=_price(79.0, 188.0),
                    description="更完整的亲子项目内容，适合家庭一起参与",
                    features="更适合周末安排，孩子更容易投入。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 320),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time=_start_time(),
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
                    start_time=_start_time(),
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
                    start_time=_start_time(),
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
                    start_time=_start_time(),
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
                    start_time=_start_time(),
                ),
            ]

        if profile == "friends_lively":
            return [
                _mk(
                    k=1,
                    name="三人小聚体验",
                    price=_price(69.0, 168.0),
                    description="适合三人小聚的基础玩法，简单上手",
                    features="更适合朋友聚会，互动轻松。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(30, 460),
                    duration_mins=base_duration,
                    duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                    start_time=_start_time(),
                ),
                _mk(
                    k=2,
                    name="四人欢聚畅玩",
                    price=_price(99.0, 228.0),
                    description="更适合四人一起玩的畅玩方案，内容更丰富",
                    features="更热闹但不费脑，适合组局。",
                    requires_booking=requires_booking_base,
                    available_stock=_stock(20, 320),
                    duration_mins=base_duration + 30,
                    duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                    start_time=_start_time(),
                ),
                _mk(
                    k=3,
                    name="六人团建包场",
                    price=_price(168.0, 368.0),
                    description="更适合多人一起玩的包场方案，体验更完整",
                    features="更适合团建与朋友大局，氛围拉满。",
                    requires_booking=True,
                    available_stock=_stock(10, 120),
                    duration_mins=base_duration + 60,
                    duration_std_dev=_std([30.0, 45.0, 60.0, 75.0]),
                    start_time=_start_time(),
                ),
            ]

        return [
            _mk(
                k=1,
                name="单人/双人随享",
                price=_price(39.0, 128.0),
                description="低决策成本的通用体验，适合临时加一站",
                features="更灵活，不需要做太多功课。",
                requires_booking=requires_booking_base,
                available_stock=_stock(40, 620),
                duration_mins=max(45, base_duration - 15),
                duration_std_dev=_std([10.0, 15.0, 20.0, 30.0]),
                start_time=_start_time(),
            ),
            _mk(
                k=2,
                name="2-4人通用票",
                price=_price(79.0, 188.0),
                description="更适合小团体的通用方案，玩法更完整",
                features="更稳更不踩雷，适合兜底安排。",
                requires_booking=requires_booking_base,
                available_stock=_stock(30, 460),
                duration_mins=base_duration,
                duration_std_dev=_std([15.0, 20.0, 30.0, 45.0]),
                start_time=_start_time(),
            ),
            _mk(
                k=3,
                name="3-5人小团体票",
                price=_price(99.0, 268.0),
                description="更适合多人一起玩的玩法组合，体验更丰富",
                features="更热闹，适合把气氛带起来。",
                requires_booking=requires_booking_base,
                available_stock=_stock(20, 320),
                duration_mins=base_duration + 30,
                duration_std_dev=_std([20.0, 30.0, 45.0, 60.0]),
                start_time=_start_time(),
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
        tags = list(plan.get("tags") or [])
        business_hours = random.choice(["10:00-22:00", "09:00-22:00", "10:00-21:30"])
        if any(k in sub_category for k in ("夜景", "Livehouse", "清吧")):
            business_hours = random.choice(["18:00-23:30", "19:00-24:00"])
        review_keywords = _keywords_for_profile(
            category="activity",
            profile=profile,
            indoor=indoor,
            sub_category=sub_category,
            delivery_supported=False,
        )

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
        mock_db["activity_venues"].append(venue)
        
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
        review_keywords = _keywords_for_profile(
            category="gift_shop",
            profile=str(plan["profile"]),
            indoor=indoor,
            sub_category=sub_category,
            delivery_supported=delivery_supported,
        )

        gifts_raw = _build_gifts(
            sub_category=sub_category,
            profile=str(plan["profile"]),
            tags=list(plan.get("tags") or []),
        )
        gifts = []
        for j, g in enumerate(gifts_raw):
            recv_mins, recv_std = _infer_receive_duration_mins(g["name"], list(plan.get("tags") or []))
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
            "tags": list(plan.get("tags") or []),
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
            tags=list(plan.get("tags") or []),
            review_keywords=review_keywords,
            indoor=indoor,
        )
        shop = _ensure_gift_shop_special_fields(
            item=shop,
            sub_category=sub_category,
            tags=list(plan.get("tags") or []),
            review_keywords=review_keywords,
        )
        mock_db["gift_shops"].append(shop)
        
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


def generate_mock_db_from_catalog(
    *,
    restaurants_catalog: list[dict],
    activities_catalog: list[dict],
    add_ons_catalog: list[dict] | None,
) -> dict[str, Any]:
    hubs = generate_hub_locations()
    hub_names = list(hubs.keys())

    mock_db = {
        "restaurants": [],
        "activity_venues": [],
        "gift_shops": [],
    }

    for i, r in enumerate(restaurants_catalog):
        district = r.get("district") or random.choice(hub_names)
        name = r.get("name") or f"餐厅_{i+1}"
        tags = r.get("tags") or []
        combos_in = r.get("combos") or []
        combos_out: list[dict] = []
        for c in combos_in:
            inferred_people = _infer_default_people_expr_for_combo(
                combo_name=c.get("name", ""),
                restaurant_tags=tags,
            )
            name_norm = _ensure_people_expr_in_name(
                c.get("name", ""),
                default_people_expr=inferred_people,
            )
            desc_norm = _render_sectionalized_description(
                str(r.get("sub_category") or r.get("category") or ""),
                c.get("description", "") or "",
            )
            feat = c.get("features", "") or ""
            if not feat.strip() or feat.strip() == desc_norm.strip():
                feat = f"{inferred_people}吃得更满足，搭配更均衡，适合轻松不踩雷。"
            combos_out.append(
                {
                    "combo_id": c.get("combo_id"),
                    "name": name_norm,
                    "price": float(c.get("price", 0.0) or 0.0),
                    "description": desc_norm,
                    "features": feat,
                    "duration_mins": int(c.get("duration_mins") or 60),
                    "duration_std_dev": float(c.get("duration_std_dev") or 10.0),
                    "suitable_time_slots": c.get("suitable_time_slots") or ["lunch", "dinner"],
                    "requires_booking": bool(c.get("requires_booking") is True),
                }
            )

        latitude = r.get("latitude")
        longitude = r.get("longitude")
        address = r.get("address")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or not isinstance(address, str) or not address:
            hub_x, hub_y = hubs[str(district)]
            loc = generate_location_near_hub(hub_x, hub_y, str(district))
            address = loc["address"]
            latitude = loc["latitude"]
            longitude = loc["longitude"]

        sub_category = r.get("sub_category") or _choose_restaurant_sub_category(tags)
        business_hours = r.get("business_hours") or "10:00-22:00"
        indoor = bool(r.get("indoor") is True) if "indoor" in r else True
        review_keywords = r.get("review_keywords")
        if not isinstance(review_keywords, list) or not review_keywords:
            review_keywords = _keywords_for_profile(
                category="restaurant",
                profile="family_mild",
                indoor=indoor,
                sub_category=str(sub_category),
                delivery_supported=False,
            )

        restaurant_item = {
            "id": r.get("id") or f"restaurant_{i+1:03d}",
            "name": name,
            "category": "restaurant",
            "sub_category": sub_category,
            "district": district,
            "address": address,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "business_hours": business_hours,
            "indoor": bool(indoor),
            "review_keywords": review_keywords,
            "rating": float(r.get("rating") or round(random.uniform(4.2, 5.0), 1)),
            "combos": combos_out,
            "tags": tags,
        }
        restaurant_item.update(
            {k: r.get(k) for k in (
                "suitable_groups",
                "experience_tag",
                "photo_score_derived",
                "onsite_walking_level_estimated",
                "noise_level_estimated",
                "kid_menu_status",
                "stroller_friendly_status",
                "child_facility_tags",
                "child_friendly_score_derived",
            ) if k in r}
        )
        restaurant_item = _ensure_profile_fields(
            item=restaurant_item,
            category="restaurant",
            profile="family_mild",
            sub_category=str(sub_category),
            tags=tags,
            review_keywords=review_keywords,
            indoor=bool(indoor),
        )
        restaurant_item = _ensure_restaurant_child_fields(
            item=restaurant_item,
            sub_category=str(sub_category),
            tags=tags,
            review_keywords=review_keywords,
            indoor=bool(indoor),
        )
        mock_db["restaurants"].append(restaurant_item)

    for i, v in enumerate(activities_catalog):
        district = v.get("district") or random.choice(hub_names)
        name = v.get("name") or f"活动_{i+1}"
        tags = v.get("tags") or []
        packages_in = v.get("packages") or []
        packages_out: list[dict] = []
        for p in packages_in:
            requires_booking = bool(p.get("requires_booking") is True)
            available_stock = p.get("available_stock")
            if not isinstance(available_stock, int):
                available_stock = random.randint(20, 500)
            packages_out.append(
                {
                    "package_id": p.get("package_id"),
                    "name": p.get("name", ""),
                    "price": float(p.get("price", 0.0) or 0.0),
                    "description": p.get("description", "") or "",
                    "features": p.get("features", "") or "",
                    "requires_booking": requires_booking,
                    "available_stock": int(available_stock),
                    "duration_mins": int(p.get("duration_mins") or 60),
                    "duration_std_dev": float(p.get("duration_std_dev") or 15.0),
                    "start_time": p.get("start_time"),
                }
            )

        latitude = v.get("latitude")
        longitude = v.get("longitude")
        address = v.get("address")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or not isinstance(address, str) or not address:
            hub_x, hub_y = hubs[str(district)]
            loc = generate_location_near_hub(hub_x, hub_y, str(district))
            address = loc["address"]
            latitude = loc["latitude"]
            longitude = loc["longitude"]

        sub_category = v.get("sub_category") or v.get("category") or "休闲娱乐"
        business_hours = v.get("business_hours") or "09:00-22:00"
        indoor = bool(v.get("indoor") is True) if "indoor" in v else True
        review_keywords = v.get("review_keywords")
        if not isinstance(review_keywords, list) or not review_keywords:
            review_keywords = _keywords_for_profile(
                category="activity",
                profile="universal",
                indoor=indoor,
                sub_category=str(sub_category),
                delivery_supported=False,
            )

        activity_item = {
            "id": v.get("id") or f"activity_{i+1:03d}",
            "name": name,
            "category": "activity",
            "sub_category": sub_category,
            "district": district,
            "address": address,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "business_hours": business_hours,
            "indoor": bool(indoor),
            "review_keywords": review_keywords,
            "is_free": bool(v.get("is_free") is True),
            "rating": float(v.get("rating") or round(random.uniform(4.0, 5.0), 1)),
            "reviews_count": int(v.get("reviews_count") or random.randint(100, 20000)),
            "tags": tags,
            "packages": packages_out,
        }
        activity_item.update(
            {k: v.get(k) for k in (
                "suitable_groups",
                "age_range",
                "experience_tag",
                "photo_score_derived",
                "onsite_walking_level_estimated",
                "noise_level_estimated",
            ) if k in v}
        )
        activity_item = _ensure_profile_fields(
            item=activity_item,
            category="activity",
            profile="universal",
            sub_category=str(sub_category),
            tags=tags,
            review_keywords=review_keywords,
            indoor=bool(indoor),
        )
        mock_db["activity_venues"].append(activity_item)

    if isinstance(add_ons_catalog, list) and add_ons_catalog:
        for i, s in enumerate(add_ons_catalog):
            district = s.get("district") or random.choice(hub_names)

            gifts_in = s.get("gifts") or []
            gifts_out: list[dict] = []
            for g in gifts_in:
                stock = g.get("stock")
                if not isinstance(stock, int):
                    stock = random.randint(5, 200)
                gifts_out.append(
                    {
                        "gift_id": g.get("gift_id"),
                        "name": g.get("name", ""),
                        "price": float(g.get("price", 0.0) or 0.0),
                        "receive_duration_mins": int(g.get("receive_duration_mins") or _infer_receive_duration_mins(g.get("name", ""), s.get("tags") or [])[0]),
                        "receive_duration_std_dev": float(g.get("receive_duration_std_dev") or _infer_receive_duration_mins(g.get("name", ""), s.get("tags") or [])[1]),
                        "description": g.get("description", "") or "",
                        "features": g.get("features", "") or "",
                        "stock": int(stock),
                    }
                )

            latitude = s.get("latitude")
            longitude = s.get("longitude")
            address = s.get("address")
            if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or not isinstance(address, str) or not address:
                hub_x, hub_y = hubs[str(district)]
                loc = generate_location_near_hub(hub_x, hub_y, str(district))
                address = loc["address"]
                latitude = loc["latitude"]
                longitude = loc["longitude"]

            tags = s.get("tags") or []
            sub_category = s.get("sub_category") or _choose_gift_shop_sub_category(tags)
            business_hours = s.get("business_hours") or "10:00-21:00"
            indoor = bool(s.get("indoor") is True) if "indoor" in s else True
            review_keywords = s.get("review_keywords")
            if not isinstance(review_keywords, list) or not review_keywords:
                review_keywords = _keywords_for_profile(
                    category="gift_shop",
                    profile="culture",
                    indoor=indoor,
                    sub_category=str(sub_category),
                    delivery_supported=bool(s.get("delivery_time_mins")),
                )

            gift_item = {
                "id": s.get("id") or f"gift_shop_{i+1:03d}",
                "name": s.get("name") or f"礼品店_{i+1}",
                "category": "gift_shop",
                "sub_category": sub_category,
                "district": district,
                "address": address,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "business_hours": business_hours,
                "indoor": bool(indoor),
                "review_keywords": review_keywords,
                "rating": float(s.get("rating") or round(random.uniform(4.5, 5.0), 1)),
                "tags": tags,
                "gifts": gifts_out,
                "delivery_time_mins": s.get("delivery_time_mins"),
                "delivery_time_std_dev": s.get("delivery_time_std_dev"),
                "delivery_radius_km": float(s.get("delivery_radius_km") or 5.0),
            }
            gift_item.update(
                {k: s.get(k) for k in (
                    "suitable_groups",
                    "experience_tag",
                    "photo_score_derived",
                    "onsite_walking_level_estimated",
                    "noise_level_estimated",
                    "gift_type",
                    "delivery_to_restaurant",
                    "surprise_score_derived",
                ) if k in s}
            )
            gift_item = _ensure_profile_fields(
                item=gift_item,
                category="gift_shop",
                profile="culture",
                sub_category=str(sub_category),
                tags=tags,
                review_keywords=review_keywords,
                indoor=bool(indoor),
            )
            gift_item = _ensure_gift_shop_special_fields(
                item=gift_item,
                sub_category=str(sub_category),
                tags=tags,
                review_keywords=review_keywords,
            )
            mock_db["gift_shops"].append(gift_item)
    else:
        for i in range(16):
            tpl = GIFT_SHOP_TEMPLATES[i % len(GIFT_SHOP_TEMPLATES)]
            district = random.choice(hub_names)
            hub_x, hub_y = hubs[district]
            loc = generate_location_near_hub(hub_x, hub_y, district)

            delivery_info = tpl["delivery"]
            tags = list(tpl.get("tags") or [])
            sub_category = _choose_gift_shop_sub_category(tags)
            business_hours = random.choice(["10:00-21:00", "10:00-22:00", "11:00-20:30"])
            indoor = True

            shop = {
                "id": f"gift_shop_{i+1:03d}",
                "name": f"{tpl['name']}({district})",
                "category": "gift_shop",
                "sub_category": sub_category,
                "district": district,
                "address": loc["address"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "business_hours": business_hours,
                "indoor": indoor,
                "review_keywords": _keywords_for_profile(
                    category="gift_shop",
                    profile="culture",
                    indoor=indoor,
                    sub_category=sub_category,
                    delivery_supported=bool(delivery_info),
                ),
                "rating": float(round(random.uniform(4.5, 5.0), 1)),
                "tags": tags,
                "gifts": [
                    {
                        "gift_id": f"gift_{i+1:03d}_{j+1}",
                        "name": g["name"],
                        "price": g["price"],
                        "receive_duration_mins": int(g.get("receive_duration_mins") or _infer_receive_duration_mins(g["name"], tpl["tags"])[0]),
                        "receive_duration_std_dev": float(g.get("receive_duration_std_dev") or _infer_receive_duration_mins(g["name"], tpl["tags"])[1]),
                        "description": g.get("desc", ""),
                        "features": g.get("features", ""),
                        "stock": g["stock"],
                    }
                    for j, g in enumerate(tpl["gifts"])
                ],
                "delivery_time_mins": delivery_info["mins"] if delivery_info else None,
                "delivery_time_std_dev": float(delivery_info["std"]) if delivery_info else None,
                "delivery_radius_km": float(tpl.get("delivery_radius_km") or 5.0),
            }
            shop = _ensure_profile_fields(
                item=shop,
                category="gift_shop",
                profile="culture",
                sub_category=str(sub_category),
                tags=tags,
                review_keywords=list(shop.get("review_keywords") or []),
                indoor=bool(indoor),
            )
            shop = _ensure_gift_shop_special_fields(
                item=shop,
                sub_category=str(sub_category),
                tags=tags,
                review_keywords=list(shop.get("review_keywords") or []),
            )
            mock_db["gift_shops"].append(shop)

    def _clone_with_new_ids(*, item: dict, kind: str, new_index: int) -> dict:
        if kind == "restaurant":
            combos_in = item.get("combos") or []
            combos_out = []
            for j, c in enumerate(combos_in):
                c2 = dict(c)
                c2["combo_id"] = f"combo_{new_index:03d}_{j+1}"
                combos_out.append(c2)
            out = dict(item)
            out["id"] = f"restaurant_{new_index:03d}"
            out["combos"] = combos_out
            return out

        if kind == "activity":
            pkgs_in = item.get("packages") or []
            pkgs_out = []
            for j, p in enumerate(pkgs_in):
                p2 = dict(p)
                p2["package_id"] = f"package_{new_index:03d}_{j+1}"
                pkgs_out.append(p2)
            out = dict(item)
            out["id"] = f"activity_{new_index:03d}"
            out["packages"] = pkgs_out
            return out

        gifts_in = item.get("gifts") or []
        gifts_out = []
        for j, g in enumerate(gifts_in):
            g2 = dict(g)
            g2["gift_id"] = f"gift_{new_index:03d}_{j+1}"
            gifts_out.append(g2)
        out = dict(item)
        out["id"] = f"gift_shop_{new_index:03d}"
        out["gifts"] = gifts_out
        return out

    target_sizes = {"restaurants": 32, "activity_venues": 40, "gift_shops": 16}
    extra_db = generate_mock_db()

    for key, target_size in target_sizes.items():
        items = mock_db.get(key) or []
        if len(items) > target_size:
            mock_db[key] = items[:target_size]
            continue
        if len(items) == target_size:
            continue

        missing = target_size - len(items)
        extra_items = extra_db.get(key) or []
        kind = "restaurant" if key == "restaurants" else ("activity" if key == "activity_venues" else "gift_shop")
        for n in range(missing):
            base = extra_items[n % len(extra_items)]
            new_index = len(mock_db[key]) + 1
            mock_db[key].append(_clone_with_new_ids(item=base, kind=kind, new_index=new_index))

    return mock_db


def _parse_hhmm_to_minutes(v: str) -> int:
    if not v or ":" not in v:
        return 0
    h, m = v.split(":", 1)
    return int(h) * 60 + int(m)


def _format_minutes_to_hhmm(minutes: int) -> str:
    if minutes < 0:
        minutes = 0
    minutes = minutes % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _pick_capacity_total(*, target_type: str, duration_mins: int | None) -> int:
    duration_mins = int(duration_mins or 60)
    if target_type == "combo":
        if duration_mins >= 150:
            return random.randint(4, 10)
        if duration_mins >= 90:
            return random.randint(6, 14)
        return random.randint(8, 18)

    if duration_mins >= 240:
        return random.randint(10, 30)
    if duration_mins >= 120:
        return random.randint(15, 50)
    return random.randint(20, 80)


def _build_time_slots_for_package(*, package: dict, business_hours: str) -> list[dict]:
    open_h, close_h = business_hours.split("-", 1) if "-" in business_hours else ("09:00", "22:00")
    open_min = _parse_hhmm_to_minutes(open_h)
    close_min = _parse_hhmm_to_minutes(close_h)
    if close_min <= open_min:
        close_min = open_min + 13 * 60

    duration_mins = int(package.get("duration_mins") or 60)
    duration_mins = max(30, min(duration_mins, 6 * 60))

    start_time = package.get("start_time")
    if isinstance(start_time, str) and start_time:
        start_min = _parse_hhmm_to_minutes(start_time)
        end_min = start_min + max(60, duration_mins)
        if end_min > close_min:
            end_min = close_min
        return [
            {
                "start_time": _format_minutes_to_hhmm(start_min),
                "end_time": _format_minutes_to_hhmm(end_min),
            }
        ]

    k = random.randint(3, 6)
    start_candidates: list[int] = []
    cursor = open_min
    while cursor + duration_mins <= close_min:
        start_candidates.append(cursor)
        cursor += 30

    if not start_candidates:
        return [
            {
                "start_time": _format_minutes_to_hhmm(open_min),
                "end_time": _format_minutes_to_hhmm(min(open_min + max(60, duration_mins), close_min)),
            }
        ]

    chosen = sorted(random.sample(start_candidates, k=min(k, len(start_candidates))))
    return [
        {
            "start_time": _format_minutes_to_hhmm(s),
            "end_time": _format_minutes_to_hhmm(min(s + duration_mins, close_min)),
        }
        for s in chosen
    ]


def _build_time_slots_for_combo(*, combo: dict) -> list[dict]:
    duration_mins = int(combo.get("duration_mins") or 60)
    duration_mins = max(30, min(duration_mins, 4 * 60))

    windows: dict[str, tuple[int, int]] = {
        "breakfast": (8 * 60, 10 * 60),
        "lunch": (11 * 60, 13 * 60 + 30),
        "afternoon_tea": (14 * 60, 16 * 60 + 30),
        "dinner": (17 * 60, 20 * 60 + 30),
        "late_night": (21 * 60, 23 * 60 + 30),
    }

    suitable = combo.get("suitable_time_slots") or []
    candidate_starts: list[int] = []
    for slot in suitable:
        if slot not in windows:
            continue
        w_start, w_end = windows[slot]
        cursor = w_start
        while cursor + duration_mins <= w_end:
            candidate_starts.append(cursor)
            cursor += 30

    if not candidate_starts:
        candidate_starts = [11 * 60, 12 * 60, 18 * 60]

    k = random.randint(2, 4)
    chosen = sorted(random.sample(candidate_starts, k=min(k, len(candidate_starts))))
    slots_out: list[dict] = []
    for s in chosen:
        end_min = s + duration_mins
        slots_out.append(
            {
                "start_time": _format_minutes_to_hhmm(s),
                "end_time": _format_minutes_to_hhmm(end_min),
            }
        )
    return slots_out


def generate_reservations_from_mock_db(mock_db: dict[str, Any]) -> list[dict]:
    reservations: list[dict] = []

    for venue in mock_db.get("activity_venues", []):
        business_hours = venue.get("business_hours") or "09:00-22:00"
        for p in venue.get("packages", []):
            if p.get("requires_booking") is not True:
                continue
            target_id = p.get("package_id")
            if not target_id:
                continue

            raw_slots = _build_time_slots_for_package(package=p, business_hours=business_hours)
            duration_mins = int(p.get("duration_mins") or 60)
            capacity_total = _pick_capacity_total(target_type="package", duration_mins=duration_mins)
            time_slots: list[dict] = []
            for s in raw_slots:
                remaining = random.randint(0, capacity_total)
                if random.random() < 0.15:
                    remaining = 0
                fullness = 1.0 - (remaining / max(1, capacity_total))
                queue_required = remaining == 0 or fullness >= 0.8 or (random.random() < 0.08)
                wait_minutes = 0
                if queue_required:
                    wait_minutes = int(round(10 + 80 * fullness))
                time_slots.append(
                    {
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "capacity_total": capacity_total,
                        "capacity_remaining": remaining,
                        "queue_required": bool(queue_required),
                        "wait_minutes": int(wait_minutes),
                    }
                )

            reservations.append(
                {
                    "target_type": "package",
                    "target_id": target_id,
                    "time_slots": time_slots,
                }
            )

    for restaurant in mock_db.get("restaurants", []):
        for c in restaurant.get("combos", []):
            if c.get("requires_booking") is not True:
                continue
            target_id = c.get("combo_id")
            if not target_id:
                continue

            raw_slots = _build_time_slots_for_combo(combo=c)
            duration_mins = int(c.get("duration_mins") or 60)
            capacity_total = _pick_capacity_total(target_type="combo", duration_mins=duration_mins)
            time_slots: list[dict] = []
            for s in raw_slots:
                remaining = random.randint(0, capacity_total)
                if random.random() < 0.18:
                    remaining = 0
                fullness = 1.0 - (remaining / max(1, capacity_total))
                queue_required = remaining == 0 or fullness >= 0.8 or (random.random() < 0.06)
                wait_minutes = 0
                if queue_required:
                    wait_minutes = int(round(5 + 60 * fullness))
                time_slots.append(
                    {
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "capacity_total": capacity_total,
                        "capacity_remaining": remaining,
                        "queue_required": bool(queue_required),
                        "wait_minutes": int(wait_minutes),
                    }
                )

            reservations.append(
                {
                    "target_type": "combo",
                    "target_id": target_id,
                    "time_slots": time_slots,
                }
            )

    return reservations

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from closedloop.core.config import REPO_ROOT_DIR, get_config
    from closedloop.core.logger import LoggerManager, logger
    from closedloop.export_mock_catalog import export_catalog

    random.seed(42) 
    config = get_config()
    LoggerManager.setup(config)

    def _resolve_dir(v: str) -> str:
        if not v:
            return ""
        if os.path.isabs(v):
            return os.path.abspath(v)
        return os.path.abspath(os.path.join(REPO_ROOT_DIR, v))

    catalog_dir = _resolve_dir(config.data.MOCK_DB_CATALOG_DIR)
    os.makedirs(catalog_dir, exist_ok=True)

    data = generate_mock_db()

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

    export_catalog()
    logger.info("phase=mock_data_generator | result=generated_mock_db_files")
