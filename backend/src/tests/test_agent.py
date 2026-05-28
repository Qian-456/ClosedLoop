import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.agent import (
    PLAN_AGENT_SYSTEM_PROMPT,
    EXECUTE_AGENT_SYSTEM_PROMPT,
    build_agent_with_async_checkpointer,
)


class TestAgent(unittest.TestCase):
    def test_graph_builder_is_callable(self):
        """测试 graph builder 存在且可调用。"""
        self.assertTrue(callable(build_agent_with_async_checkpointer))

    def test_plan_agent_prompt_is_non_empty(self):
        """测试规划 Agent prompt 非空。"""
        self.assertTrue(isinstance(PLAN_AGENT_SYSTEM_PROMPT, str) and PLAN_AGENT_SYSTEM_PROMPT.strip())

    def test_execute_agent_prompt_is_non_empty(self):
        """测试执行 Agent prompt 非空。"""
        self.assertTrue(isinstance(EXECUTE_AGENT_SYSTEM_PROMPT, str) and EXECUTE_AGENT_SYSTEM_PROMPT.strip())

    def test_plan_agent_prompt_contains_preferred_distance_rule(self):
        """测试规划 Agent prompt 包含 preferred_distance 的归一化口径。"""
        self.assertIn("preferred_distance", PLAN_AGENT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
