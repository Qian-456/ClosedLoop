import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.agent import (
    PLAN_AGENT_SYSTEM_PROMPT,
    EXECUTE_AGENT_SYSTEM_PROMPT,
    FIXUP_AGENT_SYSTEM_PROMPT,
    resolve_active_agent,
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

    def test_resolve_active_agent_should_prioritize_needs_fixup(self):
        """当 confirmation.status=needs_fixup 时，必须优先切到 fixup_agent。"""
        state = {
            "active_agent": "execute_agent",
            "confirmation": {"status": "needs_fixup"},
        }
        self.assertEqual(resolve_active_agent(state), "fixup_agent")

    def test_fixup_prompt_should_require_adjust_and_execute_and_no_second_confirm(self):
        self.assertIn("adjust_and_execute_plan_item", FIXUP_AGENT_SYSTEM_PROMPT)
        self.assertNotIn("adjust_plan_item", FIXUP_AGENT_SYSTEM_PROMPT)
        self.assertIn("中途禁止再问用户确认", FIXUP_AGENT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
