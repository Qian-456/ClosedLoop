import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import httpx

from langgraph.types import Command

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.plan_tool import plan_trip


class TestPlanTripTool(unittest.TestCase):
    @patch("closedloop.graph.tools.plan_tool.request_plan_sub_json")
    def test_plan_trip_invokes_subgraph_with_constraints(self, mock_request_plan_sub_json):
        """工具将结构化参数归一化为 constraints 后调用规划子图。"""
        mock_request_plan_sub_json.return_value = {
            "itinerary": {"status": "ok", "plans": []},
            "confirmation": {"status": "ok"},
        }

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch("closedloop.graph.tools.plan_tool.LoggerManager.setup"):
            out = plan_trip.func(
                group_type="friends",
                budget=500,
                time_period="18:00",
                duration_hours=[4.0, 6.0],
                state={"user_input": "情侣约会"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertIsInstance(out, Command)
        self.assertEqual(out.update["constraints"]["group_type"], "friends")
        self.assertEqual(out.update["constraints"]["duration_hours"], (4.0, 6.0))
        self.assertIn("itinerary", out.update)
        mock_request_plan_sub_json.assert_called_once()

    def test_plan_trip_defaults_are_normalized(self):
        """默认列表、人数、出行偏好可以被 Constraints 契约归一化。"""
        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch(
            "closedloop.graph.tools.plan_tool.request_plan_sub_json",
            return_value={"itinerary": {"status": "ok"}},
        ):
            out = plan_trip.func(
                group_type="friends",
                budget=200,
                time_period="14:00",
                state={"user_input": "和朋友下午随便逛逛"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertEqual(out.update["constraints"]["dietary_restrictions"], [])
        self.assertEqual(out.update["constraints"]["commute_preference"], "auto")
        self.assertEqual(out.update["constraints"]["adult_count"], 2)

    def test_plan_trip_child_profiles_accepts_pairs(self):
        """Ensures child_profiles uses pairs like [['F', 5], ['M', -1]] and is normalized."""
        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch(
            "closedloop.graph.tools.plan_tool.request_plan_sub_json",
            return_value={"itinerary": {"status": "ok"}},
        ):
            out = plan_trip.func(
                group_type="family",
                budget=600,
                time_period="14:00",
                adult_count=2,
                child_count=2,
                child_profiles=[["F", 5], ["M", -1]],
                state={"user_input": "带两个孩子，一个5岁，一个没说年龄"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertEqual(out.update["constraints"]["child_count"], 2)
        self.assertEqual(out.update["constraints"]["child_profiles"], [("F", 5), ("M", -1)])

    def test_plan_trip_child_profiles_pregnancy_is_u0(self):
        """Ensures pregnancy marker age=0 forces gender to U."""
        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch(
            "closedloop.graph.tools.plan_tool.request_plan_sub_json",
            return_value={"itinerary": {"status": "ok"}},
        ):
            out = plan_trip.func(
                group_type="family",
                budget=600,
                time_period="14:00",
                adult_count=2,
                child_count=1,
                child_profiles=[["F", 0]],
                state={"user_input": "孕妇一起去"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertEqual(out.update["constraints"]["child_count"], 1)
        self.assertEqual(out.update["constraints"]["child_profiles"], [("U", 0)])

    def test_plan_trip_handles_subgraph_error(self):
        """规划子图异常时返回 failed 结果。"""
        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch(
            "closedloop.graph.tools.plan_tool.request_plan_sub_json",
            side_effect=RuntimeError("boom"),
        ):
            out = plan_trip.func(
                group_type="friends",
                budget=300,
                time_period="14:00",
                state={"user_input": "朋友聚会"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertIn("规划子图调用失败", str(out.update["messages"][0].content))
        message_content = json.loads(out.update["messages"][0].content)
        self.assertEqual(message_content["status"], "failed")

    @patch("closedloop.graph.tools.plan_tool.logger")
    @patch("closedloop.graph.tools.plan_tool.request_plan_sub_json")
    def test_plan_trip_persists_candidates_to_state_update(
        self,
        mock_request_plan_sub_json,
        mock_logger,
    ):
        """规划成功时会把子图返回的 candidates 回写到主状态。"""
        mock_request_plan_sub_json.return_value = {
            "itinerary": {"status": "ok", "plans": [{"plan_id": "plan_1"}]},
            "candidates": {
                "ranked_dinner_combos": [{"combo_id": "combo_1"}],
                "ranked_packages": [{"package_id": "pkg_1"}],
                "ranked_gifts": [{"gift_id": "gift_1"}],
            },
        }

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
            ),
        ), patch("closedloop.graph.tools.plan_tool.LoggerManager.setup"):
            out = plan_trip.func(
                group_type="friends",
                budget=500,
                time_period="18:00",
                state={"user_input": "朋友聚餐"},
                config_runnable={"configurable": {"thread_id": "thread-2"}},
                tool_call_id="call_2",
            )

        self.assertEqual(out.update["candidates"], mock_request_plan_sub_json.return_value["candidates"])
        self.assertEqual(out.update["itinerary"], [{"plan_id": "plan_1"}])
        self.assertTrue(
            any(
                "restaurant_count=1" in str(call.args[0])
                and "activity_count=1" in str(call.args[0])
                and "gift_count=1" in str(call.args[0])
                for call in mock_logger.info.call_args_list
            )
        )

    @patch("closedloop.graph.tools.plan_tool.request_plan_sub_json")
    def test_plan_trip_returns_timeout_without_retry_when_transport_error(self, mock_request_plan_sub_json):
        """规划子图传输异常时，工具必须在单次调用内返回 timeout（不允许 sleep 重试超过 3 秒）。"""
        mock_request_plan_sub_json.side_effect = httpx.ConnectTimeout("timeout")

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
                TOOL_MAX_RUNTIME_SECS=3.0,
                TOOL_HTTP_TIMEOUT_SECS=3.0,
            ),
        ), patch("closedloop.graph.tools.plan_tool.LoggerManager.setup"):
            out = plan_trip.func(
                group_type="friends",
                budget=300,
                time_period="14:00",
                state={"user_input": "朋友聚会"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertIsInstance(out, Command)
        self.assertEqual(mock_request_plan_sub_json.call_count, 1)
        message_content = json.loads(out.update["messages"][0].content)
        self.assertEqual(message_content["status"], "timeout")
        self.assertIn("规划子图调用失败", message_content["result"]["error"])


if __name__ == "__main__":
    unittest.main()
