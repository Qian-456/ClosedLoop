import unittest
import json
from unittest.mock import patch


class TestAdjustPlanItemRespectsExecutionReport(unittest.TestCase):
    @patch("closedloop.graph.tools.adjust_tool.repair_plan")
    def test_adjust_plan_item_should_reject_when_target_already_executed(self, mock_repair_plan):
        from closedloop.graph.tools.adjust_tool import adjust_plan_item

        mock_repair_plan.return_value = {"status": "success", "plan": {"plan_id": "p1", "steps": []}}

        state = {
            "latest_plan_result": [{"plan_id": "p1"}],
            "candidates": {"ranked_packages": [{"package_id": "new1"}]},
            "constraints": {"budget": 500, "duration_hours": [4.0, 6.0]},
            "execution_report": {
                "execution_summary": {
                    "items": [
                        {
                            "item_id": "old1",
                            "item_type": "activity",
                            "reserved": True,
                            "replaced": False,
                        }
                    ]
                }
            },
        }

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

        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertIn("error", content)
        self.assertEqual(mock_repair_plan.call_count, 0)


if __name__ == "__main__":
    unittest.main()

