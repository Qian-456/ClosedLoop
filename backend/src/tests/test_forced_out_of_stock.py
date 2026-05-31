import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestForcedOutOfStockParser(unittest.TestCase):
    def test_parse_empty(self):
        from closedloop.utils.forced_out_of_stock import parse_forced_out_of_stock_ids

        self.assertEqual(parse_forced_out_of_stock_ids(""), set())
        self.assertEqual(parse_forced_out_of_stock_ids("()"), set())

    def test_parse_tuple_style(self):
        from closedloop.utils.forced_out_of_stock import parse_forced_out_of_stock_ids

        self.assertEqual(parse_forced_out_of_stock_ids("(combo_019_2,)"), {"combo_019_2"})
        self.assertEqual(
            parse_forced_out_of_stock_ids("(combo_019_2, package_015_1,)"),
            {"combo_019_2", "package_015_1"},
        )

    def test_parse_csv_style(self):
        from closedloop.utils.forced_out_of_stock import parse_forced_out_of_stock_ids

        self.assertEqual(parse_forced_out_of_stock_ids("combo_019_2"), {"combo_019_2"})
        self.assertEqual(parse_forced_out_of_stock_ids("combo_019_2,package_015_1"), {"combo_019_2", "package_015_1"})


class TestMockExecutorForcedOutOfStock(unittest.TestCase):
    def test_reserve_capacity_should_fail_when_remaining_is_zero(self):
        from closedloop.execution.mock_executor import _reserve_capacity

        reservations = [
            {
                "target_type": "combo",
                "target_id": "combo_001_1",
                "time_slots": [
                    {"start_time": "12:00", "end_time": "13:00", "capacity_total": 2, "capacity_remaining": 0}
                ],
            }
        ]

        ok, detail = _reserve_capacity(reservations, "combo", "combo_001_1", "12:00")
        self.assertFalse(ok)
        self.assertIsInstance(detail, dict)
        self.assertEqual(detail.get("capacity_remaining_before"), 0)

    def test_forced_combo_should_trigger_fallback_replacement(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _noop_sleep(*_args, **_kwargs):
            return None

        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
            restaurants = [
                {
                    "id": "restaurant_001",
                    "combos": [
                        {"combo_id": "combo_main", "requires_booking": False},
                        {"combo_id": "combo_backup", "requires_booking": False},
                    ],
                }
            ]
            for name, content in (
                ("restaurants.json", restaurants),
                ("activities.json", []),
                ("add_ons.json", []),
                ("reservations.json", []),
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
                            "FORCE_OUT_OF_STOCK_IDS": "(combo_main,)",
                        },
                    )()
                },
            )()

            step = ExecuteStep(
                item_id="combo_main",
                item_type="restaurant",
                start_time="12:00",
                end_time="13:00",
                backup_candidates=[{"id": "combo_backup", "name": "备选餐厅", "requires_confirmation": False}],
                replacement_policy="equivalent_only",
                user_touched=False,
            )
            async def _run():
                ctx = mock_executor._ExecutionContext(
                    request=ExecuteRequest(plan_id="plan_A", steps=[step]),
                    queue=asyncio.Queue(),
                    decision_futures={},
                    pending_confirmations={},
                    execution_key="test",
                    loop_id=id(asyncio.get_running_loop()),
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        with patch("closedloop.execution.mock_executor.asyncio.sleep", new=_noop_sleep):
                            await mock_executor._check_and_reserve_one("exe_test", ctx, step)

                return ctx

            ctx = asyncio.run(_run())

            events = []
            while not ctx.queue.empty():
                events.append(ctx.queue.get_nowait())

            done = [e for e in events if e.get("type") == "item_update" and e.get("data", {}).get("phase") == "done"]
            self.assertEqual(len(done), 1)
            data = done[0]["data"]
            self.assertTrue(data.get("replaced"))
            self.assertEqual(data.get("new_item_id"), "combo_backup")
            self.assertTrue(data.get("reserved"))

    def test_forced_combo_should_trigger_pending_confirmation_when_backup_requires_confirmation(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _noop_sleep(*_args, **_kwargs):
            return None

        async def _run():
            with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
                restaurants = [
                    {
                        "id": "restaurant_001",
                        "combos": [
                            {"combo_id": "combo_main", "requires_booking": False},
                            {"combo_id": "combo_backup", "requires_booking": False},
                        ],
                    }
                ]
                for name, content in (
                    ("restaurants.json", restaurants),
                    ("activities.json", []),
                    ("add_ons.json", []),
                    ("reservations.json", []),
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
                                "FORCE_OUT_OF_STOCK_IDS": "(combo_main,)",
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
                ctx = mock_executor._ExecutionContext(
                    request=ExecuteRequest(plan_id="plan_A", steps=[step]),
                    queue=asyncio.Queue(),
                    decision_futures={},
                    pending_confirmations={},
                    execution_key="test",
                    loop_id=id(asyncio.get_running_loop()),
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        with patch("closedloop.execution.mock_executor.asyncio.sleep", new=_noop_sleep):
                            task = asyncio.create_task(
                                mock_executor._check_and_reserve_one("exe_test", ctx, step)
                            )

                            event = None
                            while True:
                                next_event = await ctx.queue.get()
                                if (
                                    next_event.get("type") == "item_update"
                                    and next_event.get("data", {}).get("phase")
                                    == "pending_user_confirmation"
                                ):
                                    event = next_event
                                    break
                            self.assertIsNotNone(event)

                            fut = ctx.decision_futures.get("combo_main")
                            self.assertIsNotNone(fut)
                            fut.set_result({"type": "approve"})

                            await asyncio.wait_for(task, timeout=1.0)

                events = [event]
                while not ctx.queue.empty():
                    events.append(ctx.queue.get_nowait())

                done = [
                    e
                    for e in events
                    if e.get("type") == "item_update"
                    and e.get("data", {}).get("phase") == "done"
                ]
                self.assertEqual(len(done), 1)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
