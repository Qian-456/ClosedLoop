import unittest
import sys
import os
 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
 
from closedloop.graph.nodes.planner_utils import generate_and_score_combinations
 
 
class TestPlannerUtilsSelection(unittest.TestCase):
    def test_plan1_plan2_plan3_selection_from_candidate_pool(self):
        queues = {
            "activity": [
                {"package_id": "act_low", "name": "低价活动", "duration_mins": 60, "score": 60, "price": 50.0, "location": {}},
                {"package_id": "act_highscore", "name": "高分活动", "duration_mins": 60, "score": 95, "price": 100.0, "location": {}},
                {"package_id": "act_highcost", "name": "高价活动", "duration_mins": 60, "score": 70, "price": 200.0, "location": {}},
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity"]}]
 
        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=300.0,
            required_duration_mins=64.0,
        )
 
        self.assertGreater(valid_count, 0)
        self.assertEqual(missing_types, set())
        self.assertEqual(len(plans), 3)
 
        self.assertEqual(plans[0]["combo"][0]["package_id"], "act_low")
        self.assertEqual(plans[1]["combo"][0]["package_id"], "act_highcost")
        self.assertEqual(plans[2]["combo"][0]["package_id"], "act_highscore")

    def test_commute_cost_rounded_two_decimals(self):
        queues = {
            "activity": [
                {
                    "package_id": "act_1",
                    "name": "测试活动",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 3.333, "latitude": 0.0},
                }
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_mins=92.0,
        )

        self.assertGreater(valid_count, 0)
        self.assertEqual(missing_types, set())
        self.assertGreaterEqual(len(plans), 1)

        plan = plans[0]
        self.assertEqual(plan["commutes"][0]["cost"], 10.67)
        self.assertEqual(plan["commutes"][-1]["cost"], 10.67)
 
 
if __name__ == "__main__":
    unittest.main()
