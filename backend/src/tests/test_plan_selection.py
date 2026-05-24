import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.plan_subgraph.planner import _select_top_k_diverse_plans


class TestPlanSelection(unittest.TestCase):
    def test_select_top_k_diverse_plans(self):
        plans = [
            {"average_score": 60.0, "combo": [{"id": "p1"}]},
            {"average_score": 85.0, "combo": [{"id": "p2"}]},
            {"average_score": 95.0, "combo": [{"id": "p2_alt"}]},
            {"average_score": 90.0, "combo": [{"id": "p3"}]},
        ]

        selected = _select_top_k_diverse_plans(plans, 2, [])
        self.assertEqual(len(selected), 2)
        # Should pick the highest score
        self.assertEqual(selected[0]["combo"][0]["id"], "p2_alt")
        self.assertEqual(selected[1]["combo"][0]["id"], "p3")

if __name__ == "__main__":
    unittest.main()
