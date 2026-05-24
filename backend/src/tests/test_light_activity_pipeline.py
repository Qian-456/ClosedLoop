import unittest

from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.plan_subgraph.rerank import rerank_node
from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations


class TestLightActivityPipeline(unittest.TestCase):
    def test_rerank_splits_light_and_normal_packages(self):
        constraints = Constraints(
            group_type="family",
            adult_count=2,
            child_count=1,
            child_profiles=[("F", 5)],
            budget=500.0,
            dietary_restrictions=[],
            preferred_distance="2km-5km",
            time_period="13:00",
            activity_preferences=[],
        )

        act = {
            "id": "a1",
            "type": "activity",
            "name": "活动场地",
            "rating": 4.6,
            "distance_km": 3.0,
            "tags": [],
            "suitable_groups": ["family"],
            "location": {"address": "x"},
            "packages": [
                {"package_id": "p_light", "name": "轻玩套餐", "price": 10.0, "duration_mins": 60},
                {"package_id": "p_play", "name": "玩套餐", "price": 10.0, "duration_mins": 90},
            ],
        }

        state = ClosedLoopState(
            user_input="x",
            constraints=constraints,
            candidates={
                "nearby_restaurants": [],
                "nearby_activities": [act],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node", "filter_node"],
            },
        )

        new_state = rerank_node(state)
        cand = new_state["candidates"]
        light_ids = [p["package_id"] for p in cand["ranked_light_packages"]]
        play_ids = [p["package_id"] for p in cand["ranked_packages"]]
        self.assertEqual(light_ids, ["p_light"])
        self.assertEqual(play_ids, ["p_play"])

    def test_planner_utils_consumes_activity_light(self):
        queues = {
            "activity": [],
            "activity_light": [
                {"package_id": "p_light", "name": "轻玩套餐", "duration_mins": 60, "score": 80, "price": 10.0, "location": {}},
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"id": "P_LIGHT", "desc": "轻玩", "steps": ["activity_light"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(70.0, 70.0),
        )
        self.assertEqual(missing_types, set())
        self.assertGreaterEqual(valid_count, 1)
        self.assertGreaterEqual(len(plans), 1)


if __name__ == "__main__":
    unittest.main()

