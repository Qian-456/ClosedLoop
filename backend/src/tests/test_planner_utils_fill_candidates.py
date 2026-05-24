import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations


class TestPlannerUtilsFillCandidates(unittest.TestCase):
    def test_fill_candidates_when_patterns_ge_3_top1_duplicates(self):
        queues = {
            "activity": [
                {"package_id": "act_1", "name": "活动1", "duration_mins": 60, "score": 95, "price": 50.0, "location": {}},
                {"package_id": "act_2", "name": "活动2", "duration_mins": 60, "score": 85, "price": 60.0, "location": {}},
                {"package_id": "act_3", "name": "活动3", "duration_mins": 60, "score": 75, "price": 70.0, "location": {}},
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [
            {"pattern_id": "P1", "desc": "P1", "steps": ["activity"]},
            {"pattern_id": "P2", "desc": "P2", "steps": ["activity"]},
            {"pattern_id": "P3", "desc": "P3", "steps": ["activity"]},
        ]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(64.0, 64.0),
        )

        self.assertEqual(missing_types, set())
        self.assertGreaterEqual(valid_count, 3)
        self.assertGreaterEqual(len(plans), 3)
        sigs = {
            tuple(
                item.get("combo_id") or item.get("package_id") or item.get("gift_id", "unknown")
                for item in p.get("combo", [])
            )
            for p in plans
        }
        self.assertGreaterEqual(len(sigs), 3)


if __name__ == "__main__":
    unittest.main()

