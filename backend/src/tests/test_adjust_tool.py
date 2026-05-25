import unittest
import json
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

if __name__ == '__main__':
    unittest.main()
