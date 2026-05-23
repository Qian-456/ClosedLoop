import os
import sys
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import HumanMessage, SystemMessage

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.nodes.plan_agent import plan_agent_node
from closedloop.graph.tools.plan_tool import plan_trip


class _DummyAgent:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error
        self.payload = None

    def invoke(self, payload):
        self.payload = payload
        if self.error:
            raise self.error
        return self.value


class TestPlanAgentNode(unittest.TestCase):
    def test_plan_agent_node_invokes_agent_with_plan_tool(self):
        """planner agent 从 user_input 构造消息，并绑定 plan_trip 工具。"""
        agent = _DummyAgent(
            value={
                "constraints": {"group_type": "couple", "budget": 500, "time_period": "18:00"},
                "latest_plan_result": {"itinerary": {"status": "ok"}},
                "itinerary": {"status": "ok"},
            }
        )

        with patch("closedloop.graph.nodes.plan_agent.get_config"), patch(
            "closedloop.graph.nodes.plan_agent.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.plan_agent.build_agent", return_value=agent) as mock_build:
            out = plan_agent_node({"user_input": "晚上情侣约会，预算500"})

        mock_build.assert_called_once()
        self.assertEqual(mock_build.call_args.kwargs["tools"], [plan_trip])
        self.assertEqual(out["current_step"], "plan_agent_node")
        self.assertEqual(out["itinerary"]["status"], "ok")
        self.assertEqual(agent.payload["user_input"], "晚上情侣约会，预算500")
        self.assertIsInstance(agent.payload["messages"][0], SystemMessage)
        self.assertIsInstance(agent.payload["messages"][1], HumanMessage)

    def test_plan_agent_node_handles_agent_error(self):
        """Agent 调用失败时写入 latest_plan_result。"""
        agent = _DummyAgent(error=RuntimeError("boom"))

        with patch("closedloop.graph.nodes.plan_agent.get_config"), patch(
            "closedloop.graph.nodes.plan_agent.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.plan_agent.build_agent", return_value=agent):
            out = plan_agent_node({"user_input": "帮我安排下午活动"})

        self.assertEqual(out["current_step"], "plan_agent_node")
        self.assertIn("error", out["latest_plan_result"])

    def test_plan_agent_node_missing_user_input(self):
        """缺少用户输入时不构建 Agent。"""
        mock_build = Mock()

        with patch("closedloop.graph.nodes.plan_agent.get_config"), patch(
            "closedloop.graph.nodes.plan_agent.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.plan_agent.build_agent", mock_build):
            out = plan_agent_node({"user_input": ""})

        mock_build.assert_not_called()
        self.assertIn("error", out["latest_plan_result"])


if __name__ == "__main__":
    unittest.main()
