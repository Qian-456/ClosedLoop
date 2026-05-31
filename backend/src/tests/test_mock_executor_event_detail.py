import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestMockExecutorEventDetail(unittest.TestCase):
    def test_done_event_should_include_detail(self):
        from closedloop.contracts.execution import ExecuteRequest, ExecuteStep
        from closedloop.execution import mock_executor

        async def _run():
            with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
                add_ons = [{"id": "shop_1", "gifts": [{"gift_id": "gift_1", "stock": 2}]}]
                for name, content in (
                    ("restaurants.json", []),
                    ("activities.json", []),
                    ("add_ons.json", add_ons),
                    ("reservations.json", []),
                ):
                    with open(os.path.join(repo_dir, name), "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)

                fake_config = type(
                    "FakeConfig",
                    (),
                    {
                        "EXECUTION_SIM_DELAY_MAX_SECS": 0.0,
                        "data": type(
                            "Data",
                            (),
                            {"MOCK_DB_REPO_DIR": repo_dir, "MOCK_DB_RW_DIR": rw_dir, "FORCE_OUT_OF_STOCK_IDS": "()"},
                        )(),
                    },
                )()

                step = ExecuteStep(
                    item_id="gift_1",
                    item_type="gift_shop",
                    start_time="12:30",
                    end_time="12:40",
                )

                with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                    with patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0):
                        execution_id = await mock_executor.start_execution(
                            ExecuteRequest(plan_id="plan_A", steps=[step])
                        )

                        async for event in mock_executor.iter_events(execution_id):
                            if event.get("type") != "item_update":
                                continue
                            data = event.get("data") or {}
                            if data.get("phase") == "done":
                                self.assertIn("detail", data)
                                self.assertIsInstance(data.get("detail"), dict)
                                self.assertIn("stock_before", data.get("detail"))
                                self.assertIn("stock_after", data.get("detail"))
                                return

                raise AssertionError("done event not seen")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
