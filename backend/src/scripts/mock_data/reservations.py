import random
from typing import Any


def _parse_hhmm_to_minutes(v: str) -> int:
    if not v or ":" not in v:
        return 0
    h, m = v.split(":", 1)
    return int(h) * 60 + int(m)


def _format_minutes_to_hhmm(minutes: int) -> str:
    minutes = max(0, int(minutes)) % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _pick_capacity_total(*, target_type: str, duration_mins: int | None) -> int:
    duration_mins = int(duration_mins or 60)
    if target_type in ("combo", "restaurant"):
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
        end_min = min(close_min, start_min + max(60, duration_mins))
        return [{"start_time": _format_minutes_to_hhmm(start_min), "end_time": _format_minutes_to_hhmm(end_min)}]

    start_candidates: list[int] = []
    cursor = open_min
    while cursor + duration_mins <= close_min:
        start_candidates.append(cursor)
        cursor += 30

    if not start_candidates:
        end_min = min(close_min, open_min + max(60, duration_mins))
        return [{"start_time": _format_minutes_to_hhmm(open_min), "end_time": _format_minutes_to_hhmm(end_min)}]

    k = random.randint(3, 6)
    chosen = sorted(random.sample(start_candidates, k=min(k, len(start_candidates))))
    return [
        {"start_time": _format_minutes_to_hhmm(s), "end_time": _format_minutes_to_hhmm(min(s + duration_mins, close_min))}
        for s in chosen
    ]


def _build_time_slots_for_combo(*, combo: dict) -> list[dict]:
    duration_mins = int(combo.get("duration_mins") or 60)
    duration_mins = max(30, min(duration_mins, 4 * 60))

    windows: dict[str, tuple[int, int]] = {
        "breakfast": (8 * 60, 10 * 60),
        "lunch": (11 * 60, 13 * 60 + 30),
        "afternoon_tea": (13 * 60, 17 * 60),
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
    return [
        {"start_time": _format_minutes_to_hhmm(s), "end_time": _format_minutes_to_hhmm(s + duration_mins)}
        for s in chosen
    ]


def _build_time_slots_for_restaurant(*, restaurant: dict) -> list[dict]:
    business_hours = restaurant.get("business_hours") or "10:00-22:00"
    open_h, close_h = business_hours.split("-", 1) if "-" in business_hours else ("10:00", "22:00")
    open_min = _parse_hhmm_to_minutes(open_h)
    close_min = _parse_hhmm_to_minutes(close_h)
    if close_min <= open_min:
        close_min = open_min + 12 * 60

    duration_mins = 90
    start_candidates: list[int] = []
    cursor = open_min
    while cursor + duration_mins <= close_min:
        start_candidates.append(cursor)
        cursor += 30

    if not start_candidates:
        end_min = min(close_min, open_min + duration_mins)
        return [{"start_time": _format_minutes_to_hhmm(open_min), "end_time": _format_minutes_to_hhmm(end_min)}]

    k = random.randint(4, 7)
    chosen = sorted(random.sample(start_candidates, k=min(k, len(start_candidates))))
    return [
        {"start_time": _format_minutes_to_hhmm(s), "end_time": _format_minutes_to_hhmm(min(s + duration_mins, close_min))}
        for s in chosen
    ]


def generate_reservations_from_mock_db(mock_db: dict[str, Any]) -> list[dict]:
    reservations: list[dict] = []

    for venue in mock_db.get("activity_venues", []):
        business_hours = venue.get("business_hours") or "09:00-22:00"
        for p in venue.get("packages", []):
            target_id = p.get("package_id")
            if not target_id:
                continue

            raw_slots = _build_time_slots_for_package(package=p, business_hours=business_hours)
            duration_mins = int(p.get("duration_mins") or 60)
            capacity_total = _pick_capacity_total(target_type="package", duration_mins=duration_mins)
            prob = p.get("seating_risk_prob")
            risk_prob = float(prob) if isinstance(prob, (int, float)) else 0.0

            time_slots: list[dict] = []
            for s in raw_slots:
                if risk_prob > 0 and random.random() < min(0.75, risk_prob):
                    remaining = 0
                else:
                    remaining = random.randint(0, capacity_total)
                    if random.random() < 0.12:
                        remaining = 0

                fullness = 1.0 - (remaining / max(1, capacity_total))
                queue_required = remaining == 0 or fullness >= 0.85 or (random.random() < 0.06)
                wait_minutes = 0
                if queue_required:
                    wait_minutes = int(round(10 + 70 * fullness))

                time_slots.append(
                    {
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "capacity_total": int(capacity_total),
                        "capacity_remaining": int(remaining),
                        "queue_required": bool(queue_required),
                        "wait_minutes": int(wait_minutes),
                    }
                )

            reservations.append({"target_type": "package", "target_id": target_id, "time_slots": time_slots})

    for rest in mock_db.get("restaurants", []):
        target_id = rest.get("id")
        if not target_id:
            continue

        raw_slots = _build_time_slots_for_restaurant(restaurant=rest)
        capacity_total = _pick_capacity_total(target_type="restaurant", duration_mins=90)
        time_slots: list[dict] = []

        for s in raw_slots:
            remaining = random.randint(0, capacity_total)
            if random.random() < 0.12:
                remaining = 0
            fullness = 1.0 - (remaining / max(1, capacity_total))
            queue_required = remaining == 0 or fullness >= 0.85 or (random.random() < 0.06)
            wait_minutes = 0
            if queue_required:
                wait_minutes = int(round(8 + 55 * fullness))

            time_slots.append(
                {
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "capacity_total": int(capacity_total),
                    "capacity_remaining": int(remaining),
                    "queue_required": bool(queue_required),
                    "wait_minutes": int(wait_minutes),
                }
            )

        reservations.append({"target_type": "restaurant", "target_id": str(target_id), "time_slots": time_slots})

    return reservations
