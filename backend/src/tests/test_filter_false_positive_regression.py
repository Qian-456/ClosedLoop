import unittest

from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.plan_subgraph.retrieve import retrieve_candidates_node, filter_node, _apply_filters_with_events


class TestFilterFalsePositiveRegression(unittest.TestCase):
    def _base_constraints(self) -> Constraints:
        return Constraints(
            group_type="family",
            budget=600.0,
            dietary_restrictions=["海鲜"],
            preferred_distance="2km-5km",
            time_period="13:00-19:00",
            duration_hours=(4.0, 6.0),
            activity_preferences=["亲子", "室内"],
            adult_count=2,
            child_count=1,
            adult_genders=["F", "M"],
            child_profiles=[("F", 5)],
            commute_preference="taxi",
        )

    def test_filter_node_family_child_activity_kept_count_not_too_low(self):
        constraints = self._base_constraints()
        state = ClosedLoopState(user_input="x", constraints=constraints)
        state = retrieve_candidates_node(state)
        state = filter_node(state)
        activities = state["candidates"]["nearby_activities"]
        self.assertGreaterEqual(len(activities), 5)

    def test_age_range_mismatch_is_soft_kept_and_marked(self):
        constraints = self._base_constraints()
        activity = {
            "id": "a_soft_age",
            "type": "activity",
            "distance_km": 3.0,
            "open_time": "10:00",
            "close_time": "23:00",
            "suitable_groups": ["family"],
            "age_range": ["adult"],
            "tags": ["亲子", "室内"],
            "packages": [
                {"package_id": "p1", "name": "2大1小亲子票", "price": 100.0},
            ],
        }
        filtered, events, _ = _apply_filters_with_events(
            [activity], constraints, category="nearby_activities"
        )
        self.assertEqual(len(filtered), 1)
        self.assertTrue(filtered[0].get("age_range_mismatch_for_children"))
        self.assertTrue(
            any(e.get("reason_code") == "activity_age_range_mismatch" for e in events)
        )

    def test_distance_soft_threshold_allows_6km_for_2_to_5km_preference(self):
        constraints = self._base_constraints()
        activity = {
            "id": "a_soft_dist",
            "type": "activity",
            "distance_km": 6.6,
            "open_time": "10:00",
            "close_time": "23:00",
            "suitable_groups": ["family"],
            "age_range": ["3-6"],
            "tags": ["亲子", "室内"],
            "packages": [
                {"package_id": "p1", "name": "2大1小亲子票", "price": 100.0},
            ],
        }
        filtered, events, _ = _apply_filters_with_events(
            [activity], constraints, category="nearby_activities"
        )
        self.assertEqual(len(filtered), 1)
        self.assertFalse(any(e.get("reason_code") == "distance_over_max" for e in events))


if __name__ == "__main__":
    unittest.main()

