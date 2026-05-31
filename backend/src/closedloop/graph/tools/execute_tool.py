import asyncio
import time
from typing import Annotated, Literal

import json

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.execution.mock_executor import (
    iter_events,
    peek_pending_confirmation,
    start_execution,
    submit_decision,
)
from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
from closedloop.graph.policies import parse_target_start_time


class ExecuteItineraryInput(BaseModel):
    """用于执行（预订）行程的结构化输入。"""

    plan_id: str = Field(..., description="要执行的行程方案ID，如 'plan_1'")
    book_commutes_policy: Literal["first_only", "all"] = Field(
        default="first_only",
        description="通勤预订策略。'first_only' 表示只预约出发地到第一目的地的车，剩下的询问；'all' 表示一次性预约行程中所有的车程（适用于偏向J型、计划性强的用户）。",
    )


def _add_minutes_to_hhmm(hhmm: str, mins: int) -> str:
    """辅助函数：将分钟数加到 HH:MM 时间上"""
    try:
        h, m = map(int, hhmm.split(":"))
        total = h * 60 + m + mins
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        return hhmm


@tool(args_schema=ExecuteItineraryInput)
async def execute_itinerary(
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
    hitl_max_wait_secs = float(getattr(config, "HITL_RESUME_MAX_WAIT_SECS", 3.0))
    tool_budget_secs = float(getattr(config, "TOOL_MAX_RUNTIME_SECS", 3.0))
    started_at = time.perf_counter()

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
        # 提取时间基准
        constraints = state.get("constraints", {})
        time_period = constraints.get("time_period", "14:00")
        current_time = parse_target_start_time(time_period)

        # 开始组装 ExecuteRequest 与前端展示信息
        steps = target_plan.get("steps", [])
        execute_steps = []
        booked_items = []
        commute_status = []
        item_name_map: dict[str, str] = {}

        is_first_commute = True

        for step in steps:
            item = step.get("item", {})
            item_type = item.get("type")
            item_id = item.get("id")
            name = item.get("name")
            duration_minutes = int(step.get("duration_minutes", 60))
            if isinstance(item_id, str) and isinstance(name, str) and item_id:
                item_name_map[item_id] = name

            start_time = current_time
            end_time = _add_minutes_to_hhmm(start_time, duration_minutes)
            
            # 安全校验：如果 time 不是 string，就转成 string 兜底，防止 Pydantic 报错
            if not isinstance(start_time, str):
                start_time = str(start_time)
            if not isinstance(end_time, str):
                end_time = str(end_time)

            current_time = end_time  # 步进时间

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
                        execute_steps.append(ExecuteStep(
                            item_id=item_id, item_type=item_type,
                            start_time=start_time, end_time=end_time, commute_mode=commute_mode
                        ))
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
                        execute_steps.append(ExecuteStep(
                            item_id=item_id, item_type=item_type,
                            start_time=start_time, end_time=end_time, commute_mode=commute_mode
                        ))
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
                execute_steps.append(ExecuteStep(
                    item_id=item_id, item_type=item_type,
                    start_time=start_time, end_time=end_time, commute_mode=None,
                    backup_candidates=item.get("backup_candidates"),
                    replacement_policy=item.get("replacement_policy", "equivalent_only"),
                    user_touched=item.get("user_touched", False)
                ))

        # 调用后端核心逻辑启动执行
        execute_request = ExecuteRequest(plan_id=plan_id, steps=execute_steps)
        execution_id = await start_execution(execute_request)

        execution_summary: dict = {
            "execution_id": execution_id,
            "replacements": [],
            "failures": [],
            "items": [],
        }
        decided_item_ids: set[str] = set()
        status = "success"
        events_gen = iter_events(execution_id)
        waiting_progress = False
        waiting_item_id: str | None = None
        waiting_backup_id: str | None = None
        forced_event: dict | None = None

        pending = await peek_pending_confirmation(execution_id)
        if isinstance(pending, dict) and pending.get("item_id") and pending.get("backup_id"):
            pending_item_id = str(pending.get("item_id") or "")
            action_name = "execute_itinerary_replacement"
            payload = {
                "action_requests": [
                    {
                        "name": action_name,
                        "arguments": {
                            "execution_id": execution_id,
                            "item_id": pending.get("item_id"),
                            "backup_id": pending.get("backup_id"),
                        },
                        "description": pending.get("violation_reason")
                        or "执行遇到备选替换，需要用户确认",
                    }
                ],
                "review_configs": [
                    {
                        "action_name": action_name,
                        "allowed_decisions": pending.get("allowed_decisions")
                        or ["approve", "reject"],
                    }
                ],
            }

            logger.info(
                f"phase=execute_itinerary | action=hitl_interrupt_emit | execution_id={execution_id} | item_id={pending.get('item_id')} | backup_id={pending.get('backup_id')}"
            )
            resume_value = interrupt(payload)
            decisions = []
            if isinstance(resume_value, dict):
                decisions = resume_value.get("decisions") or []
            decision = (
                decisions[0]
                if isinstance(decisions, list) and decisions
                else {"type": "reject"}
            )
            logger.info(
                f"phase=execute_itinerary | action=hitl_resume_received | execution_id={execution_id} | decision={decision}"
            )

            ok = await submit_decision(
                execution_id=execution_id,
                item_id=str(pending.get("item_id") or ""),
                decision=decision,
            )
            if not ok:
                logger.error(
                    f"phase=execute_itinerary | action=hitl_submit_decision_failed | execution_id={execution_id} | item_id={pending.get('item_id')}"
                )
                raise RuntimeError("submit_decision_failed")

            waiting_progress = True
            waiting_item_id = pending_item_id
            waiting_backup_id = str(pending.get("backup_id") or "")
            decided_item_ids.add(pending_item_id)

        try:
            while True:
                try:
                    if forced_event is not None:
                        event = forced_event
                        forced_event = None
                    else:
                        remaining_secs = tool_budget_secs - (time.perf_counter() - started_at)
                        if remaining_secs <= 0:
                            raise asyncio.TimeoutError()

                        wait_timeout = remaining_secs
                        resume_timeout_mode = False
                        if waiting_progress:
                            wait_timeout = min(wait_timeout, hitl_max_wait_secs)
                            resume_timeout_mode = remaining_secs >= hitl_max_wait_secs

                        event = await asyncio.wait_for(anext(events_gen), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    grace_secs = 0.05
                    try:
                        grace_event = await asyncio.wait_for(anext(events_gen), timeout=grace_secs)
                        if isinstance(grace_event, dict):
                            forced_event = grace_event
                            continue
                    except Exception:
                        pass
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    if waiting_progress and resume_timeout_mode:
                        logger.error(
                            f"phase=execute_itinerary | action=hitl_resume_timeout | execution_id={execution_id} | item_id={waiting_item_id} | backup_id={waiting_backup_id}"
                        )
                        result_message = f"执行超时：用户已提交确认，但 {hitl_max_wait_secs} 秒内未继续推进。"
                        code = "RESUME_TIMEOUT"
                    else:
                        logger.error(
                            f"phase=execute_itinerary | action=tool_timeout | execution_id={execution_id} | elapsed_ms={elapsed_ms}"
                        )
                        result_message = f"执行超时：{tool_budget_secs} 秒内未完成。本次执行将由系统重试。"
                        code = "TOOL_TIMEOUT"
                    result = {
                        "plan_id": plan_id,
                        "execution_id": execution_id,
                        "booked_items": booked_items,
                        "commute_status": commute_status,
                        "execution_summary": execution_summary,
                        "code": code,
                        "message": result_message,
                    }
                    confirmation = {
                        "status": "timeout",
                        "execution_id": execution_id,
                        "code": code,
                        "message": result_message,
                        "execution_summary": execution_summary,
                    }
                    status = "timeout"
                    break

                waiting_progress = False
                waiting_item_id = None
                waiting_backup_id = None

                if not isinstance(event, dict):
                    continue
                if event.get("type") == "item_update":
                    data = event.get("data") or {}
                    if not isinstance(data, dict):
                        continue

                    if data.get("phase") == "pending_user_confirmation":
                        item_id = str(data.get("item_id") or "")
                        if item_id and item_id in decided_item_ids:
                            logger.info(
                                f"phase=execute_itinerary | action=hitl_pending_skipped_already_decided | execution_id={execution_id} | item_id={item_id} | backup_id={data.get('backup_id')}"
                            )
                            waiting_progress = True
                            waiting_item_id = item_id
                            waiting_backup_id = str(data.get("backup_id") or "")
                            continue

                        action_name = "execute_itinerary_replacement"
                        payload = {
                            "action_requests": [
                                {
                                    "name": action_name,
                                    "arguments": {
                                        "execution_id": execution_id,
                                        "item_id": data.get("item_id"),
                                        "backup_id": data.get("backup_id"),
                                    },
                                    "description": data.get("message") or "执行遇到备选替换，需要用户确认",
                                }
                            ],
                            "review_configs": [
                                {
                                    "action_name": action_name,
                                    "allowed_decisions": data.get("allowed_decisions") or ["approve", "reject"],
                                }
                            ],
                        }

                        logger.info(
                            f"phase=execute_itinerary | action=hitl_interrupt_emit | execution_id={execution_id} | item_id={data.get('item_id')} | backup_id={data.get('backup_id')}"
                        )
                        resume_value = interrupt(payload)
                        decisions = []
                        if isinstance(resume_value, dict):
                            decisions = resume_value.get("decisions") or []
                        decision = decisions[0] if isinstance(decisions, list) and decisions else {"type": "reject"}
                        logger.info(
                            f"phase=execute_itinerary | action=hitl_resume_received | execution_id={execution_id} | decision={decision}"
                        )

                        ok = await submit_decision(
                            execution_id=execution_id,
                            item_id=str(data.get("item_id") or ""),
                            decision=decision,
                        )
                        if not ok:
                            logger.error(
                                f"phase=execute_itinerary | action=hitl_submit_decision_failed | execution_id={execution_id} | item_id={data.get('item_id')} | backup_id={data.get('backup_id')}"
                            )
                            raise RuntimeError(
                                f"submit_decision_failed execution_id={execution_id} item_id={data.get('item_id')}"
                            )
                        logger.info(
                            f"phase=execute_itinerary | action=hitl_submit_decision_ok | execution_id={execution_id} | item_id={data.get('item_id')} | backup_id={data.get('backup_id')}"
                        )
                        waiting_progress = True
                        waiting_item_id = item_id
                        waiting_backup_id = str(data.get("backup_id") or "")
                        if item_id:
                            decided_item_ids.add(item_id)
                        continue

                    if data.get("phase") == "done":
                        execution_summary["items"].append(data)
                        if data.get("replaced"):
                            execution_summary["replacements"].append(
                                {
                                    "original_id": data.get("item_id"),
                                    "original_name": item_name_map.get(str(data.get("item_id") or ""), ""),
                                    "new_item_id": data.get("new_item_id"),
                                    "new_item_name": data.get("new_item_name"),
                                    "item_type": data.get("item_type"),
                                }
                            )
                        if data.get("reserved") is False:
                            execution_summary["failures"].append(
                                {
                                    "item_id": data.get("item_id"),
                                    "item_name": item_name_map.get(str(data.get("item_id") or ""), ""),
                                    "item_type": data.get("item_type"),
                                }
                            )
                    continue

                if event.get("type") == "done":
                    break
        finally:
            if hasattr(events_gen, "aclose"):
                try:
                    await events_gen.aclose()
                except Exception:
                    pass

        if status != "timeout":
            replacements_count = len(execution_summary.get("replacements") or [])
            failures_count = len(execution_summary.get("failures") or [])
            result_message = f"执行完成：已替换 {replacements_count} 项，失败 {failures_count} 项。"

            result = {
                "plan_id": plan_id,
                "execution_id": execution_id,
                "booked_items": booked_items,
                "commute_status": commute_status,
                "execution_summary": execution_summary,
                "message": result_message,
            }
            confirmation = {
                "status": "executed",
                "execution_id": execution_id,
                "message": result_message,
                "summary": {
                    "replacements": replacements_count,
                    "failures": failures_count,
                },
                "execution_summary": execution_summary,
            }
            status = "success"
            logger.info(
                f"phase=execute_itinerary | result=success | booked_items={len(booked_items)}"
            )

    execute_message = ToolMessage(
        content=json.dumps(
            {"tool": "execute_itinerary", "status": status, "result": result},
            ensure_ascii=False,
        ),
        tool_call_id=tool_call_id,
    )

    next_step = "confirm_trip" if status == "success" else "execute_timeout"
    execution_report = {
        "status": status,
        "execution_id": execution_id,
        "code": (result or {}).get("code") if isinstance(result, dict) else None,
        "message": (result or {}).get("message") if isinstance(result, dict) else None,
        "execution_summary": execution_summary,
    }
    update = {
        "confirmation": confirmation if status in ("success", "timeout") else result,
        "execution_report": execution_report,
        "current_step": next_step,
        "messages": [execute_message],
    }

    return Command(update=update)
