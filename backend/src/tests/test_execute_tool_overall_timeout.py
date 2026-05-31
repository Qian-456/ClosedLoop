import asyncio
import unittest
from unittest.mock import patch


class TestExecuteToolOverallTimeout(unittest.TestCase):
    def test_execute_itinerary_should_timeout_within_tool_budget(self):
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
                    "HITL_RESUME_MAX_WAIT_SECS": 3.0,
                    "TOOL_MAX_RUNTIME_SECS": 0.05,
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
                    "type": "execution_update",
                    "data": {
                        "phase": "checking",
                        "execution_id": execution_id,
                        "message": "checking",
                    },
                }
                await hang_event.wait()

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
                            cmd = await execute_itinerary.coroutine(
                                plan_id="plan_A",
                                tool_call_id="tool_call_1",
                                state=state,
                                book_commutes_policy="first_only",
                            )

            update = getattr(cmd, "update", None) or {}
            confirmation = update.get("confirmation") or {}
            self.assertEqual(confirmation.get("status"), "timeout")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

