from typing import Optional, Literal, NotRequired, Any
from typing_extensions import TypedDict, Required, TypeAlias
from pydantic import BaseModel, Field, model_validator
from langchain.agents import AgentState

class RetrievedRestaurant(TypedDict, total=False):
    """召回阶段：餐厅条目（来自 mock_db/restaurants.json 原始数据）。"""
    id: Required[str]
    name: Required[str]
    type: Required[Literal["restaurant"]]

    category: NotRequired[str]
    sub_category: NotRequired[str]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    business_hours: NotRequired[str]
    indoor: NotRequired[bool]
    review_keywords: NotRequired[list[str]]
    experience_tag: NotRequired[list[str]]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    kid_menu_status: NotRequired[Literal["explicit", "possible", "none", "unknown"]]
    stroller_friendly_status: NotRequired[Literal["yes", "likely", "no", "unknown"]]
    child_facility_tags: NotRequired[list[str]]
    child_friendly_score_derived: NotRequired[dict[str, Any]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    combos: NotRequired[list[dict]]


class RetrievedActivity(TypedDict, total=False):
    """召回阶段：活动条目（来自 mock_db/activities.json 原始数据）。"""
    id: Required[str]
    name: Required[str]
    type: Required[Literal["activity"]]

    category: NotRequired[str]
    sub_category: NotRequired[str]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    business_hours: NotRequired[str]
    indoor: NotRequired[bool]
    review_keywords: NotRequired[list[str]]
    experience_tag: NotRequired[list[str]]
    is_free: NotRequired[bool]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    age_range: NotRequired[list[Literal["3-6", "7-10", "11-17", "adult"]]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    packages: NotRequired[list[dict]]


class RetrievedGift(TypedDict, total=False):
    """召回阶段：礼物店条目（来自 mock_db/add_ons.json 原始数据）。"""
    id: Required[str]
    name: Required[str]
    type: Required[Literal["gift_shop"]]

    category: NotRequired[str]
    sub_category: NotRequired[str]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    business_hours: NotRequired[str]
    indoor: NotRequired[bool]
    review_keywords: NotRequired[list[str]]
    experience_tag: NotRequired[list[str]]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    gift_type: NotRequired[Literal["flower", "cake", "toy", "snack", "blind_box", "coffee"]]
    delivery_to_restaurant: NotRequired[bool]
    surprise_score_derived: NotRequired[dict[str, Any]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    delivery_radius_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    gifts: NotRequired[list[dict]]


class RankedCombo(TypedDict, total=False):
    """重排序阶段：扁平化的餐厅套餐条目，包含餐厅上下文。"""
    combo_id: Required[str]
    name: Required[str]
    price: Required[float]
    description: NotRequired[str]
    features: NotRequired[str]
    duration_mins: Required[int]
    duration_std_dev: NotRequired[float]
    suitable_time_slots: NotRequired[list[str]]
    score: Required[int]
    
    restaurant_id: Required[str]
    restaurant_name: Required[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    experience_tag: NotRequired[list[str]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    location: NotRequired[dict]


class RankedPackage(TypedDict, total=False):
    """重排序阶段：扁平化的活动套餐条目，包含活动场地上下文。"""
    package_id: Required[str]
    name: Required[str]
    price: Required[float]
    description: NotRequired[str]
    features: NotRequired[str]
    duration_mins: Required[int]
    duration_std_dev: NotRequired[float]
    start_time: NotRequired[str]
    score: Required[int]

    venue_id: Required[str]
    venue_name: Required[str]
    category: NotRequired[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    age_range: NotRequired[list[Literal["3-6", "7-10", "11-17", "adult"]]]
    experience_tag: NotRequired[list[str]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    location: NotRequired[dict]


class RankedGift(TypedDict, total=False):
    """重排序阶段：扁平化的礼品条目，包含礼品店上下文。"""
    gift_id: Required[str]
    name: Required[str]
    price: Required[float]
    receive_duration_mins: NotRequired[int]
    receive_duration_std_dev: NotRequired[float]
    description: NotRequired[str]
    features: NotRequired[str]
    score: Required[int]

    shop_id: Required[str]
    shop_name: Required[str]
    category: NotRequired[str]
    distance_km: NotRequired[float]
    delivery_radius_km: NotRequired[float]
    rating: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    experience_tag: NotRequired[list[str]]
    photo_score_derived: NotRequired[dict[str, Any]]
    onsite_walking_level_estimated: NotRequired[dict[str, Any]]
    noise_level_estimated: NotRequired[dict[str, Any]]
    gift_type: NotRequired[Literal["flower", "cake", "toy", "snack", "blind_box", "coffee"]]
    delivery_to_restaurant: NotRequired[bool]
    surprise_score_derived: NotRequired[dict[str, Any]]
    district: NotRequired[str]
    address: NotRequired[str]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    location: NotRequired[dict]


class Candidates(TypedDict):
    """召回/过滤阶段产出的候选与候选级元数据。"""

    nearby_restaurants: NotRequired[list[RetrievedRestaurant]]
    nearby_activities: NotRequired[list[RetrievedActivity]]
    nearby_gifts: NotRequired[list[RetrievedGift]]
    
    ranked_breakfast_combos: NotRequired[list[RankedCombo]]
    ranked_lunch_combos: NotRequired[list[RankedCombo]]
    ranked_afternoon_tea_combos: NotRequired[list[RankedCombo]]
    ranked_dinner_combos: NotRequired[list[RankedCombo]]
    ranked_late_night_combos: NotRequired[list[RankedCombo]]
    ranked_light_packages: NotRequired[list[RankedPackage]]
    
    ranked_packages: NotRequired[list[RankedPackage]]
    
    processed_steps: NotRequired[list[str]]

class Constraints(BaseModel):
    """
    为行程提取的用户约束条件 (Constraints)。
    """
    group_type: Literal["family", "friends"] = Field(
        ..., description="群体类型：家庭或朋友"
    )
    budget: float = Field(
        ..., description="旅行/活动的当地货币总预算。如果提供的是人均预算，请乘以总人数（或等效人数）。"
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list, description="饮食禁忌与偏好。请尽量归类为以下选项：'辣', '海鲜', '生冷', '甜', '快餐', '牛'。若不在上述分类内，请使用原词提取。"
    )
    preferred_distance: Literal["<2km", "2km-5km", ">5km"] = Field(
        default="2km-5km", description="偏好的出行距离范围"
    )
    time_period: str = Field(
        ..., description="行程的目标开始时间（如：'14:00'，'18:00'）。兼容历史值：也允许 'HH:MM-HH:MM'。"
    )
    duration_hours: Optional[tuple[float, float]] = Field(
        default=None, description="预期的总时长范围（小时），格式为 (min, max)。例如 (4.0, 6.0) 或 (6.0, 6.0)。"
    )
    activity_preferences: list[str] = Field(
        default_factory=list, description="用户要求的特定活动或氛围（如：'餐饮'、'电影'、'打卡点'、'安静'）"
    )

    adult_count: int = Field(
        default=2, description="成人数（预算过滤与人数口径以成人为准；单人默认1，情侣/朋友默认2，家庭可推断）"
    )
    child_count: int = Field(default=0, description="小孩数（未提及则为 0；提及但未给数量可按最小默认）")
    adult_genders: list[Literal["M", "F", "U"]] = Field(
        default_factory=list,
        description="成人性别列表：M/F/U（未知或未提及）。顺序与 adult_count 对齐。",
    )
    child_profiles: list[tuple[Literal["M", "F", "U"], int]] = Field(
        default_factory=list,
        description="小孩信息列表，每个元素为 (性别, 年龄)；年龄未知用 -1；孕妇标记为 0；性别未知用 U。",
    )
    commute_preference: Literal["auto", "walking", "taxi", "driving"] = Field(
        default="auto",
        description="出行偏好：auto(默认，按距离在 walking/taxi 中选择)、walking(偏走路)、taxi(少走路)、driving(开车)。",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data):
        if not isinstance(data, dict):
            return data

        child_ages = data.get("child_ages")
        if child_ages is not None and "child_profiles" not in data:
            data["child_profiles"] = [("U", int(age)) for age in (child_ages or []) if isinstance(age, (int, float))]

        adult_count = data.get("adult_count")
        if not isinstance(adult_count, int) or adult_count <= 0:
            adult_count = 2
        group_type = data.get("group_type")

        genders = data.get("adult_genders") or []
        if not isinstance(genders, list):
            genders = []

        if not genders:
            if group_type == "family":
                if adult_count >= 2:
                    genders = ["F", "M"] + ["F"] * (adult_count - 2)
                else:
                    genders = ["F"]
            else:
                genders = ["F"] * adult_count
        else:
            if len(genders) < adult_count:
                genders = genders + ["F"] * (adult_count - len(genders))
            elif len(genders) > adult_count:
                genders = genders[:adult_count]

        data["adult_genders"] = genders

        child_count = data.get("child_count")
        if not isinstance(child_count, int) or child_count < 0:
            child_count = 0

        raw_profiles = data.get("child_profiles") or []
        if not isinstance(raw_profiles, list):
            raw_profiles = []

        normalized_profiles: list[tuple[str, int]] = []
        for p in raw_profiles:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                g, a = p[0], p[1]
                gender = g if g in ("M", "F", "U") else "U"
                try:
                    age = int(a)
                except Exception:
                    age = -1
                if age < -1:
                    age = -1
                if age == 0:
                    gender = "U"
                elif gender == "U":
                    gender = "F"
                normalized_profiles.append((gender, age))

        if child_count < len(normalized_profiles):
            child_count = len(normalized_profiles)

        if child_count > len(normalized_profiles):
            normalized_profiles.extend([("F", -1)] * (child_count - len(normalized_profiles)))

        data["child_count"] = child_count
        data["child_profiles"] = normalized_profiles

        commute_pref = data.get("commute_preference")
        if commute_pref not in ("auto", "walking", "taxi", "driving"):
            data["commute_preference"] = "auto"

        tp = data.get("time_period")
        if not isinstance(tp, str) or not tp.strip():
            data["time_period"] = "14:00"

        dh: Any = data.get("duration_hours")
        if dh is None:
            return data

        if isinstance(dh, (int, float)):
            v = float(dh)
            data["duration_hours"] = (v, v)
            return data

        if isinstance(dh, (list, tuple)) and len(dh) == 2:
            a, b = dh[0], dh[1]
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                lo, hi = float(a), float(b)
                if lo > hi:
                    lo, hi = hi, lo
                data["duration_hours"] = (lo, hi)
                return data

        data["duration_hours"] = None
        return data

class PlanState(TypedDict):
    """
    规划子图状态。

    该状态服务于结构化规划链路：召回、过滤、重排、规划。
    顶层 Agent 编排与 handoff 状态请使用 ClosedLoopState。
    """
    constraints: NotRequired[Constraints]
    candidates: NotRequired[Candidates]
    past_itinerary: NotRequired[list[dict]]
    top_k: NotRequired[int]
    itinerary: NotRequired[dict]
    confirmation: NotRequired[dict]
    current_step: NotRequired[str]
    processed_steps: NotRequired[list[str]]


class ClosedLoopState(AgentState):
    """
    顶层 ClosedLoop Agent 状态。

    该状态用于 build_graph 之后的 Agent 编排、工具调用与后续 handoff。
    """
    user_input: str
    active_agent: NotRequired[str]
    latest_plan_result: NotRequired[list[dict]]
    plan_option: NotRequired[dict]
    constraints: NotRequired[Constraints]
    itinerary: NotRequired[list[dict]]
    confirmation: NotRequired[dict]
    current_step: NotRequired[Literal["plan_trip", "confirm_trip"]]
