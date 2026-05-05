from typing import Optional, Literal, NotRequired
from typing_extensions import TypedDict, Required, TypeAlias
from pydantic import BaseModel, Field
from langchain.agents import AgentState

class RetrievedRestaurant(TypedDict, total=False):
    """召回阶段：餐厅条目（来自 mock_db 原始数据）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["restaurant"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    avg_price_per_person: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    avg_wait_minutes: NotRequired[int]
    duration_minutes: NotRequired[int]
    tags: NotRequired[list[str]]
    avoid_tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    has_child_seat: NotRequired[bool]
    supports_reservation: NotRequired[bool]
    supports_queue: NotRequired[bool]
    location: NotRequired[str]
    description: NotRequired[str]


class RetrievedActivity(TypedDict, total=False):
    """召回阶段：活动条目（来自 mock_db 原始数据）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["activity"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    price_per_person: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    duration_minutes: NotRequired[int]
    tags: NotRequired[list[str]]
    avoid_tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    min_child_age: NotRequired[int]
    max_child_age: NotRequired[int]
    supports_reservation: NotRequired[bool]
    location: NotRequired[str]
    description: NotRequired[str]


class RetrievedGift(TypedDict, total=False):
    """召回阶段：礼物店条目（对应 mock_db 的 gift_shop）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["gift_shop"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    duration_minutes: NotRequired[int]
    price: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    supported_target_types: NotRequired[list[Literal["restaurant", "activity"]]]
    lead_time_minutes: NotRequired[int]
    handoff_minutes: NotRequired[int]
    location: NotRequired[str]
    description: NotRequired[str]


class FilteredRestaurant(TypedDict, total=False):
    """过滤阶段：餐厅条目（当前与召回阶段一致，但包含 score）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["restaurant"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    avg_price_per_person: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    avg_wait_minutes: NotRequired[int]
    duration_minutes: NotRequired[int]
    tags: NotRequired[list[str]]
    avoid_tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    has_child_seat: NotRequired[bool]
    supports_reservation: NotRequired[bool]
    supports_queue: NotRequired[bool]
    location: NotRequired[str]
    description: NotRequired[str]

    score: Required[int]


class FilteredActivity(TypedDict, total=False):
    """过滤阶段：活动条目（当前与召回阶段一致，但包含 score）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["activity"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    price_per_person: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    duration_minutes: NotRequired[int]
    tags: NotRequired[list[str]]
    avoid_tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    min_child_age: NotRequired[int]
    max_child_age: NotRequired[int]
    supports_reservation: NotRequired[bool]
    location: NotRequired[str]
    description: NotRequired[str]

    score: Required[int]


class FilteredGift(TypedDict, total=False):
    """过滤阶段：礼物/附加服务条目（当前与召回阶段一致，但包含 score）。"""

    id: Required[str]
    name: Required[str]
    type: Required[Literal["gift_shop"]]

    category: NotRequired[str]
    distance_km: NotRequired[float]
    rating: NotRequired[float]
    open_time: NotRequired[str]
    close_time: NotRequired[str]
    price: NotRequired[float]
    tags: NotRequired[list[str]]
    suitable_groups: NotRequired[list[str]]
    supported_target_types: NotRequired[list[Literal["restaurant", "activity"]]]
    lead_time_minutes: NotRequired[int]
    handoff_minutes: NotRequired[int]
    location: NotRequired[str]
    description: NotRequired[str]

    score: Required[int]


RestaurantCandidate: TypeAlias = RetrievedRestaurant | FilteredRestaurant
ActivityCandidate: TypeAlias = RetrievedActivity | FilteredActivity
GiftCandidate: TypeAlias = RetrievedGift | FilteredGift


class Candidates(TypedDict):
    """召回/过滤阶段产出的候选与候选级元数据。"""

    nearby_restaurants: NotRequired[list[RestaurantCandidate]]
    nearby_activities: NotRequired[list[ActivityCandidate]]
    nearby_gifts: NotRequired[list[GiftCandidate]]
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
