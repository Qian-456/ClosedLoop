import os
import sys
import unittest
from unittest.mock import patch

from langgraph.types import Command

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.plan_tool import plan_trip


class _DummySubgraph:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error
        self.state = None

    def invoke(self, state):
        self.state = state
        if self.error:
            raise self.error
        return self.value


class TestPlanTripTool(unittest.TestCase):
    def test_plan_trip_invokes_subgraph_with_constraints(self):
        """工具将结构化参数归一化为 constraints 后调用规划子图。"""
        subgraph = _DummySubgraph(
            value={
                "itinerary": {"status": "ok", "plans": []},
                "confirmation": {"status": "ok"},
            }
        )

        with patch("closedloop.graph.tools.plan_tool.get_config"), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("closedloop.graph.tools.plan_tool.build_subgraph_plan", return_value=subgraph):
            out = plan_trip.func(
                group_type="couple",
                budget=500,
                time_period="18:00",
                duration_hours=[4.0, 6.0],
                state={"user_input": "情侣约会"},
                tool_call_id="call_1",
            )

        self.assertIsInstance(out, Command)
        self.assertEqual(out.update["constraints"]["group_type"], "couple")
        self.assertEqual(out.update["constraints"]["duration_hours"], (4.0, 6.0))
        self.assertEqual(subgraph.state["constraints"]["budget"], 500.0)
        self.assertEqual(out.update["itinerary"]["status"], "ok")

    def test_plan_trip_defaults_are_normalized(self):
        """默认列表、人数、出行偏好可以被 Constraints 契约归一化。"""
        subgraph = _DummySubgraph(value={"itinerary": {"status": "ok"}})

        with patch("closedloop.graph.tools.plan_tool.get_config"), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("closedloop.graph.tools.plan_tool.build_subgraph_plan", return_value=subgraph):
            out = plan_trip.func(
                group_type="solo",
                budget=200,
                time_period="14:00",
                state={"user_input": "一个人下午随便逛逛"},
                tool_call_id="call_1",
            )

        self.assertEqual(out.update["constraints"]["dietary_restrictions"], [])
        self.assertEqual(out.update["constraints"]["commute_preference"], "auto")
        self.assertEqual(out.update["constraints"]["adult_count"], 2)

    def test_plan_trip_handles_subgraph_error(self):
        """规划子图异常时返回 failed 结果。"""
        subgraph = _DummySubgraph(error=RuntimeError("boom"))

        with patch("closedloop.graph.tools.plan_tool.get_config"), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("closedloop.graph.tools.plan_tool.build_subgraph_plan", return_value=subgraph):
            out = plan_trip.func(
                group_type="friends",
                budget=300,
                time_period="14:00",
                state={"user_input": "朋友聚会"},
                tool_call_id="call_1",
            )

        self.assertEqual(out.update["latest_plan_result"]["error"], "规划子图调用失败")


if __name__ == "__main__":
    unittest.main()
