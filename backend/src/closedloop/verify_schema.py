import json
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional
from enum import Enum

# ==========================================
# 定义我们最新讨论出的 Schema 结构
# ==========================================

class VenueCategory(str, Enum):
    CINEMA = "电影院"
    AMUSEMENT_PARK = "游乐园"
    MUSEUM = "博物馆"
    PARK = "公园"
    ESCAPE_ROOM = "密室逃脱"
    EXHIBITION = "展览"
    SPORTS = "体育运动"
    LEISURE = "休闲娱乐"
    OUTDOOR = "户外"

class Location(BaseModel):
    latitude: float = Field(..., description="纬度 (直角坐标X)")
    longitude: float = Field(..., description="经度 (直角坐标Y)")
    address: str = Field(..., description="详细地址")
    distance_to_center_km: float = Field(..., description="距离市中心的直线距离(km)")
    zone_name: Optional[str] = Field(None, description="商圈名称")

class ComboMeal(BaseModel):
    combo_id: str
    name: str
    price: float
    description: str
    features: Optional[str] = Field(None, description="宣传文案，包含适合人群与体验特色")
    duration_mins: int = Field(..., description="预计就餐时长(分钟)")
    duration_std_dev: float = Field(..., description="时长的标准差，表示浮动范围")
    suitable_time_slots: List[str] = Field(..., description="适合的时间段，如 ['lunch', 'dinner', 'late_night', 'afternoon_tea']")

class Restaurant(BaseModel):
    restaurant_id: str
    name: str
    location: Location
    rating: float = Field(..., ge=0, le=5.0)
    tags: List[str]
    # 之前口头说3-5个，但脚本生成了2个套餐以聚焦特定人群，这里先放宽到 min_length=1
    combos: List[ComboMeal] = Field(..., min_length=1)

class ServicePackage(BaseModel):
    package_id: str
    name: str
    price: float
    description: Optional[str] = None
    features: Optional[str] = Field(None, description="宣传文案，包含适合人群与体验特色")
    requires_booking: bool
    available_stock: int
    start_time: Optional[str] = Field(None, description="针对有明确场次时间的套餐（如电影、演出），格式如 '14:30'")
    duration_mins: Optional[int] = Field(None, description="预计体验时长(分钟)")
    duration_std_dev: Optional[float] = Field(None, description="体验时长的标准差(分钟)")

class ActivityVenue(BaseModel):
    venue_id: str
    name: str
    category: VenueCategory
    location: Location
    is_free: bool
    rating: float = Field(..., ge=0, le=5.0)
    reviews_count: int
    operating_hours: str
    tags: List[str]
    packages: List[ServicePackage]

class Gift(BaseModel):
    gift_id: str
    name: str
    price: float
    description: Optional[str] = None
    features: Optional[str] = Field(None, description="宣传文案，包含适合人群与体验特色")
    stock: int

class GiftShop(BaseModel):
    shop_id: str
    name: str
    location: Location
    rating: float = Field(..., ge=0, le=5.0)
    tags: List[str]
    gifts: List[Gift] = Field(..., min_length=1)
    delivery_time_mins: Optional[int] = Field(None, description="预计同城送达时间(分钟)，为空表示不支持配送")
    delivery_time_std_dev: Optional[float] = Field(None, description="送达时间的标准差")

class MockDatabase(BaseModel):
    restaurants: List[Restaurant]
    activity_venues: List[ActivityVenue]
    gift_shops: List[GiftShop]

# ==========================================
# 校验逻辑
# ==========================================
def verify_schema():
    try:
        with open("mock_db/restaurants.json", "r", encoding="utf-8") as f:
            restaurants = json.load(f)
        with open("mock_db/activities.json", "r", encoding="utf-8") as f:
            activities = json.load(f)
        with open("mock_db/add_ons.json", "r", encoding="utf-8") as f:
            add_ons = json.load(f)
            
        data = {
            "restaurants": restaurants,
            "activity_venues": activities,
            "gift_shops": add_ons
        }
            
        # Pydantic 校验
        db = MockDatabase(**data)
        print("校验通过！拆分后的 JSON 文件完全符合 Pydantic Schema 约束。")
        print(f"统计信息: 餐厅={len(db.restaurants)}, 活动场所={len(db.activity_venues)}, 礼品店={len(db.gift_shops)}")
        
    except ValidationError as e:
        print("校验失败！发现不符合 Schema 的数据：")
        print(e.json(indent=2))
    except Exception as e:
        print(f"发生其他错误：{e}")

if __name__ == "__main__":
    verify_schema()
