import os
import sys
import unittest
from langgraph.graph.state import CompiledStateGraph

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.agent import agent


class TestAgent(unittest.TestCase):
    def test_agent_is_compiled_state_graph(self):
        """测试 agent 导出了一个 CompiledStateGraph 实例。"""
        self.assertIsInstance(agent, CompiledStateGraph)


if __name__ == "__main__":
    unittest.main()
