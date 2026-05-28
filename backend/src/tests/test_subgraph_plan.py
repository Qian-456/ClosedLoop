import os
import sys
import unittest
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import get_type_hints

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.plan_subgraph.builder import PlanSubgraphOutput, build_subgraph_plan


class TestSubgraphPlan(unittest.TestCase):
    def test_build_subgraph_plan(self):
        """规划子图可以编译，入口不再依赖 extract_constraints。"""
        app = build_subgraph_plan()
        self.assertIsNotNone(app)

    def test_plan_subgraph_output_includes_candidates(self):
        """规划子图输出契约必须显式包含 candidates，避免结果被 output_schema 裁掉。"""
        hints = get_type_hints(PlanSubgraphOutput, include_extras=True)
        self.assertIn("itinerary", hints)
        self.assertIn("candidates", hints)


if __name__ == "__main__":
    unittest.main()
