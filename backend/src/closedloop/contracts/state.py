from typing import Optional, Literal, NotRequired
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain.agents import AgentState

class Constraints(BaseModel):
    """
    Extracted user constraints for the itinerary.
    """
    group_type: Literal["family", "friends"] = Field(
        ..., description="The type of the group, either 'family' (家庭) or 'friends' (朋友)"
    )
    people_count: int = Field(
        default=2, description="Estimated total number of people based on the context (e.g., '一家三口' -> 3, '朋友两人' -> 2)"
    )
    budget: float = Field(
        ..., description="The total budget for the trip/event in local currency. If per capita is provided, multiply by people_count."
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list, description="Specific ingredients (e.g., coriander, garlic, seafood) or flavor restrictions (e.g., no spicy, low oil)"
    )
    preferred_distance: Literal["<2km", "2km-5km", ">5km"] = Field(
        default="2km-5km", description="Preferred travel distance range"
    )
    time_period: str = Field(
        ..., description="The specific time period for the itinerary (e.g., '13:00-18:00', '18:00-21:00'). Avoid vague terms like 'afternoon'."
    )
    duration_hours: Optional[float] = Field(
        default=None, description="The expected duration of the trip in hours, if explicitly stated or inferred."
    )
    activity_preferences: list[str] = Field(
        default_factory=list, description="Specific activities or vibes requested by the user (e.g., 'dining', 'movies', 'photo spots', 'quiet')"
    )
    child_age: Optional[int] = Field(
        default=None, 
        description="The age of the child. 0 represents a pregnant woman. Only applicable if group_type is 'family'."
    )

class ClosedLoopState(AgentState):
    """
    Represents the state of the agent throughout the execution graph.
    """
    user_input: str
    constraints: NotRequired[Constraints]
    itinerary: NotRequired[dict]
    confirmation: NotRequired[dict]
    current_step: NotRequired[str]
