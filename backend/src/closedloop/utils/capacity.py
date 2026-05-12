import re
from closedloop.contracts.state import Constraints

def _get_effective_people(constraints: Constraints) -> float:
    """计算等效人数"""
    effective = float(constraints.adult_count)
    child_ages = constraints.child_ages or []
    for age in child_ages:
        if age <= 3:
            effective += 0.2
        elif age <= 6:
            effective += 0.4
        elif age <= 10:
            effective += 0.6
        elif age <= 14:
            effective += 0.8
        else:
            effective += 1.0
            
    unknown_children = max(0, constraints.child_count - len(child_ages))
    effective += unknown_children * 0.6
    return effective

def _get_capacity_from_name(name: str) -> float:
    """从套餐/活动名称中提取适用人数容量（结合成人数与等效儿童数）。"""
    if not name:
        return 1.0
        
    name = name.lower()
    
    # 1. 优先匹配明确的“X大Y小”结构 (例如：2大1小 -> 2.4 人)
    match = re.search(r'(\d+)\s*[大小]\s*(\d+)\s*[大小]', name)
    if match:
        adults = int(match.group(1))
        kids = int(match.group(2))
        # 默认儿童等效权重为 0.4
        return adults + kids * 0.4
        
    # 3. 匹配通用家庭/亲子套餐（通常指三口之家或四口之家）
    if "三口之家" in name or "2大1小" in name:
        return 2.6
    if "四口之家" in name or "2大2小" in name:
        return 3.2
    if "家庭" in name or "亲子" in name:
        return 2.6 # 默认小家庭

    # 4. 匹配具体数字
    if "单人" in name or "一人" in name or "工作餐" in name:
        return 1.0
    if "双人" in name or "两人" in name or "情侣" in name or "闺蜜" in name:
        return 2.0
    if "三人" in name:
        return 3.0
    if "四人" in name:
        return 4.0
    if "五人" in name:
        return 5.0
    if "六人" in name:
        return 6.0
    if "七人" in name:
        return 7.0
    if "八人" in name:
        return 8.0
    if "多人" in name:
        return 4.0 # 默认多人为4

    return 1.0 # 无法匹配时默认返回 1.0，因为至少适合一个人使用
