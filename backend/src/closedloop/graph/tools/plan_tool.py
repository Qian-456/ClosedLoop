from typing import Annotated, Literal, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.contracts.state import ClosedLoopState, Constraints, PlanState
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.plan_subgraph.builder import build_subgraph_plan


class PlanTripInput(BaseModel):
    """用于生成本地生活行程规划的结构化输入。"""

    group_type: Literal["solo", "couple", "family", "friends", "business"] = Field(
        ..., description="群体类型：单人、情侣、家庭、朋友或商务"
    )
    budget: float = Field(
        ...,
        description="旅行/活动的当地货币总预算。如果提供的是人均预算，请乘以总人数或等效人数。",
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description=(
            "饮食禁忌与偏好。请尽量归类为以下选项："
            "'辣', '海鲜', '生冷', '甜', '快餐', '牛'。"
            "若不在上述分类内，请使用原词提取。"
        ),
    )
    preferred_distance: Literal["<2km", "2km-5km", ">5km"] = Field(
        default="2km-5km", description="偏好的出行距离范围"
    )
    time_period: str = Field(
        ...,
        description="行程的目标开始时间，如 '14:00'、'18:00'。兼容历史值：也允许 'HH:MM-HH:MM'。",
    )
    duration_hours: Optional[tuple[float, float]] = Field(
        default=None,
        description="预期的总时长范围，单位小时，格式为 (min, max)，例如 (4.0, 6.0)。",
    )
    activity_preferences: list[str] = Field(
        default_factory=list,
        description="用户要求的特定活动或氛围，如：'餐饮'、'电影'、'打卡点'、'安静'。",
    )
    adult_count: int = Field(
        default=2,
        description="成人数。预算过滤与人数口径以成人为准；单人默认1，情侣/朋友默认2，家庭可推断。",
    )
    child_count: int = Field(default=0, description="小孩数。未提及则为 0；提及但未给数量可按最小默认。")
    adult_genders: list[Literal["M", "F", "U"]] = Field(
        default_factory=list,
        description="成人性别列表：M/F/U，未知或未提及用 U。顺序与 adult_count 对齐。",
    )
    child_profiles: list[tuple[Literal["M", "F", "U"], int]] = Field(
        default_factory=list,
        description="小孩信息列表，每个元素为 (性别, 年龄)；年龄未知用 -1；孕妇标记为 0；性别未知用 U。",
    )
    commute_preference: Literal["auto", "walking", "taxi", "driving"] = Field(
        default="auto",
        description="出行偏好：auto 默认按距离选择；walking 偏走路；taxi 少走路；driving 开车。",
    )


def _normalize_constraints(data: dict) -> dict:
    """复用 Constraints 契约完成默认值与边界归一化。"""
    constraints = Constraints(**data)
    return constraints.model_dump()


@tool(args_schema=PlanTripInput)
def plan_trip(
    group_type: Literal["solo", "couple", "family", "friends", "business"],
    budget: float,
    time_period: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    dietary_restrictions: list[str] | None = None,
    preferred_distance: Literal["<2km", "2km-5km", ">5km"] = "2km-5km",
    duration_hours: Optional[tuple[float, float]] = None,
    activity_preferences: list[str] | None = None,
    adult_count: int = 2,
    child_count: int = 0,
    adult_genders: list[Literal["M", "F", "U"]] | None = None,
    child_profiles: list[tuple[Literal["M", "F", "U"], int]] | None = None,
    commute_preference: Literal["auto", "walking", "taxi", "driving"] = "auto",
) -> Command:
    """
    根据结构化参数调用本地规划子图，生成多套本地生活行程方案。

    该工具只做进程内子图调用，不访问 HTTP 接口。
    """
    config = get_config()
    LoggerManager.setup(config)

    logger.info(f"phase=plan_trip | input=group_type={group_type} budget={budget} time_period={time_period}")

    user_input = str(state.get("user_input", ""))
    
    # 提取已有的 itinerary 历史，确保是列表
    past_itinerary = state.get("itinerary", [])
    if not isinstance(past_itinerary, list):
        past_itinerary = [past_itinerary] if past_itinerary else []

    raw_constraints = {
        "group_type": group_type,
        "budget": budget,
        "dietary_restrictions": dietary_restrictions or [],
        "preferred_distance": preferred_distance,
        "time_period": time_period,
        "duration_hours": duration_hours,
        "activity_preferences": activity_preferences or [],
        "adult_count": adult_count,
        "child_count": child_count,
        "adult_genders": adult_genders or [],
        "child_profiles": child_profiles or [],
        "commute_preference": commute_preference,
    }

    try:
        constraints = _normalize_constraints(raw_constraints)
        subgraph_state: PlanState = {
            "user_input": user_input,
            "constraints": constraints,
        }
        subgraph_output = build_subgraph_plan().invoke(subgraph_state)
        result = subgraph_output.get("itinerary", {}) if isinstance(subgraph_output, dict) else {}
        status = "success"
        logger.info(f"phase=plan_trip | result=success | itinerary_status={result.get('status')}")
    except Exception as e:
        constraints = raw_constraints
        result = {
            "error": "规划子图调用失败",
            "message": str(e),
            "constraints": constraints,
        }
        status = "failed"
        logger.error(f"phase=plan_trip | error={e}")

    transfer_message = ToolMessage(
        content={
            "tool": "plan_trip",
            "status": status,
            "result": result,
        },
        tool_call_id=tool_call_id,
    )

    update = {
        "constraints": constraints,
        "latest_plan_result": result.get("plans", []) if isinstance(result, dict) else [],
        "current_step": "plan_trip",
        "messages": [transfer_message],
    }

    if isinstance(result, dict) and "error" not in result:
        # 将新生成的 plans 扩展进历史中
        new_plans = result.get("plans", []) if isinstance(result, dict) else []
        past_itinerary.extend(new_plans)
        update["itinerary"] = past_itinerary

    return Command(update=update)


@tool
def transfer_to_execute(
    plan_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    Transfer control to execute agent node.
    You MUST provide the selected plan_id (e.g., 'plan_1', 'plan_2') that the user wants to execute.
    """
    latest_plan_result = state.get("latest_plan_result", [])
    selected_plan_data = None
    if isinstance(latest_plan_result, list):
        for plan in latest_plan_result:
            if isinstance(plan, dict) and plan.get("plan_id") == plan_id:
                selected_plan_data = plan
                break
    
    if selected_plan_data is None:
        selected_plan_data = {"plan_id": plan_id, "error": "Plan not found"}

    return Command(update={
        "messages": [
            ToolMessage(
                content=f"Transferred to execute agent with plan_id: {plan_id}",
                tool_call_id=tool_call_id
            )
        ],
        # Transition to next step
        "plan_option": selected_plan_data,
        "current_step": "transfer_to_execute",
        "active_agent": "execute_agent"
    })