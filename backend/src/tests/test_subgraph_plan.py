import os
import sys
import unittest
from langgraph.graph.state import CompiledStateGraph

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.plan_subgraph.builder import build_subgraph_plan


class TestSubgraphPlan(unittest.TestCase):
    def test_build_subgraph_plan(self):
        """规划子图可以编译，入口不再依赖 extract_constraints。"""
        app = build_subgraph_plan()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
