import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestMockExecutorResumeIdempotent(unittest.TestCase):
    def test_resume_should_reuse_execution_and_not_double_deduct_gift(self):
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
                add_ons = [
                    {
                        "id": "shop_1",
                        "gifts": [
                            {"gift_id": "gift_1", "stock": 10},
                        ],
                    }
                ]

                for name, content in (
                    ("restaurants.json", restaurants),
                    ("activities.json", []),
                    ("add_ons.json", add_ons),
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

                steps = [
                    ExecuteStep(
                        item_id="gift_1",
                        item_type="gift_shop",
                        start_time="12:30",
                        end_time="12:40",
                    ),
                    ExecuteStep(
                        item_id="combo_main",
                        item_type="restaurant",
                        start_time="12:00",
                        end_time="13:00",
                        backup_candidates=[
                            {
                                "id": "combo_backup",
                                "name": "备选餐厅",
                                "requires_confirmation": True,
                                "violation_reason": "无座需要替换",
                            }
                        ],
                        replacement_policy="equivalent_only",
                        user_touched=False,
                    ),
                ]
                req = ExecuteRequest(plan_id="plan_A", steps=steps)

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        execution_id_1 = await mock_executor.start_execution(req)

                        gen = mock_executor.iter_events(execution_id_1)
                        pending_seen = False
                        while True:
                            event = await anext(gen)
                            if (
                                event.get("type") == "item_update"
                                and (event.get("data") or {}).get("phase") == "pending_user_confirmation"
                            ):
                                pending_seen = True
                                break

                        self.assertTrue(pending_seen)

                        await gen.aclose()

                        async with mock_executor._executions_guard:
                            ctx = mock_executor._executions.get(execution_id_1)
                        self.assertIsNotNone(ctx)

                        execution_id_2 = await mock_executor.start_execution(req)
                        self.assertEqual(execution_id_1, execution_id_2)

                        pending = await mock_executor.peek_pending_confirmation(execution_id_1)
                        self.assertIsInstance(pending, dict)
                        self.assertEqual(pending.get("item_id"), "combo_main")

                        ok = await mock_executor.submit_decision(
                            execution_id=execution_id_1,
                            item_id="combo_main",
                            decision={"type": "approve"},
                        )
                        self.assertTrue(ok)

                        done_seen = False
                        gen2 = mock_executor.iter_events(execution_id_1)
                        async for event in gen2:
                            if event.get("type") == "item_update" and (event.get("data") or {}).get("phase") == "done":
                                done_seen = True
                            if event.get("type") == "done":
                                break

                        self.assertTrue(done_seen)

                        with open(os.path.join(rw_dir, "add_ons.json"), "r", encoding="utf-8") as f:
                            add_ons_after = json.load(f)
                        gift_stock = add_ons_after[0]["gifts"][0]["stock"]
                        self.assertEqual(gift_stock, 9)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
