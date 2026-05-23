from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger


class ExecuteItineraryInput(BaseModel):
    """用于执行（预订）行程的结构化输入。"""

    plan_id: str = Field(..., description="要执行的行程方案ID，如 'plan_1'")
    book_commutes_policy: Literal["first_only", "all"] = Field(
        default="first_only",
        description="通勤预订策略。'first_only' 表示只预约出发地到第一目的地的车，剩下的询问；'all' 表示一次性预约行程中所有的车程（适用于偏向J型、计划性强的用户）。",
    )


@tool(args_schema=ExecuteItineraryInput)
def execute_itinerary(
    plan_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    book_commutes_policy: Literal["first_only", "all"] = "first_only",
) -> Command:
    """
    执行用户的行程方案，包括预订套餐、活动以及预约交通。
    """
    config = get_config()
    LoggerManager.setup(config)

    logger.info(
        f"phase=execute_itinerary | input=plan_id={plan_id} book_commutes_policy={book_commutes_policy}"
    )

    # 找到对应的 plan
    latest_plan_result = state.get("latest_plan_result", [])
    plans = latest_plan_result if isinstance(latest_plan_result, list) else []

    target_plan = None
    for p in plans:
        if p.get("plan_id") == plan_id:
            target_plan = p
            break

    if not target_plan:
        result = {"error": "找不到指定的方案ID", "plan_id": plan_id}
        status = "failed"
        logger.error(
            f"phase=execute_itinerary | error=plan_not_found | plan_id={plan_id}"
        )
    else:
        # 开始模拟预订
        steps = target_plan.get("steps", [])
        booked_items = []
        commute_status = []

        is_first_commute = True

        for step in steps:
            item = step.get("item", {})
            item_type = item.get("type")
            item_id = item.get("id")
            name = item.get("name")

            if item_type == "commute":
                # 通勤逻辑
                commute_mode = item.get("commute_mode")
                if is_first_commute:
                    if commute_mode == "taxi":
                        commute_status.append(
                            {
                                "id": item_id,
                                "name": name,
                                "status": "booked",
                                "message": "已为您预约出发地到第一目的地的车",
                            }
                        )
                    else:
                        commute_status.append(
                            {
                                "id": item_id,
                                "name": name,
                                "status": "skipped",
                                "message": "该出行方式无需预约",
                            }
                        )
                    is_first_commute = False
                else:
                    if commute_mode != "taxi":
                        commute_status.append(
                            {
                                "id": item_id,
                                "name": name,
                                "status": "skipped",
                                "message": "该出行方式无需预约",
                            }
                        )
                    elif book_commutes_policy == "all":
                        commute_status.append(
                            {
                                "id": item_id,
                                "name": name,
                                "status": "booked",
                                "message": "已为您预约此段车程",
                            }
                        )
                    else:
                        commute_status.append(
                            {
                                "id": item_id,
                                "name": name,
                                "status": "pending_user_confirmation",
                                "message": "是否需要为您预约此段车程？",
                            }
                        )
            else:
                # 餐厅、活动、礼品等直接预订
                booked_items.append(
                    {
                        "id": item_id,
                        "name": name,
                        "type": item_type,
                        "status": "booked",
                        "message": "预订成功",
                    }
                )

        result = {
            "plan_id": plan_id,
            "booked_items": booked_items,
            "commute_status": commute_status,
            "message": "核心套餐已全部预订成功。第一程交通已预约。"
            + (
                "其余交通也已全部预约。"
                if book_commutes_policy == "all"
                else "请确认是否需要预约后续的交通。"
            ),
        }
        status = "success"
        logger.info(
            f"phase=execute_itinerary | result=success | booked_items={len(booked_items)}"
        )

    execute_message = ToolMessage(
        content={
            "tool": "execute_itinerary",
            "status": status,
            "result": result,
        },
        tool_call_id=tool_call_id,
    )

    update = {
        "confirmation": result,
        "current_step": "confirm_trip",
        "messages": [execute_message],
    }

    return Command(update=update)
