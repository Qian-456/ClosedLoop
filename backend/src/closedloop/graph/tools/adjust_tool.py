import json
import httpx
from typing import Annotated, Literal, Any

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


import time
from closedloop.graph.tools.execute_tool import _do_execute_itinerary


def _build_adjust_execute_update(
    exec_update: dict,
    exec_status: str,
    execute_message: ToolMessage,
    new_plan: dict,
    updated_latest: list,
    updated_itinerary: list | None,
) -> dict:
    """合并执行阶段状态，避免补齐执行成功后前端保留旧的 needs_fixup。"""
    update_dict = dict(exec_update or {})
    update_dict["messages"] = [execute_message]
    update_dict["plan_option"] = new_plan
    update_dict["latest_plan_result"] = updated_latest

    if updated_itinerary is not None:
        update_dict["itinerary"] = updated_itinerary

    confirmation = update_dict.get("confirmation") if isinstance(update_dict.get("confirmation"), dict) else {}
    if isinstance(confirmation, dict) and confirmation.get("status") == "pending_payment":
        update_dict["current_step"] = "pending_payment"
        update_dict["active_agent"] = "execute_agent"
    elif exec_status != "needs_fixup":
        update_dict["current_step"] = "adjust_and_execute_plan_item"
        update_dict["active_agent"] = "plan_agent"

    if exec_status == "failed":
        update_dict["execution_report"] = None

    return update_dict


def _build_updated_plan_list(latest_plans: Any, plan_id: str, new_plan: dict) -> list:
    """替换指定 plan；如果原列表缺失该 plan，则追加，保证新方案能写回状态。"""
    plans = latest_plans if isinstance(latest_plans, list) else []
    updated: list = []
    replaced = False
    for plan in plans:
        if isinstance(plan, dict) and plan.get("plan_id") == plan_id:
            updated.append(new_plan)
            replaced = True
        else:
            updated.append(plan)
    if not replaced:
        updated.append(new_plan)
    return updated


def _validate_active_fixup_target(plan_id: str, target_item_id: str, state: dict) -> dict | None:
    """校验补齐阶段一次只能处理当前 confirmation.fixup 指定的目标项。"""
    confirmation = state.get("confirmation") if isinstance(state, dict) else None
    if not isinstance(confirmation, dict) or confirmation.get("status") != "needs_fixup":
        return None

    fixup = confirmation.get("fixup")
    if not isinstance(fixup, dict):
        return None

    expected_plan_id = fixup.get("plan_id")
    expected_target_item_id = fixup.get("target_item_id")
    if (
        isinstance(expected_plan_id, str)
        and expected_plan_id
        and expected_plan_id != plan_id
    ) or (
        isinstance(expected_target_item_id, str)
        and expected_target_item_id
        and expected_target_item_id != target_item_id
    ):
        return {
            "tool": "adjust_and_execute_plan_item",
            "status": "rejected",
            "code": "FIXUP_TARGET_MISMATCH",
            "message": "当前补齐流程一次只能处理黄色卡指定的目标项，请等待当前目标项完成后再处理下一项。",
            "expected_plan_id": expected_plan_id,
            "actual_plan_id": plan_id,
            "expected_target_item_id": expected_target_item_id,
            "actual_target_item_id": target_item_id,
        }

    return None


class AdjustAndExecutePlanItemInput(BaseModel):
    plan_id: str = Field(..., description="要修改的方案 ID")
    target_item_id: str = Field(..., description="方案中需要被替换的旧条目 ID")
    new_item_id: str = Field(..., description="从 search_candidates 结果中挑选出的新条目 ID")
    book_commutes_policy: Literal["first_only", "all"] = Field(
        default="first_only",
        description="通勤预订策略。'first_only' 表示只预约出发地到第一目的地的车，剩下的询问；'all' 表示一次性预约行程中所有的车程（适用于偏向J型、计划性强的用户）。"
    )

class AdjustPlanItemInput(BaseModel):
    plan_id: str = Field(..., description="要修改的方案 ID")
    target_item_id: str = Field(..., description="方案中需要被替换的旧条目 ID")
    new_item_id: str = Field(..., description="从 search_candidates 结果中挑选出的新条目 ID")


def _do_adjust_plan_item(
    plan_id: str,
    target_item_id: str,
    new_item_id: str,
    state: dict,
    config: Any,
    config_runnable: RunnableConfig,
) -> tuple[str, dict, str]:
    """核心的 adjust 逻辑，返回 (status, result, error_msg)"""
    tool_http_timeout_secs = float(getattr(config, "TOOL_HTTP_TIMEOUT_SECS", 3.0))

    target_plan = None
    plan_option = state.get("plan_option")
    if isinstance(plan_option, dict) and plan_option.get("plan_id") == plan_id:
        target_plan = plan_option
        
    latest_plans = state.get("latest_plan_result", [])
    if not target_plan:
        for p in latest_plans:
            if isinstance(p, dict) and p.get("plan_id") == plan_id:
                target_plan = p
                break
                
    if not target_plan:
        return "failed", {}, "找不到指定的方案 ID"

    execution_report = state.get("execution_report", {}) if isinstance(state, dict) else {}
    execution_summary = (
        execution_report.get("execution_summary")
        if isinstance(execution_report, dict)
        else None
    )
    execution_items = (
        execution_summary.get("items")
        if isinstance(execution_summary, dict)
        else None
    )
    executed_ids: set[str] = set()
    if isinstance(execution_items, list):
        for item in execution_items:
            if not isinstance(item, dict):
                continue
            if item.get("reserved") is not True:
                continue
            item_id_val = item.get("item_id")
            if isinstance(item_id_val, str) and item_id_val:
                executed_ids.add(item_id_val)
            if item.get("replaced"):
                new_item_id_val = item.get("new_item_id")
                if isinstance(new_item_id_val, str) and new_item_id_val:
                    executed_ids.add(new_item_id_val)

    if target_item_id in executed_ids:
        return "failed", {}, "该项目已成功预订/执行，禁止替换；如需变更请重新规划新方案再执行"

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
            
    # 如果候选池中找不到，请求 plan_sub_backend API 获取完整数据
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
        return "failed", {}, f"找不到指定的新条目 ({new_item_id})，请检查 ID 是否正确"

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
    
    # 【新增限制】如果在 Adjust & Execute 过程中触发了 L4（删项）或者 L5（修不好）
    # 我们认为这种“破坏性”的修复不能被静默执行，必须返回失败，交由 Agent 处理
    if status == "success" and "plan" in result:
        original_steps_count = len([s for s in target_plan.get("steps", []) if s.get("item", {}).get("type") != "commute"])
        new_steps_count = len([s for s in result["plan"].get("steps", []) if s.get("item", {}).get("type") != "commute"])
        
        if new_steps_count < original_steps_count:
            # 说明触发了 L4 删除了项目
            return "failed", {}, "替换该备选会导致总时间或总预算严重超标，系统尝试删除了您的其他活动（如礼品或下午茶）来弥补，但这会破坏您的原定体验。请您选择其他备选，或者放弃替换。"
            
    if status == "need_user_choice":
        return "failed", {}, "替换该备选会导致总时间或总预算严重超标，且无法自动修复。请您选择其他不会严重超标的备选，或者放弃替换。"

    return status, result, ""

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
    替换行程中的指定条目，并自动处理引发的时间和预算冲突（确定性 2–3 层最小改动修复）。
    """
    config = get_config()
    LoggerManager.setup(config)
    logger.info(f"phase=adjust_plan_item | plan_id={plan_id} | target={target_item_id} | new={new_item_id}")

    status, result, error_msg = _do_adjust_plan_item(
        plan_id, target_item_id, new_item_id, state, config, config_runnable
    )
    
    if error_msg:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": error_msg, "target_item_id": target_item_id}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

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

    if status == "success" and "plan" in result:
        new_plan = result["plan"]
        updated_latest = _build_updated_plan_list(state.get("latest_plan_result", []), plan_id, new_plan)
        update["latest_plan_result"] = updated_latest

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

@tool(args_schema=AdjustAndExecutePlanItemInput)
async def adjust_and_execute_plan_item(
    plan_id: str,
    target_item_id: str,
    new_item_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config_runnable: RunnableConfig,
    book_commutes_policy: Literal["first_only", "all"] = "first_only",
) -> Command:
    """
    替换行程中的指定条目并立刻自动执行新的方案。此工具专用于 fixup_agent 阶段，一次性完成替换与重试执行。
    """
    from typing import Any
    config = get_config()
    LoggerManager.setup(config)
    tool_budget_secs = float(getattr(config, "TOOL_MAX_RUNTIME_SECS", 3.0))
    started_at = time.perf_counter()
    
    logger.info(f"phase=adjust_and_execute_plan_item | plan_id={plan_id} | target={target_item_id} | new={new_item_id}")

    rejected_result = _validate_active_fixup_target(plan_id, target_item_id, state)
    if rejected_result is not None:
        logger.warning(
            "phase=adjust_and_execute_plan_item | action=reject_out_of_scope_fixup "
            f"| plan_id={plan_id} | target={target_item_id} "
            f"| expected_plan_id={rejected_result.get('expected_plan_id')} "
            f"| expected_target_item_id={rejected_result.get('expected_target_item_id')}"
        )
        return Command(update={
            "current_step": "needs_fixup",
            "active_agent": "fixup_agent",
            "confirmation": state.get("confirmation") if isinstance(state, dict) else None,
            "messages": [
                ToolMessage(
                    content=json.dumps(rejected_result, ensure_ascii=False),
                    tool_call_id=tool_call_id,
                )
            ],
        })

    # Step 1: Adjust Plan
    status, result, error_msg = _do_adjust_plan_item(
        plan_id, target_item_id, new_item_id, state, config, config_runnable
    )
    
    if error_msg:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": error_msg, "target_item_id": target_item_id}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })
        
    if status != "success" or "plan" not in result:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({
                "tool": "adjust_and_execute_plan_item",
                "status": status,
                "result": result,
            }, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

    new_plan = result["plan"]

    # Merge state locally for execute
    merged_state = dict(state)
    merged_state["plan_option"] = new_plan
    
    updated_latest = _build_updated_plan_list(state.get("latest_plan_result", []), plan_id, new_plan)
    merged_state["latest_plan_result"] = updated_latest

    itinerary = state.get("itinerary", [])
    if isinstance(itinerary, list):
        updated_itinerary = []
        for p in itinerary:
            if isinstance(p, dict) and p.get("plan_id") == plan_id:
                updated_itinerary.append(new_plan)
            else:
                updated_itinerary.append(p)
        merged_state["itinerary"] = updated_itinerary

    # Step 2: Execute
    exec_status, exec_result, update_dict = await _do_execute_itinerary(
        plan_id, new_plan, merged_state, config, book_commutes_policy, tool_budget_secs, started_at
    )
    
    execute_message = ToolMessage(
        content=json.dumps(
            {"tool": "adjust_and_execute_plan_item", "status": exec_status, "result": exec_result},
            ensure_ascii=False,
        ),
        tool_call_id=tool_call_id,
    )
    
    update_dict = _build_adjust_execute_update(
        exec_update=update_dict,
        exec_status=exec_status,
        execute_message=execute_message,
        new_plan=new_plan,
        updated_latest=updated_latest,
        updated_itinerary=updated_itinerary if isinstance(itinerary, list) else None,
    )
    return Command(update=update_dict)
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

    execution_report = state.get("execution_report", {}) if isinstance(state, dict) else {}
    execution_summary = (
        execution_report.get("execution_summary")
        if isinstance(execution_report, dict)
        else None
    )
    execution_items = (
        execution_summary.get("items")
        if isinstance(execution_summary, dict)
        else None
    )
    executed_ids: set[str] = set()
    if isinstance(execution_items, list):
        for item in execution_items:
            if not isinstance(item, dict):
                continue
            if item.get("reserved") is not True:
                continue
            item_id_val = item.get("item_id")
            if isinstance(item_id_val, str) and item_id_val:
                executed_ids.add(item_id_val)
            if item.get("replaced"):
                new_item_id_val = item.get("new_item_id")
                if isinstance(new_item_id_val, str) and new_item_id_val:
                    executed_ids.add(new_item_id_val)

    if target_item_id in executed_ids:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "error": "该项目已成功预订/执行，禁止替换；如需变更请重新规划新方案再执行",
                                "target_item_id": target_item_id,
                            },
                            ensure_ascii=False,
                        ),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

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
