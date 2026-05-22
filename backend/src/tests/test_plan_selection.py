import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.nodes.planner import _select_three_plans


class TestPlanSelection(unittest.TestCase):
    def test_select_three_plans_decoy_gentle(self):
        plans = [
            {"total_cost": 100.0, "experience_score": 60.0, "combo": [{"id": "p1"}]},
            {"total_cost": 130.0, "experience_score": 85.0, "combo": [{"id": "p2"}]},
            {"total_cost": 160.0, "experience_score": 95.0, "combo": [{"id": "p2_alt"}]},
            {"total_cost": 220.0, "experience_score": 90.0, "combo": [{"id": "p3"}]},
        ]

        selected = _select_three_plans(plans)

        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[0]["combo"][0]["id"], "p1")
        self.assertEqual(selected[1]["combo"][0]["id"], "p2")
        self.assertEqual(selected[2]["combo"][0]["id"], "p3")

    def test_select_three_plans_never_puts_most_expensive_in_middle(self):
        plans = [
            {"total_cost": 100.0, "experience_score": 60.0, "combo": [{"id": "p1"}]},
            {"total_cost": 200.0, "experience_score": 70.0, "combo": [{"id": "p2"}]},
            {"total_cost": 220.0, "experience_score": 90.0, "combo": [{"id": "p3"}]},
        ]

        selected = _select_three_plans(plans)

        self.assertEqual(len(selected), 3)
        costs = [p["total_cost"] for p in selected]
        self.assertTrue(costs[0] <= costs[1] <= costs[2])
        self.assertEqual(selected[0]["combo"][0]["id"], "p1")
        self.assertEqual(selected[1]["combo"][0]["id"], "p2")
        self.assertEqual(selected[2]["combo"][0]["id"], "p3")


if __name__ == "__main__":
    unittest.main()
