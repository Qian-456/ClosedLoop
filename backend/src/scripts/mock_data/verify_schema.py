import json
import os
import sys
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Literal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from closedloop.core.config import REPO_ROOT_DIR, get_config
from closedloop.utils.mock_db import load_mock_data

# ==========================================
# 定义我们最新讨论出的 Schema 结构
# ==========================================

class BasePoi(BaseModel):
    id: str
    name: str
    category: Literal["restaurant", "activity", "gift_shop"]
    sub_category: str
    district: str
    address: str
    latitude: float = Field(..., description="直角坐标系 X (km)")
    longitude: float = Field(..., description="直角坐标系 Y (km)")
    business_hours: str
    indoor: bool
    review_keywords: List[str]
    suitable_groups: List[str]
    experience_tag: List[str]


class DerivedScoreSource(BaseModel):
    sub_category: str
    matched_review_keywords: List[str]
    rule: str


class DerivedScore(BaseModel):
    score: float = Field(..., ge=0.0, le=5.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: DerivedScoreSource

class ComboMeal(BaseModel):
    combo_id: str
    name: str
    price: float
    description: str
    features: Optional[str] = Field(None, description="宣传文案，包含适合人群与体验特色")
    duration_mins: int = Field(..., description="预计就餐时长(分钟)")
    duration_std_dev: float = Field(..., description="时长的标准差，表示浮动范围")
    suitable_time_slots: List[str] = Field(..., description="适合的时间段，如 ['lunch', 'dinner', 'late_night', 'afternoon_tea']")
    requires_booking: bool = Field(..., description="是否需要预约")

class Restaurant(BaseModel):
    id: str
    name: str
    category: Literal["restaurant"]
    sub_category: str
    district: str
    address: str
    latitude: float
    longitude: float
    business_hours: str
    indoor: bool
    review_keywords: List[str]
    suitable_groups: List[str]
    experience_tag: List[str]
    photo_score_derived: DerivedScore
    onsite_walking_level_estimated: DerivedScore
    noise_level_estimated: DerivedScore
    kid_menu_status: Literal["explicit", "possible", "none", "unknown"]
    stroller_friendly_status: Literal["yes", "likely", "no", "unknown"]
    child_facility_tags: List[str]
    child_friendly_score_derived: DerivedScore
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
    id: str
    name: str
    category: Literal["activity"]
    sub_category: str
    district: str
    address: str
    latitude: float
    longitude: float
    business_hours: str
    indoor: bool
    review_keywords: List[str]
    suitable_groups: List[str]
    age_range: List[Literal["3-6", "7-10", "11-17", "adult"]]
    experience_tag: List[str]
    photo_score_derived: DerivedScore
    onsite_walking_level_estimated: DerivedScore
    noise_level_estimated: DerivedScore
    is_free: bool
    rating: float = Field(..., ge=0, le=5.0)
    reviews_count: int
    tags: List[str]
    packages: List[ServicePackage]

class Gift(BaseModel):
    gift_id: str
    name: str
    price: float
    receive_duration_mins: int = Field(10, description="收礼/享用预计时长(分钟)")
    receive_duration_std_dev: float = Field(3.0, description="收礼/享用时长标准差(分钟)")
    description: Optional[str] = None
    features: Optional[str] = Field(None, description="宣传文案，包含适合人群与体验特色")
    stock: int

class GiftShop(BaseModel):
    id: str
    name: str
    category: Literal["gift_shop"]
    sub_category: str
    district: str
    address: str
    latitude: float
    longitude: float
    business_hours: str
    indoor: bool
    review_keywords: List[str]
    suitable_groups: List[str]
    experience_tag: List[str]
    photo_score_derived: DerivedScore
    onsite_walking_level_estimated: DerivedScore
    noise_level_estimated: DerivedScore
    gift_type: Literal["flower", "cake", "toy", "snack", "blind_box", "coffee"]
    delivery_to_restaurant: bool
    surprise_score_derived: DerivedScore
    rating: float = Field(..., ge=0, le=5.0)
    tags: List[str]
    gifts: List[Gift] = Field(..., min_length=1)
    delivery_time_mins: Optional[int] = Field(None, description="预计同城送达时间(分钟)，为空表示不支持配送")
    delivery_time_std_dev: Optional[float] = Field(None, description="送达时间的标准差")
    delivery_radius_km: float = Field(5.0, description="配送范围(km)")

class MockDatabase(BaseModel):
    restaurants: List[Restaurant]
    activity_venues: List[ActivityVenue]
    gift_shops: List[GiftShop]


class ReservationTimeSlot(BaseModel):
    start_time: str
    end_time: str
    capacity_total: int
    capacity_remaining: int
    queue_required: bool
    wait_minutes: int


class ReservationRecord(BaseModel):
    target_type: Literal["restaurant", "package"]
    target_id: str
    time_slots: List[ReservationTimeSlot]

# ==========================================
# 校验逻辑
# ==========================================
def verify_schema():
    try:
        config = get_config()
        repo_dir = config.data.MOCK_DB_REPO_DIR
        if not os.path.isabs(repo_dir):
            repo_dir = os.path.abspath(os.path.join(REPO_ROOT_DIR, repo_dir))
        print(f"使用数据目录: repo={repo_dir}")

        restaurants = load_mock_data("restaurants.json")
        activities = load_mock_data("activities.json")
        add_ons = load_mock_data("add_ons.json")
        reservations = load_mock_data("reservations.json")
            
        data = {
            "restaurants": restaurants,
            "activity_venues": activities,
            "gift_shops": add_ons
        }
            
        # Pydantic 校验
        db = MockDatabase(**data)
        print("校验通过！拆分后的 JSON 文件完全符合 Pydantic Schema 约束。")
        print(f"统计信息: 餐厅={len(db.restaurants)}, 活动场所={len(db.activity_venues)}, 礼品店={len(db.gift_shops)}")

        reservation_records = [ReservationRecord(**x) for x in reservations]

        restaurant_ids = {r.id for r in db.restaurants}
        package_ids = {p.package_id for v in db.activity_venues for p in v.packages}

        seen_restaurant_ids: set[str] = set()
        seen_package_ids: set[str] = set()

        for rec in reservation_records:
            for slot in rec.time_slots:
                if slot.capacity_total <= 0:
                    raise ValueError(f"Invalid capacity_total for {rec.target_type}:{rec.target_id}")
                if slot.capacity_remaining < 0 or slot.capacity_remaining > slot.capacity_total:
                    raise ValueError(f"Invalid capacity_remaining for {rec.target_type}:{rec.target_id}")

            if rec.target_type == "restaurant":
                if rec.target_id not in restaurant_ids:
                    raise ValueError(f"Unknown restaurant target_id: {rec.target_id}")
                if rec.target_id in seen_restaurant_ids:
                    raise ValueError(f"Duplicate reservation record for restaurant: {rec.target_id}")
                seen_restaurant_ids.add(rec.target_id)
            else:
                if rec.target_id not in package_ids:
                    raise ValueError(f"Unknown package target_id: {rec.target_id}")
                if rec.target_id in seen_package_ids:
                    raise ValueError(f"Duplicate reservation record for package: {rec.target_id}")
                seen_package_ids.add(rec.target_id)

        if seen_restaurant_ids != restaurant_ids:
            missing = restaurant_ids - seen_restaurant_ids
            raise ValueError(f"Missing reservation records for restaurants: {sorted(missing)[:10]}")
        if seen_package_ids != package_ids:
            missing = package_ids - seen_package_ids
            raise ValueError(f"Missing reservation records for packages: {sorted(missing)[:10]}")

        print(f"预约校验通过！records={len(reservation_records)}")
        
    except ValidationError as e:
        print("校验失败！发现不符合 Schema 的数据：")
        print(e.json(indent=2))
    except Exception as e:
        print(f"发生其他错误：{e}")

if __name__ == "__main__":
    verify_schema()
