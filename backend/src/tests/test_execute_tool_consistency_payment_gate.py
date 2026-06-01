import asyncio
import unittest
from unittest.mock import patch


class TestExecuteToolConsistencyPaymentGate(unittest.TestCase):
    def test_execute_itinerary_should_turn_to_needs_fixup_when_has_failures(self):
        from closedloop.graph.tools.execute_tool import execute_itinerary

        async def _run():
            state = {
                "constraints": {"time_period": "12:00"},
                "latest_plan_result": [
                    {
                        "plan_id": "plan_A",
                        "total_cost": 100.0,
                        "steps": [
                            {
                                "duration_minutes": 60,
                                "item": {
                                    "type": "restaurant",
                                    "id": "combo_main",
                                    "name": "主选餐厅",
                                    "cost": 88.0,
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
                        "item_id": "combo_main",
                        "item_type": "restaurant",
                        "reserved": False,
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
            self.assertEqual(update.get("active_agent"), "fixup_agent")
            self.assertEqual(update.get("current_step"), "needs_fixup")

        asyncio.run(_run())

    def test_execute_itinerary_should_fail_inconsistency_when_overpay(self):
        from closedloop.graph.tools.execute_tool import execute_itinerary

        async def _run():
            state = {
                "constraints": {"time_period": "12:00"},
                "latest_plan_result": [
                    {
                        "plan_id": "plan_A",
                        "total_cost": 10.0,
                        "steps": [
                            {
                                "duration_minutes": 60,
                                "item": {
                                    "type": "restaurant",
                                    "id": "combo_main",
                                    "name": "主选餐厅",
                                    "cost": 1000.0,
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
                        "item_id": "combo_main",
                        "item_type": "restaurant",
                        "reserved": True,
                    },
                }
                yield {"type": "done", "data": {"execution_id": execution_id, "status": "ok"}}

            restore_called = {"ok": False}

            def fake_restore(_rw_dir: str, _snapshot: dict):
                restore_called["ok"] = True

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
                                    side_effect=fake_restore,
                                ):
                                    cmd = await execute_itinerary.coroutine(
                                        plan_id="plan_A",
                                        tool_call_id="tool_call_1",
                                        state=state,
                                        book_commutes_policy="first_only",
                                    )

            update = getattr(cmd, "update", None) or {}
            confirmation = update.get("confirmation") or {}
            self.assertEqual(confirmation.get("code"), "EXECUTION_INCONSISTENT_NEEDS_RETRY")
            self.assertTrue(restore_called["ok"])

        asyncio.run(_run())

    def test_execute_itinerary_should_compare_executable_cost_without_commute_total(self):
        """方案总价含通勤时，执行对账只比较实际预订项目费用。"""
        from closedloop.graph.tools.execute_tool import execute_itinerary

        async def _run():
            state = {
                "constraints": {"time_period": "12:00"},
                "latest_plan_result": [
                    {
                        "plan_id": "plan_A",
                        "total_cost": 346.94,
                        "steps": [
                            {
                                "duration_minutes": 10,
                                "item": {
                                    "type": "commute",
                                    "id": "commute_1",
                                    "name": "打车",
                                    "cost": 41.35,
                                    "commute_mode": "taxi",
                                },
                            },
                            {
                                "duration_minutes": 60,
                                "item": {
                                    "type": "restaurant",
                                    "id": "combo_1",
                                    "name": "餐厅",
                                    "cost": 97.69,
                                },
                            },
                            {
                                "duration_minutes": 60,
                                "item": {
                                    "type": "activity",
                                    "id": "package_1",
                                    "name": "活动",
                                    "cost": 119.9,
                                },
                            },
                            {
                                "duration_minutes": 10,
                                "item": {
                                    "type": "gift_shop",
                                    "id": "gift_1",
                                    "name": "礼物",
                                    "cost": 88.0,
                                    "gift_price": 78.0,
                                    "delivery_fee": 10.0,
                                },
                            },
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
                for item_id, item_type in (
                    ("commute_1", "commute"),
                    ("combo_1", "restaurant"),
                    ("package_1", "activity"),
                    ("gift_1", "gift_shop"),
                ):
                    yield {
                        "type": "item_update",
                        "data": {
                            "phase": "done",
                            "execution_id": execution_id,
                            "item_id": item_id,
                            "item_type": item_type,
                            "reserved": True,
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
            self.assertEqual(confirmation.get("status"), "executed")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
