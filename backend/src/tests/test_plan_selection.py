import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.nodes.planner import _select_three_plans


class TestPlanSelection(unittest.TestCase):
    def test_select_three_plans_semantics(self):
        plans = [
            {"total_cost": 100.0, "average_score": 60.0, "combo": [{"id": "a"}]},
            {"total_cost": 300.0, "average_score": 99.0, "combo": [{"id": "b"}]},
            {"total_cost": 500.0, "average_score": 80.0, "combo": [{"id": "c"}]},
            {"total_cost": 120.0, "average_score": 90.0, "combo": [{"id": "d"}]},
        ]

        selected = _select_three_plans(plans)

        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[0]["total_cost"], 100.0)
        self.assertEqual(selected[1]["average_score"], 99.0)
        self.assertEqual(selected[2]["total_cost"], 500.0)


if __name__ == "__main__":
    unittest.main()

