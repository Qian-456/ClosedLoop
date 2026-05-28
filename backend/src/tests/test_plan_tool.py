import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import httpx

from langgraph.types import Command

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.plan_tool import plan_trip


class TestPlanTripTool(unittest.TestCase):
    def test_plan_trip_invokes_subgraph_with_constraints(self):
        """工具将结构化参数归一化为 constraints 后通过 httpx 调用规划子图。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "itinerary": {"status": "ok", "plans": []},
            "confirmation": {"status": "ok"},
        }
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.request.return_value = mock_response

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(PLAN_SUB_API_URL="http://localhost:8001/plan"),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("httpx.Client", return_value=mock_client):
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
        mock_client.request.assert_called_once()

    def test_plan_trip_defaults_are_normalized(self):
        """默认列表、人数、出行偏好可以被 Constraints 契约归一化。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"itinerary": {"status": "ok"}}
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.request.return_value = mock_response

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(PLAN_SUB_API_URL="http://localhost:8001/plan"),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("httpx.Client", return_value=mock_client):
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
        mock_response = MagicMock()
        mock_response.json.return_value = {"itinerary": {"status": "ok"}}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.request.return_value = mock_response

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(PLAN_SUB_API_URL="http://localhost:8001/plan"),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("httpx.Client", return_value=mock_client):
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
        mock_response = MagicMock()
        mock_response.json.return_value = {"itinerary": {"status": "ok"}}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.request.return_value = mock_response

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(PLAN_SUB_API_URL="http://localhost:8001/plan"),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("httpx.Client", return_value=mock_client):
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
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.request.side_effect = RuntimeError("boom")

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(PLAN_SUB_API_URL="http://localhost:8001/plan"),
        ), patch(
            "closedloop.graph.tools.plan_tool.LoggerManager.setup"
        ), patch("httpx.Client", return_value=mock_client):
            out = plan_trip.func(
                group_type="friends",
                budget=300,
                time_period="14:00",
                state={"user_input": "朋友聚会"},
                config_runnable={"configurable": {"thread_id": "test_thread"}},
                tool_call_id="call_1",
            )

        self.assertIn("规划子图调用失败", str(out.update["messages"][0].content))

    @patch("closedloop.graph.tools.plan_tool.time.sleep")
    @patch("closedloop.graph.tools.plan_tool.request_plan_sub_json")
    def test_plan_trip_uses_longer_timeout_and_only_retries_on_transport_error(
        self,
        mock_request_plan_sub_json,
        mock_sleep,
    ):
        """规划请求应使用放宽后的 timeout，并且仅在传输类错误下重试。"""
        mock_request_plan_sub_json.side_effect = [
            httpx.ConnectTimeout("timeout"),
            {"itinerary": {"status": "ok", "plans": []}},
        ]

        with patch(
            "closedloop.graph.tools.plan_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
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
        self.assertEqual(mock_request_plan_sub_json.call_count, 2)
        self.assertEqual(mock_request_plan_sub_json.call_args_list[0].kwargs["timeout"], 10.0)
        self.assertEqual(mock_request_plan_sub_json.call_args_list[1].kwargs["timeout"], 10.0)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
