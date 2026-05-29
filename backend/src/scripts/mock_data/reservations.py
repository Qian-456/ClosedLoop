import os
import json
import math
import random
import re
import sys
from typing import List, Dict, Any, Optional

from scripts.mock_data.constants import DEMO_BACKUP_COMBO_IDS, DEMO_FULL_COMBO_IDS, DEMO_SOLD_OUT_PACKAGE_IDS

PACKAGE_RANDOM_SOLD_OUT_RATE = 0.03
PACKAGE_RANDOM_QUEUE_RATE = 0.03
COMBO_RANDOM_FULL_RATE = 0.04
COMBO_RANDOM_QUEUE_RATE = 0.03

def _parse_hhmm_to_minutes(v: str) -> int:
    if not v or ":" not in v:
        return 0
    h, m = v.split(":", 1)
    return int(h) * 60 + int(m)


def _format_minutes_to_hhmm(minutes: int) -> str:
    if minutes < 0:
        minutes = 0
    minutes = minutes % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _pick_capacity_total(*, target_type: str, duration_mins: int | None) -> int:
    duration_mins = int(duration_mins or 60)
    if target_type == "combo":
        if duration_mins >= 150:
            return random.randint(4, 10)
        if duration_mins >= 90:
            return random.randint(6, 14)
        return random.randint(8, 18)

    if duration_mins >= 240:
        return random.randint(10, 30)
    if duration_mins >= 120:
        return random.randint(15, 50)
    return random.randint(20, 80)


def _build_time_slots_for_package(*, package: dict, business_hours: str) -> list[dict]:
    open_h, close_h = business_hours.split("-", 1) if "-" in business_hours else ("09:00", "22:00")
    open_min = _parse_hhmm_to_minutes(open_h)
    close_min = _parse_hhmm_to_minutes(close_h)
    if close_min <= open_min:
        close_min = open_min + 13 * 60

    duration_mins = int(package.get("duration_mins") or 60)
    duration_mins = max(30, min(duration_mins, 6 * 60))

    start_time = package.get("start_time")
    if isinstance(start_time, str) and start_time:
        start_min = _parse_hhmm_to_minutes(start_time)
        end_min = start_min + max(60, duration_mins)
        if end_min > close_min:
            end_min = close_min
        return [
            {
                "start_time": _format_minutes_to_hhmm(start_min),
                "end_time": _format_minutes_to_hhmm(end_min),
            }
        ]

    k = random.randint(3, 6)
    start_candidates: list[int] = []
    cursor = open_min
    while cursor + duration_mins <= close_min:
        start_candidates.append(cursor)
        cursor += 30

    if not start_candidates:
        return [
            {
                "start_time": _format_minutes_to_hhmm(open_min),
                "end_time": _format_minutes_to_hhmm(min(open_min + max(60, duration_mins), close_min)),
            }
        ]

    chosen = sorted(random.sample(start_candidates, k=min(k, len(start_candidates))))
    return [
        {
            "start_time": _format_minutes_to_hhmm(s),
            "end_time": _format_minutes_to_hhmm(min(s + duration_mins, close_min)),
        }
        for s in chosen
    ]


def _build_time_slots_for_combo(*, combo: dict) -> list[dict]:
    duration_mins = int(combo.get("duration_mins") or 60)
    duration_mins = max(30, min(duration_mins, 4 * 60))

    windows: dict[str, tuple[int, int]] = {
        "breakfast": (8 * 60, 10 * 60),
        "lunch": (11 * 60, 13 * 60 + 30),
        "afternoon_tea": (14 * 60, 16 * 60 + 30),
        "dinner": (17 * 60, 20 * 60 + 30),
        "late_night": (21 * 60, 23 * 60 + 30),
    }

    suitable = combo.get("suitable_time_slots") or []
    candidate_starts: list[int] = []
    for slot in suitable:
        if slot not in windows:
            continue
        w_start, w_end = windows[slot]
        cursor = w_start
        while cursor + duration_mins <= w_end:
            candidate_starts.append(cursor)
            cursor += 30

    if not candidate_starts:
        candidate_starts = [11 * 60, 12 * 60, 18 * 60]

    k = random.randint(2, 4)
    chosen = sorted(random.sample(candidate_starts, k=min(k, len(candidate_starts))))
    slots_out: list[dict] = []
    for s in chosen:
        end_min = s + duration_mins
        slots_out.append(
            {
                "start_time": _format_minutes_to_hhmm(s),
                "end_time": _format_minutes_to_hhmm(end_min),
            }
        )
    return slots_out


def generate_reservations_from_mock_db(mock_db: dict[str, Any]) -> list[dict]:
    reservations: list[dict] = []

    for venue in mock_db.get("activity_venues", []):
        business_hours = venue.get("business_hours") or "09:00-22:00"
        for p in venue.get("packages", []):
            if p.get("requires_booking") is not True:
                continue
            target_id = p.get("package_id")
            if not target_id:
                continue

            raw_slots = _build_time_slots_for_package(package=p, business_hours=business_hours)
            duration_mins = int(p.get("duration_mins") or 60)
            capacity_total = _pick_capacity_total(target_type="package", duration_mins=duration_mins)
            time_slots: list[dict] = []
            for s in raw_slots:
                remaining = random.randint(0, capacity_total)
                if random.random() < PACKAGE_RANDOM_SOLD_OUT_RATE:
                    remaining = 0
                if target_id in DEMO_SOLD_OUT_PACKAGE_IDS:
                    remaining = 0
                fullness = 1.0 - (remaining / max(1, capacity_total))
                queue_required = remaining == 0 or fullness >= 0.8 or (random.random() < PACKAGE_RANDOM_QUEUE_RATE)
                wait_minutes = 0
                if queue_required:
                    wait_minutes = int(round(10 + 80 * fullness))
                time_slots.append(
                    {
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "capacity_total": capacity_total,
                        "capacity_remaining": remaining,
                        "queue_required": bool(queue_required),
                        "wait_minutes": int(wait_minutes),
                    }
                )

            reservations.append(
                {
                    "target_type": "package",
                    "target_id": target_id,
                    "time_slots": time_slots,
                }
            )

    for restaurant in mock_db.get("restaurants", []):
        for c in restaurant.get("combos", []):
            if c.get("requires_booking") is not True:
                continue
            target_id = c.get("combo_id")
            if not target_id:
                continue

            raw_slots = _build_time_slots_for_combo(combo=c)
            duration_mins = int(c.get("duration_mins") or 60)
            capacity_total = _pick_capacity_total(target_type="combo", duration_mins=duration_mins)
            time_slots: list[dict] = []
            for s in raw_slots:
                remaining = random.randint(0, capacity_total)
                if random.random() < COMBO_RANDOM_FULL_RATE:
                    remaining = 0
                
                # 演示锚点：主选固定无座，备选固定可承接自动替换。
                if target_id in DEMO_FULL_COMBO_IDS:
                    remaining = 0
                elif target_id in DEMO_BACKUP_COMBO_IDS:
                    remaining = max(2, remaining)
                    
                fullness = 1.0 - (remaining / max(1, capacity_total))
                queue_required = remaining == 0 or fullness >= 0.8 or (random.random() < COMBO_RANDOM_QUEUE_RATE)
                wait_minutes = 0
                if queue_required:
                    wait_minutes = int(round(5 + 60 * fullness))
                time_slots.append(
                    {
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "capacity_total": capacity_total,
                        "capacity_remaining": remaining,
                        "queue_required": bool(queue_required),
                        "wait_minutes": int(wait_minutes),
                    }
                )

            reservations.append(
                {
                    "target_type": "combo",
                    "target_id": target_id,
                    "time_slots": time_slots,
                }
            )

    return reservations

