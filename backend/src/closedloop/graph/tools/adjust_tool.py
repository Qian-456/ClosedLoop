import json
import httpx
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.plan_subgraph.repairer import repair_plan
from closedloop.graph.tools.plan_sub_api import request_plan_sub_json
from closedloop.contracts.state import Constraints
from langchain_core.runnables import RunnableConfig

class AdjustPlanItemInput(BaseModel):
    plan_id: str = Field(..., description="要修改的方案 ID")
    target_item_id: str = Field(..., description="方案中需要被替换的旧条目 ID")
    new_item_id: str = Field(..., description="从 search_candidates 结果中挑选出的新条目 ID")

@tool(args_schema=AdjustPlanItemInput)
def adjust_plan_item(
    plan_id: str,
    target_item_id: str,
    new_item_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config_runnable: RunnableConfig,
) -> Command:
    """
    替换行程中的指定条目，并自动处理引发的时间和预算冲突（5级修复策略）。
    """
    config = get_config()
    LoggerManager.setup(config)
    tool_http_timeout_secs = float(getattr(config, "TOOL_HTTP_TIMEOUT_SECS", 3.0))

    logger.info(f"phase=adjust_plan_item | plan_id={plan_id} | target={target_item_id} | new={new_item_id}")

    latest_plans = state.get("latest_plan_result", [])
    target_plan = None
    for p in latest_plans:
        if isinstance(p, dict) and p.get("plan_id") == plan_id:
            target_plan = p
            break
            
    if not target_plan:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": "找不到指定的方案 ID"}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

    # 优先从 candidates 里找出 new_item_id 的完整数据
    candidates = state.get("candidates", {})
    new_item_data = None
    for k in ["ranked_breakfast_combos", "ranked_lunch_combos", "ranked_afternoon_tea_combos", "ranked_dinner_combos", "ranked_late_night_combos", "ranked_packages", "ranked_light_packages", "ranked_gifts"]:
        for item in candidates.get(k, []):
            item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
            if item_id == new_item_id:
                new_item_data = item
                break
        if new_item_data:
            break
            
    # 如果候选池中找不到，请求 plan_sub_backend API 获取完整数据（替换原有的读取本地 json 文件兜底逻辑）
    if not new_item_data:
        session_id = config_runnable.get("configurable", {}).get("thread_id", "default")
        
        try:
            res_data = request_plan_sub_json(
                method="GET",
                configured_url=getattr(config, "PLAN_SUB_API_URL", "http://localhost:8001/plan"),
                target_path=f"/item/{new_item_id}",
                phase="adjust_plan_item",
                params={"session_id": session_id},
                timeout=tool_http_timeout_secs,
                network_mode=getattr(config, "PLAN_SUB_NETWORK_MODE", "local"),
            )
            if res_data.get("status") == "success" and res_data.get("item"):
                new_item_data = res_data.get("item")
        except Exception as e:
            logger.warning(f"phase=adjust_plan_item | msg=api_fallback_search_error | error={e}")

    if not new_item_data:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": f"找不到指定的新条目 ({new_item_id})，请检查 ID 是否正确"}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

    constraints_dict = state.get("constraints", {})
    budget = constraints_dict.get("budget", 999999.0)
    
    # 重新解析 duration_hours_range
    duration_hours = constraints_dict.get("duration_hours")
    duration_hours_range = (4.0, 6.0) # default
    if isinstance(duration_hours, (list, tuple)) and len(duration_hours) == 2:
        duration_hours_range = (float(duration_hours[0]), float(duration_hours[1]))
    elif isinstance(duration_hours, (int, float)):
        duration_hours_range = (float(duration_hours), float(duration_hours))
        
    duration_range_mins = (duration_hours_range[0] * 60.0, duration_hours_range[1] * 60.0)
    commute_preference = constraints_dict.get("commute_preference", "auto")

    result = repair_plan(
        plan=target_plan,
        target_item_id=target_item_id,
        new_item=new_item_data,
        budget=budget,
        duration_range_mins=duration_range_mins,
        candidates=candidates,
        commute_preference=commute_preference
    )

    status = result.get("status", "failed")

    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "adjust_plan_item",
            "status": status,
            "result": result,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )

    update = {
        "current_step": "adjust_plan_item",
        "messages": [transfer_message],
    }

    # 如果修复成功，我们把最新的 plan 替换到 latest_plan_result 中
    if status == "success" and "plan" in result:
        new_plan = result["plan"]
        updated_latest = []
        for p in latest_plans:
            if isinstance(p, dict) and p.get("plan_id") == plan_id:
                updated_latest.append(new_plan)
            else:
                updated_latest.append(p)
        update["latest_plan_result"] = updated_latest

        # 同时更新 itinerary (历史记录)
        itinerary = state.get("itinerary", [])
        if isinstance(itinerary, list):
            updated_itinerary = []
            for p in itinerary:
                if isinstance(p, dict) and p.get("plan_id") == plan_id:
                    updated_itinerary.append(new_plan)
                else:
                    updated_itinerary.append(p)
            update["itinerary"] = updated_itinerary

    return Command(update=update)
