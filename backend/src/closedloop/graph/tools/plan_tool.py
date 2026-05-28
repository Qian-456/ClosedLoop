import json
import time
from typing import Annotated, Literal, Optional
import httpx

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from langchain_core.runnables import RunnableConfig

from closedloop.contracts.state import ClosedLoopState, Constraints, PlanState
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.tools.plan_sub_api import request_plan_sub_json

PLAN_SUB_RETRYABLE_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError)


class PlanTripInput(BaseModel):
    """用于生成本地生活行程规划的结构化输入。"""

    group_type: Literal["family", "friends"] = Field(
        ..., description="群体类型：家庭或朋友"
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
        description="小孩信息列表，每个元素为 (性别, 年龄)；小孩的性别默认女(F)，如果不知道岁数默认-1，年龄为0代表孕妇，性别可以填U。",
    )
    commute_preference: Literal["auto", "walking", "taxi", "driving"] = Field(
        default="auto",
        description="出行偏好：auto 默认按距离选择；walking 偏走路；taxi 少走路；driving 开车。",
    )
    preferred_pattern_steps: Optional[list[str]] = Field(
        default=None,
        description="用户指定的行程活动顺序。如果提供，将优先使用该顺序生成方案。例如 ['activity', 'activity', 'restaurant:dinner']"
    )
    include_gift: bool = Field(
        default=True,
        description="是否推荐包含礼品（gift_shop）的行程。默认为 True。除非用户明确说不要推荐礼品、惊喜等，才设为 False。"
    )


def _count_plan_candidates(candidates: dict | None) -> dict[str, int]:
    """Summarize ranked candidate counts returned by the plan subgraph."""
    candidate_state = candidates or {}
    return {
        "restaurant_count": sum(
            len(candidate_state.get(key, []) or [])
            for key in (
                "ranked_breakfast_combos",
                "ranked_lunch_combos",
                "ranked_afternoon_tea_combos",
                "ranked_dinner_combos",
                "ranked_late_night_combos",
            )
        ),
        "activity_count": sum(
            len(candidate_state.get(key, []) or [])
            for key in ("ranked_light_packages", "ranked_packages")
        ),
        "gift_count": len(candidate_state.get("ranked_gifts", []) or []),
    }


def _normalize_constraints(data: dict) -> dict:
    """复用 Constraints 契约完成默认值与边界归一化。"""
    constraints = Constraints(**data)
    return constraints.model_dump()


@tool(args_schema=PlanTripInput)
def plan_trip(
    group_type: Literal["family", "friends"],
    budget: float,
    time_period: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config_runnable: RunnableConfig,
    dietary_restrictions: list[str] | None = None,
    preferred_distance: Literal["<2km", "2km-5km", ">5km"] = "2km-5km",
    duration_hours: Optional[tuple[float, float]] = None,
    activity_preferences: list[str] | None = None,
    adult_count: int = 2,
    child_count: int = 0,
    adult_genders: list[Literal["M", "F", "U"]] | None = None,
    child_profiles: list[tuple[Literal["M", "F", "U"], int]] | None = None,
    commute_preference: Literal["auto", "walking", "taxi", "driving"] = "auto",
    preferred_pattern_steps: Optional[list[str]] = None,
    include_gift: bool = True,
) -> Command:
    """
    根据结构化参数调用本地规划子图，生成多套本地生活行程方案。

    该工具只做进程内子图调用，不访问 HTTP 接口。
    """
    config = get_config()
    LoggerManager.setup(config)
    session_id = config_runnable.get("configurable", {}).get("thread_id", "default")

    logger.info(f"phase=plan_trip | input=group_type={group_type} budget={budget} time_period={time_period} session_id={session_id}")

    # 因为 plan_trip 代表全新的约束规划，所以清空历史方案，使 plan_id 重新从 plan_1 开始
    past_itinerary = []

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
        "preferred_pattern_steps": preferred_pattern_steps,
        "include_gift": include_gift,
    }

    try:
        constraints = _normalize_constraints(raw_constraints)
        
        payload = {
            "constraints": constraints,
            "past_itinerary": past_itinerary,
            "top_k": 1,
            "session_id": session_id,
        }
        
        for attempt in range(3):
            try:
                subgraph_output = request_plan_sub_json(
                    method="POST",
                    configured_url=getattr(config, "PLAN_SUB_API_URL", "http://localhost:8001/plan"),
                    target_path="/plan",
                    phase="plan_trip",
                    json=payload,
                    timeout=3.0,
                    network_mode=getattr(config, "PLAN_SUB_NETWORK_MODE", "local"),
                )
                break
            except PLAN_SUB_RETRYABLE_ERRORS as e:
                if attempt == 2:
                    raise
                logger.warning(
                    f"phase=plan_trip | msg=retrying | attempt={attempt+1} | retryable=True | error={e}"
                )
                time.sleep(2.0)

        candidates = subgraph_output.get("candidates", {}) if isinstance(subgraph_output, dict) else {}
        result = subgraph_output.get("itinerary", {}) if isinstance(subgraph_output, dict) else {}
        status = "success"
        candidate_counts = _count_plan_candidates(candidates)
        logger.info(
            f"phase=plan_trip | msg=persist_candidates_to_state "
            f"| restaurant_count={candidate_counts['restaurant_count']} "
            f"| activity_count={candidate_counts['activity_count']} "
            f"| gift_count={candidate_counts['gift_count']}"
        )
        logger.info(f"phase=plan_trip | result=success | itinerary_status={result.get('status')}")
    except Exception as e:
        constraints = raw_constraints
        candidates = {}
        result = {
            "error": "规划子图调用失败",
            "message": str(e),
            "constraints": constraints,
        }
        status = "failed"
        logger.error(f"phase=plan_trip | error={e}")

    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "plan_trip",
            "status": status,
            "result": result,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )

    update = {
        "constraints": constraints,
        "candidates": candidates,
        "latest_plan_result": result.get("plans", []) if isinstance(result, dict) else [],
        "current_step": "plan_trip",
        "messages": [transfer_message],
    }

    if isinstance(result, dict) and "error" not in result:
        # 因为是全新约束，所以直接覆盖历史
        new_plans = result.get("plans", []) if isinstance(result, dict) else []
        update["itinerary"] = new_plans
        update["latest_plan_result"] = new_plans

    return Command(update=update)


class GenerateAlternativePlansInput(BaseModel):
    count: int = Field(default=2, description="需要生成的额外备选方案数量。默认生成2个。")

@tool(args_schema=GenerateAlternativePlansInput)
def generate_alternative_plans(
    count: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config_runnable: RunnableConfig,
) -> Command:
    """
    基于当前已有的 constraints，生成更多与历史方案不同的备选方案。
    这会保证生成的方案和已有的历史方案有较大的相似度差异（至少一半元素不同）。
    """
    config = get_config()
    LoggerManager.setup(config)
    session_id = config_runnable.get("configurable", {}).get("thread_id", "default")
    
    logger.info(f"phase=generate_alternative_plans | count={count} | session_id={session_id}")
    
    constraints = state.get("constraints")
    if not constraints:
        return Command(update={
            "messages": [
                ToolMessage(
                    content="错误：当前没有可用的约束条件，请先调用 plan_trip。",
                    tool_call_id=tool_call_id,
                )
            ]
        })
        
    past_itinerary = state.get("itinerary", [])
    if not isinstance(past_itinerary, list):
        past_itinerary = [past_itinerary] if past_itinerary else []
        
    try:
        payload = {
            "constraints": constraints,
            "past_itinerary": past_itinerary,
            "top_k": count,
            "session_id": session_id,
        }
        
        import time
        for attempt in range(3):
            try:
                subgraph_output = request_plan_sub_json(
                    method="POST",
                    configured_url=getattr(config, "PLAN_SUB_API_URL", "http://localhost:8001/plan"),
                    target_path="/plan",
                    phase="generate_alternative_plans",
                    json=payload,
                    timeout=30.0,
                    network_mode=getattr(config, "PLAN_SUB_NETWORK_MODE", "local"),
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"phase=generate_alternative_plans | msg=retrying | attempt={attempt+1} | error={e}")
                time.sleep(2.0)
            
        result = subgraph_output.get("itinerary", {}) if isinstance(subgraph_output, dict) else {}
        status = "success"
        logger.info(f"phase=generate_alternative_plans | result=success | count={count}")
    except Exception as e:
        result = {"error": str(e)}
        status = "failed"
        logger.error(f"phase=generate_alternative_plans | error={e}")
        
    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "generate_alternative_plans",
            "status": status,
            "result": result,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )
    
    update = {
        "current_step": "generate_alternative_plans",
        "messages": [transfer_message],
    }
    
    if isinstance(result, dict) and "error" not in result:
        new_plans = result.get("plans", []) if isinstance(result, dict) else []
        past_itinerary.extend(new_plans)
        update["itinerary"] = past_itinerary
        # 将追加了新方案的完整列表作为 latest_plan_result，让用户可以选择当前约束下的所有历史方案
        update["latest_plan_result"] = past_itinerary

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
