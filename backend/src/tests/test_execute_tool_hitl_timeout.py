import asyncio
import unittest
from unittest.mock import patch


class TestExecuteToolHITLTimeout(unittest.TestCase):
    def test_resume_timeout_should_return_timeout_confirmation(self):
        from closedloop.graph.tools.execute_tool import execute_itinerary

        async def _run():
            state = {
                "constraints": {"time_period": "12:00"},
                "latest_plan_result": [
                    {
                        "plan_id": "plan_A",
                        "steps": [
                            {
                                "duration_minutes": 60,
                                "item": {
                                    "type": "restaurant",
                                    "id": "combo_main",
                                    "name": "主选餐厅",
                                    "backup_candidates": [
                                        {
                                            "id": "combo_backup",
                                            "name": "备选餐厅",
                                            "requires_confirmation": True,
                                            "violation_reason": "超出预算或时间",
                                        }
                                    ],
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

            hang_event = asyncio.Event()

            async def fake_iter_events(execution_id: str):
                yield {
                    "type": "item_update",
                    "data": {
                        "phase": "pending_user_confirmation",
                        "execution_id": execution_id,
                        "item_id": "combo_main",
                        "backup_id": "combo_backup",
                        "message": "主选无座，是否同意替换？",
                        "allowed_decisions": ["approve", "reject"],
                    },
                }
                await hang_event.wait()

            async def fake_submit_decision(**_kwargs):
                return True

            with patch(
                "closedloop.graph.tools.execute_tool.get_config", return_value=fake_config
            ):
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
                                "closedloop.graph.tools.execute_tool.submit_decision",
                                side_effect=fake_submit_decision,
                            ):
                                with patch(
                                    "closedloop.graph.tools.execute_tool.interrupt",
                                    return_value={"decisions": [{"type": "approve"}]},
                                ):
                                    cmd = await execute_itinerary.coroutine(
                                        plan_id="plan_A",
                                        tool_call_id="tool_call_1",
                                        state=state,
                                        book_commutes_policy="first_only",
                                    )

            update = getattr(cmd, "update", None) or {}
            confirmation = update.get("confirmation") or {}
            self.assertEqual(confirmation.get("status"), "timeout")
            execution_report = update.get("execution_report") or {}
            self.assertEqual(execution_report.get("status"), "timeout")
            self.assertIsInstance(execution_report.get("execution_summary"), dict)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
