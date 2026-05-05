from typing import Optional, Literal, NotRequired
from typing_extensions import TypedDict, Required, TypeAlias
from pydantic import BaseModel, Field
from langchain.agents import AgentState

class RetrievedRestaurant(TypedDict, total=False):
    """召回阶段：餐厅条目（来自 mock_db/restaurants.json 原始数据）。"""
    id: Required[str]  # 对应 JSON 中的 restaurant_id
    name: Required[str]
    type: Required[Literal["restaurant"]]

    category: NotRequired[str]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    operating_hours: NotRequired[str]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    combos: NotRequired[list[dict]]


class RetrievedActivity(TypedDict, total=False):
    """召回阶段：活动条目（来自 mock_db/activities.json 原始数据）。"""
    id: Required[str]  # 对应 JSON 中的 venue_id
    name: Required[str]
    type: Required[Literal["activity"]]

    category: NotRequired[str]
    is_free: NotRequired[bool]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    operating_hours: NotRequired[str]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    packages: NotRequired[list[dict]]


class RetrievedGift(TypedDict, total=False):
    """召回阶段：礼物店条目（来自 mock_db/add_ons.json 原始数据）。"""
    id: Required[str]  # 对应 JSON 中的 shop_id
    name: Required[str]
    type: Required[Literal["gift_shop"]]

    category: NotRequired[str]
    rating: NotRequired[float]
    reviews_count: NotRequired[int]
    operating_hours: NotRequired[str]
    tags: NotRequired[list[str]]
    
    # 扁平化附加字段 (由 retrieve 节点计算附加)
    distance_km: NotRequired[float]
    location: NotRequired[dict]
    
    # 嵌套内容
    gifts: NotRequired[list[dict]]


class RankedCombo(TypedDict, total=False):
    """重排序阶段：扁平化的餐厅套餐条目，包含餐厅上下文。"""
    combo_id: Required[str]
    name: Required[str]
    price: Required[float]
    description: NotRequired[str]
    duration_mins: Required[int]
    duration_std_dev: NotRequired[float]
    suitable_time_slots: NotRequired[list[str]]
    score: Required[int]
    
    restaurant_id: Required[str]
    restaurant_name: Required[str]
    category: NotRequired[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    location: NotRequired[dict]


class RankedPackage(TypedDict, total=False):
    """重排序阶段：扁平化的活动套餐条目，包含活动场地上下文。"""
    package_id: Required[str]
    name: Required[str]
    price: Required[float]
    description: NotRequired[str]
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
    location: NotRequired[dict]


class RankedGift(TypedDict, total=False):
    """重排序阶段：扁平化的礼品条目，包含礼品店上下文。"""
    gift_id: Required[str]
    name: Required[str]
    price: Required[float]
    description: NotRequired[str]
    score: Required[int]

    shop_id: Required[str]
    shop_name: Required[str]
    category: NotRequired[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    location: NotRequired[dict]


class Candidates(TypedDict):
    """召回/过滤阶段产出的候选与候选级元数据。"""

    nearby_restaurants: NotRequired[list[RetrievedRestaurant]]
    nearby_activities: NotRequired[list[RetrievedActivity]]
    nearby_gifts: NotRequired[list[RetrievedGift]]
    
    ranked_combos: NotRequired[list[RankedCombo]]
    ranked_packages: NotRequired[list[RankedPackage]]
    ranked_gifts: NotRequired[list[RankedGift]]
    
    processed_steps: NotRequired[list[str]]

class Constraints(BaseModel):
    """
    为行程提取的用户约束条件 (Constraints)。
    """
    group_type: Literal["family", "friends"] = Field(
        ..., description="群体类型：家庭或朋友（内部编码为 family / friends）"
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
        ..., description="行程的具体时间段（如：'13:00-18:00'，'18:00-21:00'）。避免使用如'下午'这样模糊的词汇。"
    )
    duration_hours: Optional[float] = Field(
        default=None, description="如果明确说明或可以推断出，则为预期的旅行时长（小时）。"
    )
    activity_preferences: list[str] = Field(
        default_factory=list, description="用户要求的特定活动或氛围（如：'餐饮'、'电影'、'打卡点'、'安静'）"
    )

    adult_count: int = Field(
        default=2, description="成人数（预算过滤与人数口径以成人为准；朋友默认 2，家庭可推断）"
    )
    child_count: int = Field(default=0, description="小孩数（未提及则为 0；提及但未给数量可按最小默认）")
    child_ages: list[int] = Field(default_factory=list, description="小孩年龄列表（支持多个年龄；可为空）")

class ClosedLoopState(AgentState):
    """
    表示 Agent 在整个执行图中的状态。
    """
    user_input: str
    constraints: NotRequired[Constraints]
    candidates: NotRequired[Candidates]
    itinerary: NotRequired[dict]
    confirmation: NotRequired[dict]
    current_step: NotRequired[str]
