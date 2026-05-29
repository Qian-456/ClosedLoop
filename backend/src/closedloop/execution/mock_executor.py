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


_activities_lock = asyncio.Lock()
_add_ons_lock = asyncio.Lock()
_restaurants_lock = asyncio.Lock()
_reservations_lock = asyncio.Lock()


@dataclass(frozen=True)
class _ExecutionContext:
    request: ExecuteRequest
    queue: asyncio.Queue[dict[str, Any]]


_executions: dict[str, _ExecutionContext] = {}
_executions_guard = asyncio.Lock()

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


def _reserve_capacity(
    reservations: list[dict[str, Any]],
    target_type: Literal["combo", "package"],
    target_id: str,
    start_time: str,
) -> tuple[bool, dict[str, Any] | None]:
    record = None
    for r in reservations:
        if r.get("target_type") == target_type and r.get("target_id") == target_id:
            record = r
            break
    if not record:
        return False, None
    slot = _pick_time_slot(record, start_time)
    if not slot:
        return False, None
    if isinstance(slot.get("capacity_remaining"), int):
        before = int(slot["capacity_remaining"])
        after = max(0, before - 1)
        slot["capacity_remaining"] = after
        return True, {
            "slot_start_time": slot.get("start_time"),
            "slot_end_time": slot.get("end_time"),
            "capacity_remaining_before": before,
            "capacity_remaining_after": after,
        }
    return False, None


async def start_execution(request: ExecuteRequest) -> str:
    """创建执行会话并启动后台任务，返回 execution_id。"""

    execution_id = f"exe_{uuid.uuid4().hex}"
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    ctx = _ExecutionContext(request=request, queue=queue)

    async with _executions_guard:
        _executions[execution_id] = ctx

    asyncio.create_task(_run_execution(execution_id, ctx))
    return execution_id


async def iter_events(execution_id: str) -> AsyncIterator[dict[str, Any]]:
    """按 SSE 需要顺序产出事件（以 dict 形式）。"""

    async with _executions_guard:
        ctx = _executions.get(execution_id)
    if not ctx:
        yield ExecuteEvent(type="done", data={"status": "not_found"}).model_dump()
        return

    try:
        while True:
            event = await ctx.queue.get()
            yield event
            if event.get("type") == "done":
                return
    finally:
        async with _executions_guard:
            _executions.pop(execution_id, None)


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
        return "正在锁定餐厅预约位置…"
    if step.item_type == "activity":
        return "正在预定门票并扣减库存…"
    if step.item_type == "gift_shop":
        return "正在预定礼物并安排配送…"
    return "正在预定…"


async def _check_and_reserve_one(execution_id: str, ctx: _ExecutionContext, step: ExecuteStep) -> None:
    if step.item_type == "commute":
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

    check_delay = float(random.uniform(0.05, 0.30))
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

    reserve_delay = float(random.uniform(0.05, 0.30))
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

    try:
        if step.item_type == "gift_shop":
            delivery_time = _gift_delivery_time(step.start_time)
            async with _add_ons_lock:
                add_ons = _read_list_json(repo_dir, "add_ons.json")
                gift, _ = _find_gift(add_ons, step.item_id)
                if gift and isinstance(gift.get("stock"), int):
                    before_stock = int(gift["stock"])
                    after_stock = max(0, before_stock - 1)
                    gift["stock"] = after_stock
                    reserved = True
                    reserved_detail = {
                        "stock_before": before_stock,
                        "stock_after": after_stock,
                        "delivery_time": delivery_time,
                    }
                _atomic_write_json(os.path.join(repo_dir, "add_ons.json"), add_ons)
            logger.info(
                f"phase=execute_mock | action=reserve_gift | execution_id={execution_id} | gift_id={step.item_id} | reserved={reserved} | detail={reserved_detail}"
            )

        elif step.item_type == "activity":
            async with _activities_lock:
                activities = _read_list_json(repo_dir, "activities.json")
                pkg, _ = _find_package(activities, step.item_id)
                modified = False
                if pkg and isinstance(pkg.get("available_stock"), int):
                    before_stock = int(pkg["available_stock"])
                    after_stock = max(0, before_stock - 1)
                    pkg["available_stock"] = after_stock
                    reserved = True
                    reserved_detail = {"available_stock_before": before_stock, "available_stock_after": after_stock}
                    modified = True
                if modified:
                    _atomic_write_json(os.path.join(repo_dir, "activities.json"), activities)

            requires_booking = False
            if pkg is not None:
                requires_booking = bool(pkg.get("requires_booking", False))
            if requires_booking:
                async with _reservations_lock:
                    reservations = _read_list_json(repo_dir, "reservations.json")
                    ok, detail = _reserve_capacity(
                        reservations, "package", step.item_id, step.start_time
                    )
                    reserved = ok or reserved
                    if detail:
                        reserved_detail = {**(reserved_detail or {}), **detail}
                    _atomic_write_json(os.path.join(repo_dir, "reservations.json"), reservations)
            logger.info(
                f"phase=execute_mock | action=reserve_package | execution_id={execution_id} | package_id={step.item_id} | reserved={reserved} | start_time={step.start_time} | detail={reserved_detail}"
            )

        elif step.item_type == "restaurant":
            requires_booking = False
            restaurants = _read_list_json(repo_dir, "restaurants.json")
            combo = _find_combo(restaurants, step.item_id)
            if combo is not None:
                requires_booking = bool(combo.get("requires_booking", False))

            if requires_booking:
                async with _reservations_lock:
                    reservations = _read_list_json(repo_dir, "reservations.json")
                    reserved, reserved_detail = _reserve_capacity(
                        reservations, "combo", step.item_id, step.start_time
                    )
                    
                    if not reserved and step.replacement_policy != "strict" and not step.user_touched:
                        logger.debug(f"phase=execute_mock | action=fallback_start | execution_id={execution_id} | original_id={step.item_id} | backups={len(step.backup_candidates or [])}")
                        for backup in (step.backup_candidates or []):
                            b_requires_confirmation = backup.get("requires_confirmation", False)
                            logger.debug(f"phase=execute_mock | action=fallback_check | backup_id={backup.get('id')} | requires_confirmation={b_requires_confirmation}")
                            if b_requires_confirmation:
                                # Trigger user confirmation event instead of silent replacement
                                await _emit(ctx, ExecuteEvent(
                                    type="item_update",
                                    data={
                                        "execution_id": execution_id,
                                        "item_id": step.item_id,
                                        "item_type": step.item_type,
                                        "phase": "pending_user_confirmation",
                                        "message": f"主选餐厅无座，备选餐厅({backup.get('name')})触发提醒: {backup.get('violation_reason')}",
                                    }
                                ))
                                break # Stop silent replacement

                            b_id = backup.get("id")
                            b_combo = _find_combo(restaurants, b_id)
                            if not b_combo:
                                continue
                            b_req_booking = bool(b_combo.get("requires_booking", False))
                            if b_req_booking:
                                b_reserved, b_detail = _reserve_capacity(reservations, "combo", b_id, step.start_time)
                                if b_reserved:
                                    reserved = True
                                    reserved_detail = b_detail
                                    replaced = True
                                    new_item_id = b_id
                                    new_item_name = backup.get("name")
                                    break
                            else:
                                reserved = True
                                replaced = True
                                new_item_id = b_id
                                new_item_name = backup.get("name")
                                break
                                
                    if reserved:
                        _atomic_write_json(os.path.join(repo_dir, "reservations.json"), reservations)
            else:
                reserved = True
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

    check_delay = float(random.uniform(0.05, 0.30))
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

    reserve_delay = float(random.uniform(0.05, 0.30))
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
            },
        ),
    )


async def _run_execution(execution_id: str, ctx: _ExecutionContext) -> None:
    steps = [s for s in ctx.request.steps if s.item_type != "commute"]
    commutes = [s for s in ctx.request.steps if s.item_type == "commute"]

    taxi_steps = [c for c in commutes if (c.commute_mode or "") == "taxi"]
    total = len(steps) + len(taxi_steps)

    await _emit(
        ctx,
        ExecuteEvent(type="item_update", data={"execution_id": execution_id, "phase": "checking", "total": total}),
    )

    tasks: list[asyncio.Task] = []
    for taxi_step in taxi_steps:
        tasks.append(asyncio.create_task(_book_taxi(execution_id, ctx, taxi_step)))
    tasks.extend([asyncio.create_task(_check_and_reserve_one(execution_id, ctx, s)) for s in steps])
    await asyncio.gather(*tasks, return_exceptions=True)

    await _emit(ctx, ExecuteEvent(type="done", data={"execution_id": execution_id, "status": "ok"}))
