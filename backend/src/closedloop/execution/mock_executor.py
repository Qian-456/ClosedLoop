from __future__ import annotations

import asyncio
import json
import os
import random
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from closedloop.core.config import REPO_ROOT_DIR, get_config
from closedloop.core.logger import logger
from closedloop.contracts.execution import ExecuteEvent, ExecuteRequest, ExecuteStep
from closedloop.utils.forced_out_of_stock import parse_forced_out_of_stock_ids


_activities_lock = asyncio.Lock()
_add_ons_lock = asyncio.Lock()
_restaurants_lock = asyncio.Lock()
_reservations_lock = asyncio.Lock()


@dataclass(frozen=True)
class _ExecutionContext:
    request: ExecuteRequest
    queue: asyncio.Queue[dict[str, Any]]
    control: dict[str, Any]
    execution_key: str
    loop_id: int


_executions: dict[str, _ExecutionContext] = {}
_execution_keys: dict[str, str] = {}
_payment_commands: dict[str, ExecuteRequest] = {}
_executions_guard = asyncio.Lock()


def _execution_key_from_request(request: ExecuteRequest) -> str:
    try:
        dumped = request.model_dump()
    except Exception:
        dumped = {"plan_id": getattr(request, "plan_id", ""), "steps": getattr(request, "steps", [])}
    return json.dumps(dumped, ensure_ascii=False, sort_keys=True)

def _resolve_dir(v: str) -> str:
    if not v:
        return ""
    if os.path.isabs(v):
        return os.path.abspath(v)
    return os.path.abspath(os.path.join(REPO_ROOT_DIR, v))


def _is_dir_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        base = os.path.join(path, f".write_test_{uuid.uuid4().hex}")
        tmp = f"{base}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("ok")
        os.replace(tmp, base)
        os.remove(base)
        return True
    except Exception:
        return False


def _seed_mock_db_files(src_dir: str, dst_dir: str) -> None:
    filenames = ["restaurants.json", "activities.json", "add_ons.json", "reservations.json"]
    for name in filenames:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        if os.path.exists(dst):
            continue
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)


def _resolve_repo_dir() -> str:
    config = get_config()
    data = getattr(config, "data", None)

    repo_dir = _resolve_dir(getattr(data, "MOCK_DB_REPO_DIR", "") or "")
    rw_dir = _resolve_dir(getattr(data, "MOCK_DB_RW_DIR", "") or "")

    if rw_dir:
        if _is_dir_writable(rw_dir):
            if repo_dir and os.path.isdir(repo_dir):
                _seed_mock_db_files(repo_dir, rw_dir)
            return rw_dir

    if repo_dir and _is_dir_writable(repo_dir):
        return repo_dir

    tmp_dir = os.path.abspath(os.path.join(tempfile.gettempdir(), "closedloop_mock_db"))
    os.makedirs(tmp_dir, exist_ok=True)
    if repo_dir and os.path.isdir(repo_dir):
        _seed_mock_db_files(repo_dir, tmp_dir)
    return tmp_dir


def _read_list_json(repo_dir: str, filename: str) -> list[dict[str, Any]]:
    path = os.path.join(repo_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"mock_db file must be a list: {path}")
    return data


def _atomic_write_json(path: str, data: Any) -> None:
    tmp_path = f"{path}.tmp_{uuid.uuid4().hex}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _parse_hhmm_to_minutes(v: str) -> int:
    # 防止因为 float(13.0) 被强转为 "13.0" 从而无法按 ":" 分割的问题
    if not v or ":" not in str(v):
        try:
            return int(float(v) * 60)
        except Exception:
            return 0
    h, m = str(v).strip().split(":")
    return int(h) * 60 + int(m)


def _minutes_to_hhmm(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _gift_delivery_time(start_time: str) -> str:
    return _minutes_to_hhmm(_parse_hhmm_to_minutes(start_time) - 10)


def _find_combo(restaurants: list[dict[str, Any]], combo_id: str) -> dict[str, Any] | None:
    for r in restaurants:
        for c in r.get("combos", []) or []:
            if c.get("combo_id") == combo_id:
                return c
    return None


def _find_combo_with_restaurant(
    restaurants: list[dict[str, Any]], combo_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for r in restaurants:
        for c in r.get("combos", []) or []:
            if c.get("combo_id") == combo_id:
                return c, r
    return None, None


def _find_package(
    activities: list[dict[str, Any]], package_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for v in activities:
        for p in v.get("packages", []) or []:
            if p.get("package_id") == package_id:
                return p, v
    return None, None


def _find_gift(add_ons: list[dict[str, Any]], gift_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for s in add_ons:
        for g in s.get("gifts", []) or []:
            if g.get("gift_id") == gift_id:
                return g, s
    return None, None


def _pick_time_slot(
    record: dict[str, Any], start_time: str
) -> dict[str, Any] | None:
    slots = record.get("time_slots", []) or []
    if not slots:
        return None

    t = _parse_hhmm_to_minutes(start_time)
    for s in slots:
        try:
            lo = _parse_hhmm_to_minutes(str(s.get("start_time", "") or "0:00"))
            hi = _parse_hhmm_to_minutes(str(s.get("end_time", "") or "0:00"))
        except Exception:
            continue
        if lo <= t < hi:
            return s
    return slots[0]


def _forced_out_of_stock_ids() -> set[str]:
    config = get_config()
    data = getattr(config, "data", None)
    raw = getattr(data, "FORCE_OUT_OF_STOCK_IDS", "") if data is not None else ""
    return parse_forced_out_of_stock_ids(raw or "")


def _reserve_capacity(
    reservations: list[dict[str, Any]],
    target_type: Literal["restaurant", "package"],
    target_id: str,
    start_time: str,
    *,
    commit: bool = True,
) -> tuple[bool, dict[str, Any] | None]:
    record = None
    for r in reservations:
        if r.get("target_type") == target_type and r.get("target_id") == target_id:
            record = r
            break
    if not record:
        return False, {"reason": "no_record"}
    slot = _pick_time_slot(record, start_time)
    if not slot:
        return False, {"reason": "no_time_slot"}
    if isinstance(slot.get("capacity_remaining"), int):
        before = int(slot["capacity_remaining"])
        if before <= 0:
            return False, {
                "reason": "out_of_stock",
                "slot_start_time": slot.get("start_time"),
                "slot_end_time": slot.get("end_time"),
                "capacity_remaining_before": before,
                "capacity_remaining_after": before,
            }
        after = before - 1
        if commit:
            slot["capacity_remaining"] = after
        return True, {
            "slot_start_time": slot.get("start_time"),
            "slot_end_time": slot.get("end_time"),
            "capacity_remaining_before": before,
            "capacity_remaining_after": after,
            "payment_gate": "committed" if commit else "pending",
        }
    return False, None


async def start_execution(request: ExecuteRequest) -> str:
    """创建执行会话并启动后台任务，返回 execution_id。"""

    execution_key = _execution_key_from_request(request)
    current_loop_id = id(asyncio.get_running_loop())
    async with _executions_guard:
        existing_id = _execution_keys.get(execution_key)
        if existing_id and existing_id in _executions:
            existing_ctx = _executions.get(existing_id)
            if existing_ctx is not None and existing_ctx.loop_id == current_loop_id:
                return existing_id

        execution_id = f"exe_{uuid.uuid4().hex}"
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        ctx = _ExecutionContext(
            request=request,
            queue=queue,
            control={"stop": False, "status": "ok", "stop_payload": None},
            execution_key=execution_key,
            loop_id=current_loop_id,
        )
        _executions[execution_id] = ctx
        _execution_keys[execution_key] = execution_id
        if getattr(request, "mode", "commit") == "preview":
            _payment_commands[execution_id] = request

    asyncio.create_task(_run_execution(execution_id, ctx))
    return execution_id


async def iter_events(execution_id: str) -> AsyncIterator[dict[str, Any]]:
    """按 SSE 需要顺序产出事件（以 dict 形式）。"""

    async with _executions_guard:
        ctx = _executions.get(execution_id)
    if not ctx:
        yield ExecuteEvent(type="done", data={"status": "not_found"}).model_dump()
        return

    done_seen = False
    try:
        while True:
            event = await ctx.queue.get()
            yield event
            if event.get("type") == "done":
                done_seen = True
                return
    finally:
        if done_seen:
            async with _executions_guard:
                removed = _executions.pop(execution_id, None)
                if removed is not None:
                    mapped = _execution_keys.get(removed.execution_key)
                    if mapped == execution_id:
                        _execution_keys.pop(removed.execution_key, None)


async def commit_execution_payment(execution_id: str, payment_password: str) -> dict[str, Any]:
    """校验 Mock 支付密码，并在支付成功后提交执行命令。"""

    logger.info(
        f"phase=execute_mock | action=mock_payment_verify | execution_id={execution_id} | password_length={len(payment_password or '')}"
    )
    if payment_password != "111111":
        logger.warning(
            f"phase=execute_mock | action=mock_payment_verify_failed | execution_id={execution_id}"
        )
        return {
            "execution_id": execution_id,
            "payment_status": "failed",
            "commit_status": "not_started",
            "message": "Mock 支付密码错误",
        }

    async with _executions_guard:
        preview_request = _payment_commands.get(execution_id)

    if preview_request is None:
        logger.warning(
            f"phase=execute_mock | action=mock_payment_command_missing | execution_id={execution_id}"
        )
        return {
            "execution_id": execution_id,
            "payment_status": "paid",
            "commit_status": "not_found",
            "message": "未找到待支付执行命令",
        }

    commit_request = ExecuteRequest(
        plan_id=preview_request.plan_id,
        steps=preview_request.steps,
        mode="commit",
    )
    commit_execution_id = await start_execution(commit_request)
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    async for event in iter_events(commit_execution_id):
        if not isinstance(event, dict):
            continue
        if event.get("type") != "item_update":
            continue
        data = event.get("data") or {}
        if not isinstance(data, dict):
            continue
        if data.get("phase") != "done":
            continue
        items.append(data)
        if data.get("reserved") is False:
            failures.append(data)

    commit_status = "failed" if failures else "success"
    if commit_status == "success":
        async with _executions_guard:
            _payment_commands.pop(execution_id, None)

    logger.info(
        f"phase=execute_mock | action=payment_commit_done | execution_id={execution_id} | commit_execution_id={commit_execution_id} | commit_status={commit_status} | failures={len(failures)}"
    )
    return {
        "execution_id": execution_id,
        "commit_execution_id": commit_execution_id,
        "payment_status": "paid",
        "commit_status": commit_status,
        "items": items,
        "failures": failures,
        "message": "Mock 执行已完成" if commit_status == "success" else "Mock 执行提交失败",
    }


async def _emit(ctx: _ExecutionContext, event: ExecuteEvent) -> None:
    await ctx.queue.put(event.model_dump())


def _checking_message(step: ExecuteStep) -> str:
    if step.item_type == "restaurant":
        return "正在读取当前餐厅套餐是否还有预约位置…"
    if step.item_type == "activity":
        return "正在读取当前活动是否还有票/库存…"
    if step.item_type == "gift_shop":
        return "正在读取当前礼物是否还有库存…"
    return "正在检查…"


def _reserving_message(step: ExecuteStep) -> str:
    if step.item_type == "restaurant":
        return "正在生成餐厅待支付预约命令…"
    if step.item_type == "activity":
        return "正在生成活动待支付购票命令…"
    if step.item_type == "gift_shop":
        return "正在生成礼物待支付配送命令…"
    return "正在生成执行命令…"


async def _check_and_reserve_one(execution_id: str, ctx: _ExecutionContext, step: ExecuteStep) -> None:
    if step.item_type == "commute":
        return
    if bool(ctx.control.get("stop")):
        return

    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": step.item_type,
                "phase": "checking",
                "message": _checking_message(step),
            },
        ),
    )

    config = get_config()
    sim_delay_max = float(getattr(config, "EXECUTION_SIM_DELAY_MAX_SECS", 0.02))
    check_delay = float(random.uniform(0.0, max(0.0, sim_delay_max)))
    t0 = time.perf_counter()
    await asyncio.sleep(check_delay)
    checked_ms = int((time.perf_counter() - t0) * 1000)

    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": step.item_type,
                "phase": "reserving",
                "message": _reserving_message(step),
                "checked_ms": checked_ms,
            },
        ),
    )

    reserve_delay = float(random.uniform(0.0, max(0.0, sim_delay_max)))
    t1 = time.perf_counter()
    await asyncio.sleep(reserve_delay)
    reserved_ms = int((time.perf_counter() - t1) * 1000)

    delivery_time = None
    reserved = False
    reserved_detail: dict[str, Any] | None = None
    replaced = False
    new_item_id = None
    new_item_name = None
    repo_dir = _resolve_repo_dir()
    forced_ids = _forced_out_of_stock_ids()
    commit_mode = getattr(ctx.request, "mode", "commit") == "commit"
    payment_gate = "committed" if commit_mode else "pending"

    try:
        if step.item_type == "gift_shop":
            delivery_time = _gift_delivery_time(step.start_time)
            async with _add_ons_lock:
                add_ons = _read_list_json(repo_dir, "add_ons.json")
                gift, _ = _find_gift(add_ons, step.item_id)
                modified = False
                if step.item_id in forced_ids:
                    reserved = False
                    reserved_detail = {"forced_out_of_stock": True, "delivery_time": delivery_time}
                elif gift and isinstance(gift.get("stock"), int):
                    before_stock = int(gift["stock"])
                    if before_stock <= 0:
                        reserved = False
                        reserved_detail = {"stock_before": before_stock, "stock_after": before_stock, "delivery_time": delivery_time}
                    elif step.item_id not in forced_ids:
                        after_stock = before_stock - 1
                        if commit_mode:
                            gift["stock"] = after_stock
                        reserved = True
                        reserved_detail = {
                            "stock_before": before_stock,
                            "stock_after": after_stock,
                            "delivery_time": delivery_time,
                            "payment_gate": payment_gate,
                        }
                        modified = commit_mode
                if commit_mode and modified:
                    _atomic_write_json(os.path.join(repo_dir, "add_ons.json"), add_ons)
            logger.info(
                f"phase=execute_mock | action={'commit_gift' if commit_mode else 'generate_gift_command'} | execution_id={execution_id} | gift_id={step.item_id} | reserved={reserved} | payment_gate={payment_gate} | detail={reserved_detail}"
            )

        elif step.item_type == "activity":
            async with _activities_lock:
                activities = _read_list_json(repo_dir, "activities.json")
                pkg, _ = _find_package(activities, step.item_id)
                modified = False
                requires_booking = bool(pkg.get("requires_booking", False)) if pkg is not None else False

                if step.item_id in forced_ids:
                    reserved = False
                    reserved_detail = {"forced_out_of_stock": True}
                elif requires_booking:
                    async with _reservations_lock:
                        reservations = _read_list_json(repo_dir, "reservations.json")
                        ok, detail = _reserve_capacity(
                            reservations, "package", step.item_id, step.start_time, commit=commit_mode
                        )
                        if not ok:
                            reserved = False
                            reserved_detail = detail
                        else:
                            before_stock = int(pkg["available_stock"]) if isinstance(pkg.get("available_stock"), int) else -1
                            if before_stock <= 0:
                                reserved = False
                                reserved_detail = {
                                    **(detail or {}),
                                    "available_stock_before": before_stock,
                                    "available_stock_after": before_stock,
                                }
                            else:
                                if commit_mode:
                                    pkg["available_stock"] = before_stock - 1
                                reserved = True
                                reserved_detail = {
                                    **(detail or {}),
                                    "available_stock_before": before_stock,
                                    "available_stock_after": before_stock - 1,
                                    "payment_gate": payment_gate,
                                }
                                modified = commit_mode
                                if commit_mode:
                                    _atomic_write_json(os.path.join(repo_dir, "reservations.json"), reservations)
                else:
                    if pkg and isinstance(pkg.get("available_stock"), int):
                        before_stock = int(pkg["available_stock"])
                        if before_stock <= 0:
                            reserved = False
                            reserved_detail = {"available_stock_before": before_stock, "available_stock_after": before_stock}
                        else:
                            if commit_mode:
                                pkg["available_stock"] = before_stock - 1
                            reserved = True
                            reserved_detail = {"available_stock_before": before_stock, "available_stock_after": before_stock - 1, "payment_gate": payment_gate}
                            modified = commit_mode

                if commit_mode and modified:
                    _atomic_write_json(os.path.join(repo_dir, "activities.json"), activities)
            logger.info(
                f"phase=execute_mock | action={'commit_package' if commit_mode else 'generate_package_command'} | execution_id={execution_id} | package_id={step.item_id} | reserved={reserved} | payment_gate={payment_gate} | start_time={step.start_time} | detail={reserved_detail}"
            )

        elif step.item_type == "restaurant":
            requires_booking = False
            restaurants = _read_list_json(repo_dir, "restaurants.json")
            combo, restaurant = _find_combo_with_restaurant(restaurants, step.item_id)
            if combo is not None:
                requires_booking = bool(combo.get("requires_booking", False))
            booking_target_type = step.booking_target_type or "restaurant"
            booking_target_id = step.booking_target_id or ((restaurant or {}).get("id") or (restaurant or {}).get("restaurant_id") or step.item_id)

            reservations = None
            if step.item_id in forced_ids:
                reserved = False
                reserved_detail = {"forced_out_of_stock": True}
            elif requires_booking:
                async with _reservations_lock:
                    reservations = _read_list_json(repo_dir, "reservations.json")
                    reserved, reserved_detail = _reserve_capacity(
                        reservations, booking_target_type, booking_target_id, step.start_time, commit=commit_mode
                    )
                    if commit_mode and reserved:
                        _atomic_write_json(os.path.join(repo_dir, "reservations.json"), reservations)
            else:
                reserved = True
                reserved_detail = {"requires_booking": False, "payment_gate": payment_gate}

            if not reserved and step.replacement_policy != "strict" and not step.user_touched:
                logger.info(f"phase=execute_mock | action=fallback_start | execution_id={execution_id} | original_id={step.item_id} | backups={len(step.backup_candidates or [])}")
                async with _reservations_lock:
                    reservations = _read_list_json(repo_dir, "reservations.json")
                    for attempt_index, backup in enumerate((step.backup_candidates or []), start=1):
                        b_requires_confirmation = backup.get("requires_confirmation", False)
                        logger.info(
                            f"phase=execute_mock | action=fallback_check | execution_id={execution_id} | original_id={step.item_id} | attempt={attempt_index} | backup_id={backup.get('id')} | requires_confirmation={b_requires_confirmation}"
                        )
                        b_id = backup.get("id")
                        if not b_id or str(b_id) in forced_ids:
                            logger.info(
                                f"phase=execute_mock | action=fallback_next | execution_id={execution_id} | original_id={step.item_id} | attempt={attempt_index} | backup_id={b_id} | reason=invalid_or_forced"
                            )
                            continue

                        b_combo, b_restaurant = _find_combo_with_restaurant(restaurants, b_id)
                        if not b_combo:
                            logger.info(f"phase=execute_mock | action=fallback_skip | execution_id={execution_id} | backup_id={b_id} | reason=combo_not_found")
                            logger.info(
                                f"phase=execute_mock | action=fallback_next | execution_id={execution_id} | original_id={step.item_id} | attempt={attempt_index} | backup_id={b_id} | reason=combo_not_found"
                            )
                            continue

                        if bool(b_requires_confirmation):
                            stop_payload = {
                                "execution_id": execution_id,
                                "item_id": step.item_id,
                                "item_type": step.item_type,
                                "backup_id": b_id,
                                "backup_name": backup.get("name"),
                                "violation_reason": backup.get("violation_reason"),
                                "backup_candidates": [
                                    {
                                        "id": x.get("id"),
                                        "name": x.get("name"),
                                        "violation_reason": x.get("violation_reason"),
                                        "requires_confirmation": bool(x.get("requires_confirmation", False)),
                                    }
                                    for x in (step.backup_candidates or [])
                                    if isinstance(x, dict)
                                ],
                            }
                            ctx.control["stop"] = True
                            ctx.control["status"] = "needs_fixup"
                            ctx.control["stop_payload"] = stop_payload

                            logger.info(
                                f"phase=execute_mock | action=fallback_pending_confirmation | execution_id={execution_id} | original_id={step.item_id} | backup_id={b_id}"
                            )
                            await _emit(
                                ctx,
                                ExecuteEvent(
                                    type="item_update",
                                    data={
                                        "execution_id": execution_id,
                                        "item_id": step.item_id,
                                        "item_type": step.item_type,
                                        "phase": "pending_user_confirmation",
                                        "message": f"主选餐厅无座，需要你从备选中选择替换：{backup.get('violation_reason')}",
                                        "backup_id": b_id,
                                        "backup_name": backup.get("name"),
                                        "violation_reason": backup.get("violation_reason"),
                                        "backup_candidates": stop_payload.get("backup_candidates"),
                                    },
                                ),
                            )
                            reserved_detail = {
                                **(reserved_detail or {}),
                                "needs_user_confirmation": True,
                                "blocked_by_backup_id": b_id,
                                "violation_reason": backup.get("violation_reason"),
                            }
                            break

                        b_requires_booking = bool(b_combo.get("requires_booking", False))
                        b_booking_target_id = (b_restaurant or {}).get("id") or (b_restaurant or {}).get("restaurant_id") or str(b_id)
                        b_reserved = False
                        b_detail: dict[str, Any] | None = None
                        if b_requires_booking:
                            b_reserved, b_detail = _reserve_capacity(
                                reservations, "restaurant", b_booking_target_id, step.start_time, commit=commit_mode
                            )
                            if commit_mode and b_reserved:
                                _atomic_write_json(os.path.join(repo_dir, "reservations.json"), reservations)
                        else:
                            b_reserved = True
                            b_detail = {"requires_booking": False}

                        logger.info(
                            f"phase=execute_mock | action=fallback_reserve_result | execution_id={execution_id} | original_id={step.item_id} | attempt={attempt_index} | backup_id={b_id} | reserved={b_reserved} | detail={b_detail}"
                        )

                        if not b_reserved:
                            reason = None
                            if isinstance(b_detail, dict):
                                reason = b_detail.get("reason")
                            logger.info(
                                f"phase=execute_mock | action=fallback_next | execution_id={execution_id} | original_id={step.item_id} | attempt={attempt_index} | backup_id={b_id} | reason={reason or 'booking_failed'}"
                            )
                            continue

                        reserved = True
                        replaced = True
                        new_item_id = str(b_id)
                        new_item_name = backup.get("name")
                        reserved_detail = {
                            **(reserved_detail or {}),
                            "auto_replaced": True,
                            "attempt": attempt_index,
                            "new_combo_id": b_id,
                            "new_combo_name": new_item_name,
                            "booking_target_type": "restaurant",
                            "booking_target_id": b_booking_target_id,
                            "replacement_detail": b_detail,
                        }
                        break

                    if (not reserved) and (not bool(ctx.control.get("stop"))) and (step.backup_candidates or []):
                        stop_payload = {
                            "execution_id": execution_id,
                            "item_id": step.item_id,
                            "item_type": step.item_type,
                            "backup_id": None,
                            "backup_name": None,
                            "violation_reason": "自动备选均失败，需要搜索或手动选择替换",
                            "backup_candidates": [
                                {
                                    "id": x.get("id"),
                                    "name": x.get("name"),
                                    "violation_reason": x.get("violation_reason"),
                                    "requires_confirmation": bool(x.get("requires_confirmation", False)),
                                }
                                for x in (step.backup_candidates or [])
                                if isinstance(x, dict)
                            ],
                        }
                        ctx.control["stop"] = True
                        ctx.control["status"] = "needs_fixup"
                        ctx.control["stop_payload"] = stop_payload
                        logger.info(
                            f"phase=execute_mock | action=fallback_exhausted_needs_fixup | execution_id={execution_id} | original_id={step.item_id}"
                        )
                        await _emit(
                            ctx,
                            ExecuteEvent(
                                type="item_update",
                                data={
                                    "execution_id": execution_id,
                                    "item_id": step.item_id,
                                    "item_type": step.item_type,
                                    "phase": "pending_user_confirmation",
                                    "message": stop_payload.get("violation_reason"),
                                    "backup_id": None,
                                    "backup_name": None,
                                    "violation_reason": stop_payload.get("violation_reason"),
                                    "backup_candidates": stop_payload.get("backup_candidates"),
                                },
                            ),
                        )
                        reserved_detail = {
                            **(reserved_detail or {}),
                            "needs_user_confirmation": True,
                            "violation_reason": stop_payload.get("violation_reason"),
                        }
            logger.info(
                f"phase=execute_mock | action=reserve_combo | execution_id={execution_id} | combo_id={step.item_id} | reserved={reserved} | start_time={step.start_time} | detail={reserved_detail} | replaced={replaced} | new_id={new_item_id}"
            )
    except Exception as e:
        logger.error(f"phase=execute_mock | execution_id={execution_id} | item_id={step.item_id} | error={e}")

    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": step.item_type,
                "phase": "done",
                "checked_ms": checked_ms,
                "reserved_ms": reserved_ms,
                "reserved": bool(reserved),
                "detail": reserved_detail,
                "delivery_time": delivery_time,
                "replaced": replaced,
                "new_item_id": new_item_id,
                "new_item_name": new_item_name,
            },
        ),
    )

async def _book_taxi(execution_id: str, ctx: _ExecutionContext, step: ExecuteStep) -> None:
    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": "commute",
                "phase": "checking",
                "message": "正在读取出租车运力与预估费用…",
            },
        ),
    )

    config = get_config()
    sim_delay_max = float(getattr(config, "EXECUTION_SIM_DELAY_MAX_SECS", 0.02))
    check_delay = float(random.uniform(0.0, max(0.0, sim_delay_max)))
    t0 = time.perf_counter()
    await asyncio.sleep(check_delay)
    checked_ms = int((time.perf_counter() - t0) * 1000)

    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": "commute",
                "phase": "reserving",
                "message": "正在预定出租车…",
                "checked_ms": checked_ms,
            },
        ),
    )

    reserve_delay = float(random.uniform(0.0, max(0.0, sim_delay_max)))
    t1 = time.perf_counter()
    await asyncio.sleep(reserve_delay)
    reserved_ms = int((time.perf_counter() - t1) * 1000)

    logger.info(
        f"phase=execute_mock | action=reserve_taxi | execution_id={execution_id} | commute_id={step.item_id} | checked_ms={checked_ms} | reserved_ms={reserved_ms}"
    )

    await _emit(
        ctx,
        ExecuteEvent(
            type="item_update",
            data={
                "execution_id": execution_id,
                "item_id": step.item_id,
                "item_type": "commute",
                "phase": "done",
                "checked_ms": checked_ms,
                "reserved_ms": reserved_ms,
                "reserved": True,
                "detail": {"commute_mode": "taxi", "checked_ms": checked_ms, "reserved_ms": reserved_ms},
            },
        ),
    )


async def _run_execution(execution_id: str, ctx: _ExecutionContext) -> None:
    steps = list(ctx.request.steps or [])
    total = len(steps)

    await _emit(
        ctx,
        ExecuteEvent(type="item_update", data={"execution_id": execution_id, "phase": "checking", "total": total}),
    )

    for step in steps:
        if bool(ctx.control.get("stop")):
            break
        if step.item_type == "commute":
            if (step.commute_mode or "") == "taxi":
                await _book_taxi(execution_id, ctx, step)
            continue
        await _check_and_reserve_one(execution_id, ctx, step)

    await _emit(
        ctx,
        ExecuteEvent(
            type="done",
            data={
                "execution_id": execution_id,
                "status": str(ctx.control.get("status") or "ok"),
                "stop_payload": ctx.control.get("stop_payload"),
            },
        ),
    )
