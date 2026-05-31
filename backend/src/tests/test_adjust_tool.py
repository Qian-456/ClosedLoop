import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from closedloop.graph.tools.adjust_tool import adjust_plan_item

class TestAdjustTool(unittest.TestCase):
    @patch('closedloop.graph.tools.adjust_tool.repair_plan')
    def test_adjust_plan_item_success(self, mock_repair_plan):
        mock_repair_plan.return_value = {
            "status": "success",
            "plan": {"plan_id": "p1", "steps": []}
        }
        
        state = {
            "latest_plan_result": [{"plan_id": "p1"}],
            "candidates": {
                "ranked_packages": [{"package_id": "new1"}]
            },
            "constraints": {
                "budget": 500,
                "duration_hours": [4.0, 6.0]
            }
        }
        
        command = adjust_plan_item.invoke({
            "plan_id": "p1",
            "target_item_id": "old1",
            "new_item_id": "new1",
            "tool_call_id": "call_123",
            "state": state
        })
        
        self.assertIsNotNone(command)
        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertEqual(content["status"], "success")
        
        # Verify it updates latest_plan_result
        self.assertEqual(command.update["latest_plan_result"][0]["plan_id"], "p1")

    def test_adjust_plan_item_not_found(self):
        state = {
            "latest_plan_result": [{"plan_id": "p2"}]
        }
        
        command = adjust_plan_item.invoke({
            "plan_id": "p1",
            "target_item_id": "old1",
            "new_item_id": "new1",
            "tool_call_id": "call_123",
            "state": state
        })
        
        messages = command.update.get("messages", [])
        content = json.loads(messages[0].content)
        self.assertIn("error", content)

    @patch("closedloop.graph.tools.adjust_tool.request_plan_sub_json")
    def test_adjust_plan_item_item_api_timeout_should_use_tool_http_timeout(self, mock_request_plan_sub_json):
        mock_request_plan_sub_json.side_effect = RuntimeError("boom")

        state = {
            "latest_plan_result": [{"plan_id": "p1"}],
            "candidates": {},
            "constraints": {"budget": 500, "duration_hours": [4.0, 6.0]},
        }

        with patch(
            "closedloop.graph.tools.adjust_tool.get_config",
            return_value=SimpleNamespace(
                PLAN_SUB_API_URL="http://localhost:8001/plan",
                PLAN_SUB_NETWORK_MODE="local",
                TOOL_HTTP_TIMEOUT_SECS=3.0,
                TOOL_MAX_RUNTIME_SECS=3.0,
            ),
        ), patch("closedloop.graph.tools.adjust_tool.LoggerManager.setup"):
            command = adjust_plan_item.invoke(
                {
                    "plan_id": "p1",
                    "target_item_id": "old1",
                    "new_item_id": "new1",
                    "tool_call_id": "call_123",
                    "state": state,
                    "config_runnable": {"configurable": {"thread_id": "thread-1"}},
                }
            )

        self.assertEqual(mock_request_plan_sub_json.call_args.kwargs.get("timeout"), 3.0)
        messages = command.update.get("messages", [])
        content = json.loads(messages[0].content)
        self.assertIn("error", content)

if __name__ == '__main__':
    unittest.main()
