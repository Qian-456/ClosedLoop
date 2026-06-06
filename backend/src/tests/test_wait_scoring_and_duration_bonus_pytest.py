"""
Pytest coverage for per-minute queue scoring and duration bonus rules.
"""

import pytest

from closedloop.contracts.state import Constraints
from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations
from closedloop.graph.plan_subgraph.rerank import score_item


def _build_constraints(queue_preference: str) -> Constraints:
    """
    Build minimal constraints for deterministic scoring tests.
    """
    return Constraints(
        group_type="friends",
        adult_count=1,
        child_count=0,
        child_profiles=[],
        budget=500.0,
        dietary_restrictions=[],
        preferred_distance="2km-5km",
        time_period="13:00",
        activity_preferences=[],
        queue_preference=queue_preference,
    )


@pytest.mark.parametrize(
    ("queue_preference", "expected_delta"),
    [
        ("avoid_queues", -30),
        ("neutral", -9),
        ("accept_hot", 6),
    ],
)
def test_queue_scoring_is_per_minute(queue_preference: str, expected_delta: int) -> None:
    """
    Queue scoring SHALL be linear per minute with fixed coefficients.
    """
    constraints = _build_constraints(queue_preference)
    item = {"id": "r1", "type": "restaurant", "rating": 4.0}
    inner_item = {"name": "单人套餐"}

    score_0 = score_item(item, inner_item, constraints, expected_wait_minutes=0)
    score_30 = score_item(item, inner_item, constraints, expected_wait_minutes=30)

    assert score_30 - score_0 == expected_delta


def test_activity_duration_bonus_includes_wait_minutes() -> None:
    """
    Activity duration bonus SHALL use (duration_mins + expected_wait_minutes).
    """
    constraints = _build_constraints("neutral")
    item = {"id": "a1", "type": "activity", "rating": 4.0}
    pkg = {"package_id": "p1", "name": "活动套餐", "duration_mins": 80}

    score_no_wait = score_item(item, pkg, constraints, expected_wait_minutes=0)
    score_with_wait = score_item(item, pkg, constraints, expected_wait_minutes=30)

    assert score_no_wait - score_with_wait == 24


def _compute_first_plan_average_score(expected_wait_minutes: int) -> float:
    queues = {
        "activity": [
            {
                "package_id": "p1",
                "venue_id": "v1",
                "name": "活动套餐",
                "price": 0.0,
                "score": 50,
                "duration_mins": 80,
                "expected_wait_minutes": expected_wait_minutes,
                "longitude": 0.0,
                "latitude": 0.0,
            }
        ]
    }
    patterns = [{"id": "pt1", "steps": ["activity"]}]

    plans, _, missing = generate_and_score_combinations(
        queues=queues,
        patterns=patterns,
        budget=1000.0,
        required_duration_range_mins=(0.0, 500.0),
        commute_preference="auto",
        start_time=0.0,
        constraints=None,
    )

    assert not missing
    assert plans
    return float(plans[0]["_sort_score"])


def test_planner_duration_bonus_includes_wait_minutes() -> None:
    """
    Planner average duration bonus SHALL use core (duration_mins + expected_wait_minutes) and exclude gifts/commutes.
    """
    avg_score_no_wait = _compute_first_plan_average_score(expected_wait_minutes=0)
    avg_score_with_wait = _compute_first_plan_average_score(expected_wait_minutes=30)

    assert avg_score_no_wait > avg_score_with_wait

