import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestMockExecutorHITL(unittest.TestCase):
    def test_pending_confirmation_should_block_until_decision_then_continue(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _run():
            with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
                restaurants = [
                    {
                        "id": "restaurant_001",
                        "combos": [
                            {"combo_id": "combo_main", "requires_booking": True},
                            {"combo_id": "combo_backup", "requires_booking": False},
                        ],
                    }
                ]
                reservations = [
                    {
                        "target_type": "combo",
                        "target_id": "combo_main",
                        "time_slots": [
                            {"start_time": "12:00", "end_time": "13:00", "capacity_total": 1, "capacity_remaining": 0}
                        ],
                    }
                ]
                for name, content in (
                    ("restaurants.json", restaurants),
                    ("activities.json", []),
                    ("add_ons.json", []),
                    ("reservations.json", reservations),
                ):
                    with open(os.path.join(repo_dir, name), "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)

                fake_config = type(
                    "FakeConfig",
                    (),
                    {
                        "data": type(
                            "Data",
                            (),
                            {"MOCK_DB_REPO_DIR": repo_dir, "MOCK_DB_RW_DIR": rw_dir, "FORCE_OUT_OF_STOCK_IDS": "()"},
                        )()
                    },
                )()

                step = ExecuteStep(
                    item_id="combo_main",
                    item_type="restaurant",
                    start_time="12:00",
                    end_time="13:00",
                    backup_candidates=[
                        {
                            "id": "combo_backup",
                            "name": "备选餐厅",
                            "requires_confirmation": True,
                            "violation_reason": "超出预算或时间",
                        }
                    ],
                    replacement_policy="equivalent_only",
                    user_touched=False,
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        execution_id = await mock_executor.start_execution(ExecuteRequest(plan_id="plan_A", steps=[step]))

                        gen = mock_executor.iter_events(execution_id)

                        pending_event = None
                        while True:
                            event = await anext(gen)
                            if (
                                event.get("type") == "item_update"
                                and event.get("data", {}).get("phase") == "pending_user_confirmation"
                            ):
                                pending_event = event
                                break

                        self.assertIsNotNone(pending_event)

                        await asyncio.sleep(0.05)
                        async with mock_executor._executions_guard:
                            ctx = mock_executor._executions.get(execution_id)
                        self.assertIsNotNone(ctx)
                        self.assertTrue(ctx.queue.empty())

                        await mock_executor.submit_decision(
                            execution_id=execution_id,
                            item_id="combo_main",
                            decision={"type": "approve"},
                        )

                        done_seen = False
                        async for event in gen:
                            if event.get("type") == "item_update" and event.get("data", {}).get("phase") == "done":
                                done_seen = True
                            if event.get("type") == "done":
                                break

                        self.assertTrue(done_seen)

        asyncio.run(_run())

    def test_submit_decision_wrong_item_id_should_fail(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _run():
            with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
                restaurants = [
                    {
                        "id": "restaurant_001",
                        "combos": [
                            {"combo_id": "combo_main", "requires_booking": True},
                            {"combo_id": "combo_backup", "requires_booking": False},
                        ],
                    }
                ]
                reservations = [
                    {
                        "target_type": "combo",
                        "target_id": "combo_main",
                        "time_slots": [
                            {
                                "start_time": "12:00",
                                "end_time": "13:00",
                                "capacity_total": 1,
                                "capacity_remaining": 0,
                            }
                        ],
                    }
                ]
                for name, content in (
                    ("restaurants.json", restaurants),
                    ("activities.json", []),
                    ("add_ons.json", []),
                    ("reservations.json", reservations),
                ):
                    with open(os.path.join(repo_dir, name), "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)

                fake_config = type(
                    "FakeConfig",
                    (),
                    {
                        "data": type(
                            "Data",
                            (),
                            {
                                "MOCK_DB_REPO_DIR": repo_dir,
                                "MOCK_DB_RW_DIR": rw_dir,
                                "FORCE_OUT_OF_STOCK_IDS": "()",
                            },
                        )()
                    },
                )()

                step = ExecuteStep(
                    item_id="combo_main",
                    item_type="restaurant",
                    start_time="12:00",
                    end_time="13:00",
                    backup_candidates=[
                        {
                            "id": "combo_backup",
                            "name": "备选餐厅",
                            "requires_confirmation": True,
                            "violation_reason": "超出预算或时间",
                        }
                    ],
                    replacement_policy="equivalent_only",
                    user_touched=False,
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        execution_id = await mock_executor.start_execution(
                            ExecuteRequest(plan_id="plan_A", steps=[step])
                        )
                        gen = mock_executor.iter_events(execution_id)

                        while True:
                            event = await anext(gen)
                            if (
                                event.get("type") == "item_update"
                                and event.get("data", {}).get("phase") == "pending_user_confirmation"
                            ):
                                break

                        ok = await mock_executor.submit_decision(
                            execution_id=execution_id,
                            item_id="combo_other",
                            decision={"type": "approve"},
                        )
                        self.assertFalse(ok)

                        await asyncio.sleep(0.05)
                        async with mock_executor._executions_guard:
                            ctx = mock_executor._executions.get(execution_id)
                        self.assertIsNotNone(ctx)
                        self.assertTrue(ctx.queue.empty())
                        self.assertIn("combo_main", ctx.decision_futures)
                        self.assertNotIn("combo_other", ctx.decision_futures)

        asyncio.run(_run())

    def test_reject_should_continue_to_next_backup_confirmation(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _run():
            with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
                restaurants = [
                    {
                        "id": "restaurant_001",
                        "combos": [
                            {"combo_id": "combo_main", "requires_booking": True},
                            {"combo_id": "combo_backup_1", "requires_booking": False},
                            {"combo_id": "combo_backup_2", "requires_booking": False},
                        ],
                    }
                ]
                reservations = [
                    {
                        "target_type": "combo",
                        "target_id": "combo_main",
                        "time_slots": [
                            {
                                "start_time": "12:00",
                                "end_time": "13:00",
                                "capacity_total": 1,
                                "capacity_remaining": 0,
                            }
                        ],
                    }
                ]
                for name, content in (
                    ("restaurants.json", restaurants),
                    ("activities.json", []),
                    ("add_ons.json", []),
                    ("reservations.json", reservations),
                ):
                    with open(os.path.join(repo_dir, name), "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)

                fake_config = type(
                    "FakeConfig",
                    (),
                    {
                        "data": type(
                            "Data",
                            (),
                            {
                                "MOCK_DB_REPO_DIR": repo_dir,
                                "MOCK_DB_RW_DIR": rw_dir,
                                "FORCE_OUT_OF_STOCK_IDS": "()",
                            },
                        )()
                    },
                )()

                step = ExecuteStep(
                    item_id="combo_main",
                    item_type="restaurant",
                    start_time="12:00",
                    end_time="13:00",
                    backup_candidates=[
                        {
                            "id": "combo_backup_1",
                            "name": "备选餐厅 1",
                            "requires_confirmation": True,
                            "violation_reason": "超出预算或时间",
                        },
                        {
                            "id": "combo_backup_2",
                            "name": "备选餐厅 2",
                            "requires_confirmation": True,
                            "violation_reason": "偏好可能受损",
                        },
                    ],
                    replacement_policy="equivalent_only",
                    user_touched=False,
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        execution_id = await mock_executor.start_execution(
                            ExecuteRequest(plan_id="plan_A", steps=[step])
                        )

                        gen = mock_executor.iter_events(execution_id)

                        first_pending = None
                        while True:
                            event = await anext(gen)
                            if (
                                event.get("type") == "item_update"
                                and event.get("data", {}).get("phase")
                                == "pending_user_confirmation"
                            ):
                                first_pending = event
                                break

                        self.assertIsNotNone(first_pending)
                        self.assertEqual(
                            first_pending.get("data", {}).get("backup_id"),
                            "combo_backup_1",
                        )

                        await mock_executor.submit_decision(
                            execution_id=execution_id,
                            item_id="combo_main",
                            decision={"type": "reject"},
                        )

                        second_pending = None
                        while True:
                            event = await anext(gen)
                            if (
                                event.get("type") == "item_update"
                                and event.get("data", {}).get("phase")
                                == "pending_user_confirmation"
                            ):
                                second_pending = event
                                break

                        self.assertIsNotNone(second_pending)
                        self.assertEqual(
                            second_pending.get("data", {}).get("backup_id"),
                            "combo_backup_2",
                        )

                        await mock_executor.submit_decision(
                            execution_id=execution_id,
                            item_id="combo_main",
                            decision={"type": "approve"},
                        )

                        done_item = None
                        async for event in gen:
                            if (
                                event.get("type") == "item_update"
                                and event.get("data", {}).get("phase") == "done"
                            ):
                                done_item = event.get("data")
                            if event.get("type") == "done":
                                break

                        self.assertIsNotNone(done_item)
                        self.assertTrue(done_item.get("replaced"))
                        self.assertEqual(done_item.get("new_item_id"), "combo_backup_2")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
