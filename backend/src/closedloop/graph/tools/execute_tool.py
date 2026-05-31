

import asyncio
import time
import os
from typing import Annotated, Literal, Any
from contextlib import suppress

import json

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import REPO_ROOT_DIR, get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.execution.mock_executor import (
    iter_events,
    start_execution,
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


def _resolve_rw_dir(config) -> str:
    data = getattr(config, "data", None)
    rw_dir = getattr(data, "MOCK_DB_RW_DIR", "") if data is not None else ""
    if not isinstance(rw_dir, str) or not rw_dir:
        rw_dir = "mock_data/runtime"
    if os.path.isabs(rw_dir):
        return os.path.abspath(rw_dir)
    return os.path.abspath(os.path.join(REPO_ROOT_DIR, rw_dir))


def _snapshot_runtime_jsons(rw_dir: str, filenames: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name in filenames:
        path = os.path.join(rw_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            snapshot[name] = json.load(f)
    return snapshot


def _restore_runtime_jsons(rw_dir: str, snapshot: dict[str, Any]) -> None:
    for name, content in (snapshot or {}).items():
        path = os.path.join(rw_dir, name)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)


def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v))
    except Exception:
        return 0.0


def _read_list_json(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []


def _lookup_item_cost(
    repo_dir: str,
    item_type: str,
    item_id: str,
) -> float:
    try:
        if item_type == "restaurant":
            restaurants = _read_list_json(os.path.join(repo_dir, "restaurants.json"))
            for r in restaurants:
                for c in (r.get("combos") or []):
                    if c.get("combo_id") == item_id:
                        return _safe_float(c.get("combo_price") or c.get("cost") or c.get("price") or 0.0)
            return 0.0
        if item_type == "activity":
            activities = _read_list_json(os.path.join(repo_dir, "activities.json"))
            for a in activities:
                for p in (a.get("packages") or []):
                    if p.get("package_id") == item_id:
                        return _safe_float(p.get("cost") or p.get("price") or 0.0)
            return 0.0
        if item_type == "gift_shop":
            add_ons = _read_list_json(os.path.join(repo_dir, "add_ons.json"))
            for s in add_ons:
                for g in (s.get("gifts") or []):
                    if g.get("gift_id") == item_id:
                        return _safe_float(g.get("price") or g.get("gift_price") or g.get("cost") or 0.0)
            return 0.0
        return 0.0
    except Exception:
        return 0.0


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

async def _do_execute_itinerary(
    plan_id: str,
    target_plan: dict,
    state: dict,
    config: Any,
    book_commutes_policy: str,
    tool_budget_secs: float,
    started_at: float,
) -> tuple[str, dict, dict]:
    """提取的核心执行逻辑。返回 (status, result, update_dict)。"""
    # 提取时间基准
    constraints = state.get("constraints", {})
    time_period = constraints.get("time_period", "14:00")
    current_time = parse_target_start_time(time_period)

    for attempt in range(2):
        # 每次重试时，需要重新初始化相关的结构
        steps = target_plan.get("steps", [])
        previous_report = state.get("execution_report") if isinstance(state, dict) else None
        previous_summary = (
            previous_report.get("execution_summary")
            if isinstance(previous_report, dict)
            else None
        )
        previous_items = (
            previous_summary.get("items")
            if isinstance(previous_summary, dict)
            else None
        )
        executed_skip_ids: set[str] = set()
        if isinstance(previous_items, list):
            for item in previous_items:
                if not isinstance(item, dict):
                    continue
                if item.get("reserved") is not True:
                    continue
                item_id_val = item.get("item_id")
                if isinstance(item_id_val, str) and item_id_val:
                    executed_skip_ids.add(item_id_val)
                new_item_id_val = item.get("new_item_id")
                if item.get("replaced") and isinstance(new_item_id_val, str) and new_item_id_val:
                    executed_skip_ids.add(new_item_id_val)
                    
        execute_steps = []
        booked_items = []
        commute_status = []
        item_name_map: dict[str, str] = {}

        is_first_commute = True
        
        loop_current_time = current_time

        for step in steps:
            item = step.get("item", {})
            item_type = item.get("type")
            item_id = item.get("id")
            name = item.get("name")
            duration_minutes = int(step.get("duration_minutes", 60))
            if isinstance(item_id, str) and isinstance(name, str) and item_id:
                item_name_map[item_id] = name

            start_time = loop_current_time
            end_time = _add_minutes_to_hhmm(start_time, duration_minutes)
            
            # 安全校验：如果 time 不是 string，就转成 string 兜底，防止 Pydantic 报错
            if not isinstance(start_time, str):
                start_time = str(start_time)
            if not isinstance(end_time, str):
                end_time = str(end_time)

            loop_current_time = end_time  # 步进时间

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
                if isinstance(item_id, str) and item_id and item_id in executed_skip_ids:
                    booked_items.append(
                        {
                            "id": item_id,
                            "name": name,
                            "type": item_type,
                            "status": "skipped",
                            "message": "该项目已执行过，本次跳过",
                        }
                    )
                    continue
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

        rw_dir = _resolve_rw_dir(config)
        runtime_snapshot = _snapshot_runtime_jsons(
            rw_dir,
            ["restaurants.json", "activities.json", "add_ons.json", "reservations.json"],
        )

        plan_cost_by_id: dict[str, float] = {}
        plan_type_by_id: dict[str, str] = {}
        expected_step_ids: list[str] = []
        for step in steps:
            item = step.get("item", {}) if isinstance(step, dict) else {}
            item_type = item.get("type")
            if item_type == "commute":
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                continue
            expected_step_ids.append(item_id)
            plan_cost_by_id[item_id] = _safe_float(item.get("cost") or item.get("gift_price") or 0.0)
            if isinstance(item_type, str) and item_type:
                plan_type_by_id[item_id] = item_type

        expected_total_cost = _safe_float(target_plan.get("total_cost"))

        execution_summary: dict = {
            "execution_id": None,
            "replacements": [],
            "failures": [],
            "items": [],
        }
        if isinstance(previous_summary, dict):
            if isinstance(previous_summary.get("replacements"), list):
                execution_summary["replacements"].extend(previous_summary.get("replacements") or [])
            if isinstance(previous_summary.get("failures"), list):
                execution_summary["failures"].extend(previous_summary.get("failures") or [])
            if isinstance(previous_summary.get("items"), list):
                execution_summary["items"].extend(previous_summary.get("items") or [])

        execution_id: str | None = None
        status = "success"
        confirmation: dict | None = None
        result: dict | None = None

        if execute_steps:
            execute_request = ExecuteRequest(plan_id=plan_id, steps=execute_steps)
            execution_id = await start_execution(execute_request)
            execution_summary["execution_id"] = execution_id

            events_gen = iter_events(execution_id)
            try:
                while True:
                    remaining_secs = tool_budget_secs - (time.perf_counter() - started_at)
                    if remaining_secs <= 0:
                        raise asyncio.TimeoutError()

                    event = await asyncio.wait_for(anext(events_gen), timeout=remaining_secs)
                    if not isinstance(event, dict):
                        continue

                    if event.get("type") == "item_update":
                        data = event.get("data") or {}
                        if not isinstance(data, dict):
                            continue

                        if data.get("phase") == "pending_user_confirmation":
                            backup_candidates = data.get("backup_candidates")
                            fixup = {
                                "plan_id": plan_id,
                                "target_item_id": data.get("item_id"),
                                "reason": data.get("violation_reason") or data.get("message") or "需要你确认备选替换",
                                "backup_candidates": backup_candidates if isinstance(backup_candidates, list) else [],
                            }
                            confirmation = {
                                "status": "needs_fixup",
                                "execution_id": execution_id,
                                "fixup": fixup,
                            }
                            result = {
                                "plan_id": plan_id,
                                "execution_id": execution_id,
                                "booked_items": booked_items,
                                "commute_status": commute_status,
                                "execution_summary": execution_summary,
                                "code": "NEEDS_FIXUP",
                                "message": "执行遇到备选替换，需要用户选择候选1/2或搜索其他备选。",
                            }
                            status = "needs_fixup"
                            break

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
            except asyncio.TimeoutError:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                logger.error(
                    f"phase=execute_itinerary | action=tool_timeout | execution_id={execution_id} | elapsed_ms={elapsed_ms}"
                )
                result = {
                    "plan_id": plan_id,
                    "execution_id": execution_id,
                    "booked_items": booked_items,
                    "commute_status": commute_status,
                    "execution_summary": execution_summary,
                    "code": "TIMEOUT",
                    "message": f"执行超时（限制 {tool_budget_secs}s），请检查网络或系统负载。",
                }
                confirmation = {
                    "status": "timeout",
                    "execution_id": execution_id,
                    "code": "TIMEOUT",
                    "message": "执行超时",
                    "execution_summary": execution_summary,
                }
                status = "timeout"

        if status == "success":
            replacement_map: dict[str, str] = {}
            for r in execution_summary.get("replacements") or []:
                if not isinstance(r, dict):
                    continue
                o = r.get("original_id")
                n = r.get("new_item_id")
                if isinstance(o, str) and o and isinstance(n, str) and n:
                    replacement_map[o] = n

            expected_mapped_ids: list[str] = []
            mapped_type_by_id: dict[str, str] = dict(plan_type_by_id)
            for x in expected_step_ids:
                if not isinstance(x, str) or not x:
                    continue
                mapped = replacement_map.get(x, x)
                expected_mapped_ids.append(mapped)
                if mapped != x and x in plan_type_by_id:
                    mapped_type_by_id[mapped] = plan_type_by_id[x]

            executed_step_ids: list[str] = []
            for item in execution_summary.get("items") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("reserved") is not True:
                    continue
                if item.get("item_type") == "commute":
                    continue
                item_id_val = item.get("new_item_id") if item.get("replaced") else item.get("item_id")
                if isinstance(item_id_val, str) and item_id_val:
                    executed_step_ids.append(item_id_val)

            def _cost_for_id(_id: str) -> float:
                v = plan_cost_by_id.get(_id)
                if isinstance(v, (int, float)) and float(v) > 0:
                    return float(v)
                t = mapped_type_by_id.get(_id) or ""
                if not isinstance(t, str) or not t:
                    return 0.0
                return _lookup_item_cost(rw_dir, t, _id)

            expected_total_cost_mapped = sum(_cost_for_id(x) for x in expected_mapped_ids)
            executed_total_cost = sum(_cost_for_id(x) for x in executed_step_ids)
            expected_set = {x for x in expected_mapped_ids if isinstance(x, str) and x}
            executed_set = {x for x in executed_step_ids if isinstance(x, str) and x}

            failures_count = len(execution_summary.get("failures") or [])
            missing_ids = list(expected_set - executed_set)
            missing_count = len(missing_ids)

            if failures_count == 0 and expected_set != executed_set:
                if attempt == 0:
                    logger.warning("phase=execute_itinerary | action=consistency_check_failed | msg=retrying")
                    _restore_runtime_jsons(rw_dir, runtime_snapshot)
                    continue
                else:
                    logger.error("phase=execute_itinerary | action=consistency_check_failed | msg=retry_exhausted")
                    # Fallthrough to needs_fixup logic if it fails twice

            if failures_count > 0 or expected_set != executed_set:
                target_item_id = None
                failures = execution_summary.get("failures") or []
                if isinstance(failures, list) and failures:
                    first_failure = failures[0] if isinstance(failures[0], dict) else {}
                    if isinstance(first_failure, dict):
                        target_item_id = first_failure.get("item_id")
                if (not isinstance(target_item_id, str) or not target_item_id) and missing_ids:
                    target_item_id = missing_ids[0]

                logger.info(
                    "phase=execute_itinerary | action=enter_fixup_after_execution "
                    f"| plan_id={plan_id} | failures_count={failures_count} | missing_count={missing_count} | target_item_id={target_item_id}"
                )

                fixup = {
                    "plan_id": plan_id,
                    "target_item_id": target_item_id,
                    "reason": "存在未成功预订项目，需要补齐后再进入付款对账",
                    "backup_candidates": [],
                }
                confirmation = {
                    "status": "needs_fixup",
                    "execution_id": execution_id,
                    "fixup": fixup,
                }
                result = {
                    "plan_id": plan_id,
                    "execution_id": execution_id,
                    "booked_items": booked_items,
                    "commute_status": commute_status,
                    "execution_summary": execution_summary,
                    "code": "NEEDS_FIXUP",
                    "message": "执行未完全成功：需要补齐替换后再继续执行。",
                }
                status = "needs_fixup"
            else:
                plan_total_cost = expected_total_cost
                overpay = (executed_total_cost - plan_total_cost) > 1e-6
                logger.info(
                    "phase=execute_itinerary | action=consistency_check "
                    f"| plan_id={plan_id} "
                    f"| plan_total_cost={plan_total_cost} "
                    f"| executed_cost={executed_total_cost} "
                    f"| overpay={overpay} "
                    f"| expected_steps={len(expected_set)} "
                    f"| executed_steps={len(executed_set)}"
                )

                if overpay:
                    _restore_runtime_jsons(rw_dir, runtime_snapshot)
                    message = "执行一致性校验失败：已回滚本次执行，并将由系统自动重试。"
                    result = {
                        "plan_id": plan_id,
                        "execution_id": execution_id,
                        "booked_items": booked_items,
                        "commute_status": commute_status,
                        "execution_summary": execution_summary,
                        "code": "EXECUTION_INCONSISTENT_NEEDS_RETRY",
                        "message": message,
                    }
                    confirmation = {
                        "status": "failed",
                        "execution_id": execution_id,
                        "code": "EXECUTION_INCONSISTENT_NEEDS_RETRY",
                        "message": message,
                        "execution_summary": execution_summary,
                    }
                    status = "failed"
                else:
                    result_message = "执行完成：失败 0 项。"
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
                            "failures": 0,
                        },
                        "execution_summary": execution_summary,
                    }
                    logger.info(
                        f"phase=execute_itinerary | result=success | booked_items={len(booked_items)}"
                    )
        
        break # Exit retry loop if we reached the end

    update_dict = {
        "current_step": "execute_itinerary",
        "confirmation": confirmation,
        "execution_report": {
            "status": status,
            "execution_id": execution_id,
            "execution_summary": execution_summary,
            "last_updated_at": time.time(),
        },
    }
    if status == "needs_fixup":
        update_dict["active_agent"] = "fixup_agent"
        update_dict["current_step"] = "needs_fixup"
    
    return status, result, update_dict

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
    tool_budget_secs = float(getattr(config, "TOOL_MAX_RUNTIME_SECS", 3.0))
    started_at = time.perf_counter()

    logger.info(
        f"phase=execute_itinerary | input=plan_id={plan_id} book_commutes_policy={book_commutes_policy}"
    )

    # 优先使用 plan_option 作为可信源，兜底使用 latest_plan_result
    target_plan = None
    plan_option = state.get("plan_option")
    if isinstance(plan_option, dict) and plan_option.get("plan_id") == plan_id:
        target_plan = plan_option

    if not target_plan:
        latest_plan_result = state.get("latest_plan_result", [])
        plans = latest_plan_result if isinstance(latest_plan_result, list) else []
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
        update_dict = {"current_step": "execute_itinerary"}
    else:
        status, result, update_dict = await _do_execute_itinerary(
            plan_id, target_plan, state, config, book_commutes_policy, tool_budget_secs, started_at
        )

    execute_message = ToolMessage(
        content=json.dumps(
            {"tool": "execute_itinerary", "status": status, "result": result},
            ensure_ascii=False,
        ),
        tool_call_id=tool_call_id,
    )
    
    update_dict["messages"] = [execute_message]

    return Command(update=update_dict)
