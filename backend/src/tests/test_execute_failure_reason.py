import asyncio
import unittest
from unittest.mock import patch


class TestExecuteFailureReason(unittest.TestCase):
    def test_forced_out_of_stock_should_surface_stock_reason_for_fixup(self):
        """强制缺货应在 ToolMessage/confirmation 中明确标记为库存不足。"""
        from closedloop.graph.tools.execute_tool import execute_itinerary

        async def _run():
            state = {
                "constraints": {"time_period": "12:00"},
                "latest_plan_result": [
                    {
                        "plan_id": "plan_A",
                        "total_cost": 88.0,
                        "steps": [
                            {
                                "duration_minutes": 10,
                                "start_time": "13:00",
                                "item": {
                                    "type": "gift_shop",
                                    "id": "gift_1",
                                    "name": "益智拼图",
                                    "cost": 88.0,
                                    "gift_price": 78.0,
                                    "delivery_fee": 10.0,
                                    "backup_candidates": [],
                                    "replacement_policy": "equivalent_only",
                                    "user_touched": False,
                                },
                            }
                        ],
                    }
                ],
            }

            fake_config = type(
                "FakeConfig",
                (),
                {
                    "HITL_RESUME_HEARTBEAT_SECS": 0.01,
                    "HITL_RESUME_MAX_WAIT_SECS": 0.05,
                    "TOOL_MAX_RUNTIME_SECS": 3.0,
                    "TOOL_HTTP_TIMEOUT_SECS": 3.0,
                    "data": type("Data", (), {})(),
                    "logging": type("Logging", (), {})(),
                },
            )()

            async def fake_start_execution(_req):
                return "exe_test_1"

            async def fake_iter_events(execution_id: str):
                yield {
                    "type": "item_update",
                    "data": {
                        "phase": "done",
                        "execution_id": execution_id,
                        "item_id": "gift_1",
                        "item_type": "gift_shop",
                        "reserved": False,
                        "delivery_time": "12:50",
                        "detail": {
                            "forced_out_of_stock": True,
                            "delivery_time": "12:50",
                        },
                    },
                }
                yield {"type": "done", "data": {"execution_id": execution_id, "status": "ok"}}

            with patch("closedloop.graph.tools.execute_tool.get_config", return_value=fake_config):
                with patch("closedloop.graph.tools.execute_tool.LoggerManager.setup", return_value=None):
                    with patch(
                        "closedloop.graph.tools.execute_tool.start_execution",
                        side_effect=fake_start_execution,
                    ):
                        with patch(
                            "closedloop.graph.tools.execute_tool.iter_events",
                            side_effect=fake_iter_events,
                        ):
                            with patch(
                                "closedloop.graph.tools.execute_tool._snapshot_runtime_jsons",
                                return_value={},
                            ):
                                with patch(
                                    "closedloop.graph.tools.execute_tool._restore_runtime_jsons",
                                    return_value=None,
                                ):
                                    cmd = await execute_itinerary.coroutine(
                                        plan_id="plan_A",
                                        tool_call_id="tool_call_1",
                                        state=state,
                                        book_commutes_policy="first_only",
                                    )

            update = getattr(cmd, "update", None) or {}
            confirmation = update.get("confirmation") or {}
            self.assertEqual(confirmation.get("status"), "needs_fixup")
            self.assertEqual(confirmation.get("fixup", {}).get("reason"), "库存不足")

            execution_summary = (update.get("execution_report") or {}).get("execution_summary") or {}
            failures = execution_summary.get("failures") or []
            self.assertEqual(failures[0].get("reason_code"), "out_of_stock")
            self.assertEqual(failures[0].get("reason_text"), "库存不足")
            self.assertEqual(failures[0].get("delivery_time"), "12:50")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
