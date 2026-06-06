from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def percentile(values: list[float], q: float) -> float:
    """Return the q-th percentile (0-100) using the nearest-rank method."""
    if not values:
        raise ValueError("values must not be empty")
    if q < 0 or q > 100:
        raise ValueError("q must be between 0 and 100")

    sorted_values = sorted(values)
    n = len(sorted_values)
    if q == 0:
        return float(sorted_values[0])
    if q == 100:
        return float(sorted_values[-1])

    rank = int((q / 100.0) * n)
    if (q / 100.0) * n > rank:
        rank += 1
    index = max(0, min(n - 1, rank - 1))
    return float(sorted_values[index])


@dataclass(frozen=True)
class LatencySummary:
    """Hold latency summary statistics."""

    count: int
    success_count: int
    error_count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p90_ms: float
    p99_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert the summary into JSON-serializable dictionary."""
        return {
            "count": self.count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "mean_ms": self.mean_ms,
            "p50_ms": self.p50_ms,
            "p90_ms": self.p90_ms,
            "p99_ms": self.p99_ms,
        }


def summarize_latencies(latencies_ms: list[float], success_count: int, error_count: int) -> LatencySummary:
    """Summarize latency distributions into percentiles."""
    if not latencies_ms:
        raise ValueError("latencies_ms must not be empty")

    count = len(latencies_ms)
    min_ms = float(min(latencies_ms))
    max_ms = float(max(latencies_ms))
    mean_ms = float(sum(latencies_ms) / count)

    return LatencySummary(
        count=count,
        success_count=success_count,
        error_count=error_count,
        min_ms=min_ms,
        max_ms=max_ms,
        mean_ms=mean_ms,
        p50_ms=percentile(latencies_ms, 50),
        p90_ms=percentile(latencies_ms, 90),
        p99_ms=percentile(latencies_ms, 99),
    )


def build_default_constraints_cases() -> list[dict[str, Any]]:
    """Build 20 representative constraints cases for benchmarking plan_sub_backend."""
    base_duration = (4.0, 6.0)
    cases: list[dict[str, Any]] = [
        {
            "group_type": "friends",
            "budget": 300.0,
            "preferred_distance": "<2km",
            "time_period": "14:00",
            "duration_hours": base_duration,
            "activity_preferences": ["安静", "打卡点"],
            "adult_count": 2,
            "child_count": 0,
            "commute_preference": "walking",
            "queue_preference": "avoid_queues",
            "include_gift": True,
        },
        {
            "group_type": "friends",
            "budget": 600.0,
            "preferred_distance": "2km-5km",
            "time_period": "18:00",
            "duration_hours": base_duration,
            "activity_preferences": ["热闹", "美食"],
            "adult_count": 3,
            "child_count": 0,
            "commute_preference": "taxi",
            "queue_preference": "accept_hot",
            "include_gift": True,
        },
        {
            "group_type": "family",
            "budget": 500.0,
            "preferred_distance": "<2km",
            "time_period": "10:30",
            "duration_hours": base_duration,
            "activity_preferences": ["亲子", "轻松"],
            "adult_count": 2,
            "child_count": 1,
            "child_profiles": [("F", 6)],
            "commute_preference": "taxi",
            "queue_preference": "avoid_queues",
            "include_gift": True,
        },
        {
            "group_type": "family",
            "budget": 800.0,
            "preferred_distance": "2km-5km",
            "time_period": "15:00",
            "duration_hours": base_duration,
            "activity_preferences": ["室内", "拍照"],
            "adult_count": 2,
            "child_count": 2,
            "child_profiles": [("F", 3), ("M", 8)],
            "commute_preference": "auto",
            "queue_preference": "neutral",
            "include_gift": True,
        },
        {
            "group_type": "friends",
            "budget": 400.0,
            "preferred_distance": ">5km",
            "time_period": "12:00",
            "duration_hours": base_duration,
            "activity_preferences": ["运动", "户外"],
            "adult_count": 2,
            "child_count": 0,
            "commute_preference": "driving",
            "queue_preference": "neutral",
            "include_gift": False,
        },
        {
            "group_type": "friends",
            "budget": 350.0,
            "preferred_distance": "<2km",
            "time_period": "19:00",
            "duration_hours": base_duration,
            "activity_preferences": ["电影", "安静"],
            "adult_count": 2,
            "child_count": 0,
            "commute_preference": "walking",
            "queue_preference": "avoid_queues",
            "include_gift": False,
        },
        {
            "group_type": "family",
            "budget": 650.0,
            "preferred_distance": "2km-5km",
            "time_period": "11:00",
            "duration_hours": base_duration,
            "activity_preferences": ["亲子", "低噪音"],
            "adult_count": 2,
            "child_count": 1,
            "child_profiles": [("F", -1)],
            "commute_preference": "taxi",
            "queue_preference": "avoid_queues",
            "include_gift": True,
        },
        {
            "group_type": "friends",
            "budget": 1000.0,
            "preferred_distance": ">5km",
            "time_period": "13:30",
            "duration_hours": (5.5, 6.5),
            "activity_preferences": ["精致", "氛围感"],
            "adult_count": 4,
            "child_count": 0,
            "commute_preference": "driving",
            "queue_preference": "accept_hot",
            "include_gift": True,
        },
        {
            "group_type": "family",
            "budget": 450.0,
            "preferred_distance": "<2km",
            "time_period": "16:00",
            "duration_hours": base_duration,
            "activity_preferences": ["室内", "亲子"],
            "adult_count": 2,
            "child_count": 1,
            "child_profiles": [("F", 0)],
            "commute_preference": "taxi",
            "queue_preference": "avoid_queues",
            "include_gift": False,
        },
        {
            "group_type": "friends",
            "budget": 280.0,
            "preferred_distance": "2km-5km",
            "time_period": "14:30",
            "duration_hours": (4.0, 4.0),
            "activity_preferences": ["省钱", "轻松"],
            "adult_count": 2,
            "child_count": 0,
            "commute_preference": "auto",
            "queue_preference": "neutral",
            "include_gift": False,
        },
    ]

    templates = [
        ("friends", 520.0, "<2km", "15:30", ["展览", "拍照"], 2, 0, "walking", "neutral", True),
        ("friends", 420.0, "2km-5km", "17:30", ["咖啡", "聊天"], 2, 0, "taxi", "avoid_queues", False),
        ("family", 720.0, "<2km", "10:00", ["亲子", "轻量"], 2, 1, "walking", "avoid_queues", True),
        ("family", 900.0, "2km-5km", "13:00", ["室内", "手作"], 2, 2, "taxi", "neutral", True),
        ("friends", 760.0, ">5km", "18:30", ["网红", "热闹"], 3, 0, "driving", "accept_hot", True),
        ("friends", 380.0, "<2km", "11:30", ["午餐", "轻松"], 2, 0, "walking", "avoid_queues", False),
        ("family", 560.0, "2km-5km", "16:30", ["亲子", "低排队"], 2, 1, "auto", "avoid_queues", False),
        ("friends", 650.0, "2km-5km", "20:00", ["夜宵", "热闹"], 2, 0, "taxi", "accept_hot", True),
        ("family", 780.0, ">5km", "14:00", ["室外", "拍照"], 2, 1, "driving", "neutral", True),
        ("friends", 500.0, "<2km", "09:30", ["早午餐", "安静"], 2, 0, "walking", "neutral", False),
    ]

    for (
        group_type,
        budget,
        preferred_distance,
        time_period,
        activity_preferences,
        adult_count,
        child_count,
        commute_preference,
        queue_preference,
        include_gift,
    ) in templates:
        case: dict[str, Any] = {
            "group_type": group_type,
            "budget": float(budget),
            "preferred_distance": preferred_distance,
            "time_period": time_period,
            "duration_hours": base_duration,
            "activity_preferences": list(activity_preferences),
            "adult_count": int(adult_count),
            "child_count": int(child_count),
            "commute_preference": commute_preference,
            "queue_preference": queue_preference,
            "include_gift": bool(include_gift),
        }
        if group_type == "family" and child_count > 0:
            case["child_profiles"] = [("F", -1)] * child_count
        cases.append(case)

    return cases[:20]

