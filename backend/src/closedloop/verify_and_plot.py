import json
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def verify_and_plot():
    # 解决 matplotlib 中文字体显示问题
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    with open('mock_db/restaurants.json', 'r', encoding='utf-8') as f:
        restaurants = json.load(f)
    with open('mock_db/activities.json', 'r', encoding='utf-8') as f:
        activities = json.load(f)
    with open('mock_db/add_ons.json', 'r', encoding='utf-8') as f:
        add_ons = json.load(f)

    data = {
        'restaurants': restaurants,
        'activity_venues': activities,
        'gift_shops': add_ons
    }

    errors = []
    plot_data = {
        'restaurants': {'x': [], 'y': [], 'names': []},
        'activity_venues': {'x': [], 'y': [], 'names': []},
        'gift_shops': {'x': [], 'y': [], 'names': []}
    }
    
    # 记录各个商圈的坐标点，用于计算商圈中心
    zone_coords = {}

    # 1. 距离校验
    print("开始校验距离数据...")
    for category in ['restaurants', 'activity_venues', 'gift_shops']:
        for item in data[category]:
            x, y = item.get('latitude'), item.get('longitude')
            zone_name = item.get('district')
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                errors.append(f"坐标缺失 -> {item.get('name')}")
                continue
            
            if zone_name:
                if zone_name not in zone_coords:
                    zone_coords[zone_name] = {'x': [], 'y': []}
                zone_coords[zone_name]['x'].append(x)
                zone_coords[zone_name]['y'].append(y)

            calc_dist = math.sqrt(float(x)**2 + float(y)**2)
            
            if calc_dist > 12.0 + 1e-6:
                errors.append(f"超出12km -> {item.get('name')}: {calc_dist:.2f}km")

            plot_data[category]['x'].append(x)
            plot_data[category]['y'].append(y)
            plot_data[category]['names'].append(item['name'])

    if errors:
        for e in errors:
            print(e)
    else:
        print("校验通过：所有地点坐标均在 12km 范围内，符合欧几里得距离约束！\n")

    # 2. 可视化绘制
    print("开始绘制可视化分布图...")
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # 绘制三类实体
    ax.scatter(plot_data['restaurants']['x'], plot_data['restaurants']['y'], 
               c='#1f77b4', label='餐厅 (Restaurants)', alpha=0.7, marker='o', s=80)
    ax.scatter(plot_data['activity_venues']['x'], plot_data['activity_venues']['y'], 
               c='#2ca02c', label='活动场所 (Venues)', alpha=0.7, marker='s', s=80)
    ax.scatter(plot_data['gift_shops']['x'], plot_data['gift_shops']['y'], 
               c='#ff7f0e', label='礼品店 (Gift Shops)', alpha=0.9, marker='^', s=100)

    # 绘制原点 (0,0) - 代表用户位置
    ax.scatter(0, 0, c='#d62728', s=300, label='用户当前位置 (0,0)', marker='*', zorder=5)

    # 绘制 12km 的边界圆
    circle = patches.Circle((0, 0), 12, color='gray', fill=False, linestyle='--', linewidth=1.5, label='12km 边界范围')
    ax.add_patch(circle)

    # 计算并绘制商圈中心 (Hubs)
    hubs = {}
    for zone, coords in zone_coords.items():
        if len(coords['x']) > 0:
            avg_x = sum(coords['x']) / len(coords['x'])
            avg_y = sum(coords['y']) / len(coords['y'])
            hubs[zone] = (avg_x, avg_y)

    for zone, (hx, hy) in hubs.items():
        # 绘制中心点标记
        ax.scatter(hx, hy, c='purple', marker='P', s=250, edgecolor='white', zorder=4)
        # 添加文本标签
        ax.text(hx, hy + 0.6, zone, fontsize=10, fontweight='bold', ha='center', va='bottom',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray', boxstyle='round,pad=0.3'))
        # 绘制商圈影响范围 (例如 1.5km 核心辐射圈)
        hub_circle = patches.Circle((hx, hy), 1.5, color='purple', fill=True, alpha=0.08, linestyle=':')
        ax.add_patch(hub_circle)

    # 为图例添加一个商圈中心的虚拟点
    ax.scatter([], [], c='purple', marker='P', s=200, label='商圈中心 (Hubs)')

    # 设置图表属性
    ax.set_aspect('equal', 'box')
    ax.set_xlim(-15, 15)
    ax.set_ylim(-15, 15)
    ax.set_xlabel('X 坐标 (km)', fontsize=12)
    ax.set_ylabel('Y 坐标 (km)', fontsize=12)
    ax.set_title('本地生活 Mock 数据地理分布可视化 (极坐标 + 商圈聚类)', fontsize=16, pad=20)
    ax.legend(loc='upper right', fontsize=10)
    plt.grid(True, linestyle=':', alpha=0.6)

    # 保存图片
    output_path = 'mock_db_map.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"可视化图表已生成并保存至: {output_path}")

if __name__ == "__main__":
    verify_and_plot()
