import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import ToolMessage

from closedloop.graph.tools.adjust_tool import _build_adjust_execute_update


class TestAdjustAndExecuteUpdate(unittest.TestCase):
    def test_success_should_keep_execute_confirmation_and_leave_fixup_agent(self):
        """补齐执行成功后，必须把 executed 状态写回前端可见 state。"""
        execute_message = ToolMessage(
            content='{"tool":"adjust_and_execute_plan_item","status":"success"}',
            tool_call_id="tool_1",
        )
        exec_update = {
            "current_step": "execute_itinerary",
            "confirmation": {"status": "executed", "execution_id": "exec_1"},
            "execution_report": {"status": "success"},
        }

        update = _build_adjust_execute_update(
            exec_update=exec_update,
            exec_status="success",
            execute_message=execute_message,
            new_plan={"plan_id": "plan_A"},
            updated_latest=[{"plan_id": "plan_A"}],
            updated_itinerary=[{"plan_id": "plan_A"}],
        )

        self.assertEqual(update["confirmation"]["status"], "executed")
        self.assertEqual(update["execution_report"]["status"], "success")
        self.assertEqual(update["active_agent"], "plan_agent")
        self.assertEqual(update["current_step"], "adjust_and_execute_plan_item")
        self.assertEqual(update["plan_option"]["plan_id"], "plan_A")
        self.assertEqual(update["itinerary"][0]["plan_id"], "plan_A")

    def test_needs_fixup_should_keep_execute_routing(self):
        """补齐后仍失败时，必须保留底层执行给出的 fixup 路由。"""
        execute_message = ToolMessage(
            content='{"tool":"adjust_and_execute_plan_item","status":"needs_fixup"}',
            tool_call_id="tool_1",
        )
        exec_update = {
            "current_step": "needs_fixup",
            "active_agent": "fixup_agent",
            "confirmation": {"status": "needs_fixup", "fixup": {"backup_candidates": []}},
        }

        update = _build_adjust_execute_update(
            exec_update=exec_update,
            exec_status="needs_fixup",
            execute_message=execute_message,
            new_plan={"plan_id": "plan_A"},
            updated_latest=[{"plan_id": "plan_A"}],
            updated_itinerary=None,
        )

        self.assertEqual(update["confirmation"]["status"], "needs_fixup")
        self.assertEqual(update["active_agent"], "fixup_agent")
        self.assertEqual(update["current_step"], "needs_fixup")


if __name__ == "__main__":
    unittest.main()
