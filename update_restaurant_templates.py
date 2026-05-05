import re

with open("backend/src/closedloop/mock_data_generator.py", "r", encoding="utf-8") as f:
    content = f.read()

new_templates = """RESTAURANT_TEMPLATES = [
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
        {"name": "营养儿童专属套餐", "price": 58.0, "desc": "鲜虾滑蛋+肉末蒸菜+南瓜浓汤+儿童果汁", "features": "科学配比的儿童营养餐，口味清淡，呵护宝宝健康。", "dur": 45, "std": 10, "slots": ["lunch", "dinner"]}
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
]"""

pattern = re.compile(r"RESTAURANT_TEMPLATES\s*=\s*\[.*?(?=\nVENUE_TEMPLATES)", re.DOTALL)
new_content = pattern.sub(new_templates, content)

with open("backend/src/closedloop/mock_data_generator.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Replaced templates successfully!")