from typing import Optional, Literal, NotRequired
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain.agents import AgentState

class Constraints(BaseModel):
    """
    为行程提取的用户约束条件 (Constraints)。
    """
    group_type: Literal["family", "friends"] = Field(
        ..., description="群体类型，可以是 'family' (家庭) 或 'friends' (朋友)"
    )
    people_count: int = Field(
        default=2, description="基于上下文估计的总人数（例如，'一家三口' -> 3，'朋友两人' -> 2）"
    )
    budget: float = Field(
        ..., description="旅行/活动的当地货币总预算。如果提供的是人均预算，请乘以 people_count。"
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list, description="特定食材（如：香菜、大蒜、海鲜）或口味限制（如：不吃辣、少油）"
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
    child_age: Optional[int] = Field(
        default=None, 
        description="儿童的年龄。0 表示孕妇。仅当 group_type 为 'family' 时适用。"
    )

class ClosedLoopState(AgentState):
    """
    表示 Agent 在整个执行图 (execution graph) 中的状态。
    """
    user_input: str
    constraints: NotRequired[Constraints]
    itinerary: NotRequired[dict]
    confirmation: NotRequired[dict]
    current_step: NotRequired[str]
