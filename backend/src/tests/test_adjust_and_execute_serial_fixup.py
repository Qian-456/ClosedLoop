import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.adjust_tool import adjust_and_execute_plan_item


class TestAdjustAndExecuteSerialFixup(unittest.IsolatedAsyncioTestCase):
    async def test_should_reject_target_mismatch_without_repair_or_execute(self):
        """补齐阶段只能处理当前黄色卡 target，错 target 必须被确定性拒绝。"""
        state = {
            "confirmation": {
                "status": "needs_fixup",
                "fixup": {
                    "plan_id": "plan_A",
                    "target_item_id": "package_014_3",
                    "backup_candidates": [],
                },
            },
            "latest_plan_result": [{"plan_id": "plan_A"}],
        }

        with patch(
            "closedloop.graph.tools.adjust_tool.get_config",
            return_value=SimpleNamespace(TOOL_MAX_RUNTIME_SECS=3.0),
        ), patch("closedloop.graph.tools.adjust_tool.LoggerManager.setup"), patch(
            "closedloop.graph.tools.adjust_tool._do_adjust_plan_item"
        ) as mock_adjust, patch(
            "closedloop.graph.tools.adjust_tool._do_execute_itinerary", new_callable=AsyncMock
        ) as mock_execute:
            command = await adjust_and_execute_plan_item.ainvoke(
                {
                    "plan_id": "plan_A",
                    "target_item_id": "gift_011_6",
                    "new_item_id": "gift_011_1",
                    "tool_call_id": "call_1",
                    "state": state,
                    "config_runnable": {"configurable": {"thread_id": "thread-1"}},
                }
            )

        self.assertEqual(mock_adjust.call_count, 0)
        self.assertEqual(mock_execute.await_count, 0)
        self.assertEqual(command.update.get("active_agent"), "fixup_agent")
        self.assertEqual(command.update.get("current_step"), "needs_fixup")

        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertEqual(content.get("status"), "rejected")
        self.assertEqual(content.get("code"), "FIXUP_TARGET_MISMATCH")
        self.assertEqual(content.get("expected_target_item_id"), "package_014_3")
        self.assertEqual(content.get("actual_target_item_id"), "gift_011_6")

    async def test_should_persist_repaired_plan_when_execute_returns_next_fixup(self):
        """当前项 repair 成功但仍有下一项失败时，新 plan 必须成为后续可信基线。"""
        old_plan = {
            "plan_id": "plan_A",
            "steps": [
                {"item": {"id": "package_014_3", "type": "activity"}},
                {"item": {"id": "gift_011_6", "type": "gift_shop"}},
            ],
        }
        new_plan = {
            "plan_id": "plan_A",
            "steps": [
                {"item": {"id": "package_015_2", "type": "activity"}},
                {"item": {"id": "gift_011_6", "type": "gift_shop"}},
            ],
        }
        state = {
            "confirmation": {
                "status": "needs_fixup",
                "fixup": {
                    "plan_id": "plan_A",
                    "target_item_id": "package_014_3",
                    "backup_candidates": [],
                },
            },
            "plan_option": old_plan,
            "latest_plan_result": [old_plan],
            "itinerary": [old_plan],
            "constraints": {},
        }
        exec_update = {
            "current_step": "needs_fixup",
            "active_agent": "fixup_agent",
            "confirmation": {
                "status": "needs_fixup",
                "fixup": {
                    "plan_id": "plan_A",
                    "target_item_id": "gift_011_6",
                    "backup_candidates": [],
                },
            },
            "execution_report": {"status": "needs_fixup"},
        }

        with patch(
            "closedloop.graph.tools.adjust_tool.get_config",
            return_value=SimpleNamespace(TOOL_MAX_RUNTIME_SECS=3.0),
        ), patch("closedloop.graph.tools.adjust_tool.LoggerManager.setup"), patch(
            "closedloop.graph.tools.adjust_tool._do_adjust_plan_item",
            return_value=("success", {"plan": new_plan}, ""),
        ), patch(
            "closedloop.graph.tools.adjust_tool._do_execute_itinerary",
            new=AsyncMock(return_value=("needs_fixup", {"code": "NEEDS_FIXUP"}, exec_update)),
        ):
            command = await adjust_and_execute_plan_item.ainvoke(
                {
                    "plan_id": "plan_A",
                    "target_item_id": "package_014_3",
                    "new_item_id": "package_015_2",
                    "tool_call_id": "call_1",
                    "state": state,
                    "config_runnable": {"configurable": {"thread_id": "thread-1"}},
                }
            )

        self.assertEqual(command.update["confirmation"]["fixup"]["target_item_id"], "gift_011_6")
        self.assertEqual(command.update["plan_option"], new_plan)
        self.assertEqual(command.update["latest_plan_result"][0], new_plan)
        self.assertEqual(command.update["itinerary"][0], new_plan)


if __name__ == "__main__":
    unittest.main()
