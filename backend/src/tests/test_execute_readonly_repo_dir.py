import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app


client = TestClient(app)


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestExecuteReadonlyRepoDir(unittest.TestCase):
    def test_execute_should_fallback_to_rw_dir_when_repo_dir_readonly(self):
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
            activities = [
                {
                    "venue_id": "v1",
                    "name": "场馆A",
                    "packages": [
                        {
                            "package_id": "package_1",
                            "name": "门票",
                            "requires_booking": False,
                            "available_stock": 1,
                        }
                    ],
                }
            ]
            restaurants = [
                {
                    "restaurant_id": "r1",
                    "name": "餐厅A",
                    "combos": [
                        {
                            "combo_id": "combo_1",
                            "name": "套餐",
                            "requires_booking": False,
                        }
                    ],
                }
            ]
            add_ons = [
                {
                    "shop_id": "s1",
                    "name": "礼物店A",
                    "gifts": [
                        {
                            "gift_id": "gift_1",
                            "name": "花束",
                            "stock": 1,
                        }
                    ],
                }
            ]
            reservations = []

            _write_json(os.path.join(repo_dir, "restaurants.json"), restaurants)
            _write_json(os.path.join(repo_dir, "activities.json"), activities)
            _write_json(os.path.join(repo_dir, "add_ons.json"), add_ons)
            _write_json(os.path.join(repo_dir, "reservations.json"), reservations)

            fake_config = type(
                "FakeConfig",
                (),
                {"data": type("Data", (), {"MOCK_DB_REPO_DIR": repo_dir, "MOCK_DB_RW_DIR": rw_dir})()},
            )()

            payload = {
                "plan_id": "plan_1",
                "steps": [
                    {"item_id": "combo_1", "item_type": "restaurant", "start_time": "14:00", "end_time": "15:00"},
                    {"item_id": "package_1", "item_type": "activity", "start_time": "15:10", "end_time": "16:40"},
                    {"item_id": "gift_1", "item_type": "gift_shop", "start_time": "16:00", "end_time": "16:10"},
                ],
            }

            import builtins

            real_open = builtins.open
            repo_dir_abs = os.path.abspath(repo_dir)

            def guarded_open(file, mode="r", *args, **kwargs):
                p = os.path.abspath(str(file))
                if ("w" in mode or "a" in mode or "+" in mode) and p.startswith(repo_dir_abs):
                    raise OSError(30, "Read-only file system", p)
                return real_open(file, mode, *args, **kwargs)

            with (
                patch("closedloop.execution.mock_executor.get_config", return_value=fake_config),
                patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0),
                patch("closedloop.execution.mock_executor.open", side_effect=guarded_open),
            ):
                start_resp = client.post("/execute/start", json=payload)
                self.assertEqual(start_resp.status_code, 200)
                execution_id = start_resp.json().get("execution_id")
                self.assertTrue(execution_id)

                events: list[dict] = []
                with client.stream("GET", f"/execute/events/{execution_id}") as r:
                    self.assertEqual(r.status_code, 200)
                    for line in r.iter_lines():
                        if not line:
                            continue
                        if isinstance(line, bytes):
                            text = line.decode("utf-8")
                        else:
                            text = line
                        if text.startswith("data:"):
                            raw = text[len("data:") :].strip()
                            events.append(json.loads(raw))
                        if events and events[-1].get("type") == "done":
                            break

                self.assertTrue(any(e.get("type") == "done" for e in events))

            repo_activities = _read_json(os.path.join(repo_dir, "activities.json"))
            self.assertEqual(repo_activities[0]["packages"][0]["available_stock"], 1)

            rw_activities = _read_json(os.path.join(rw_dir, "activities.json"))
            self.assertEqual(rw_activities[0]["packages"][0]["available_stock"], 0)

            rw_add_ons = _read_json(os.path.join(rw_dir, "add_ons.json"))
            self.assertEqual(rw_add_ons[0]["gifts"][0]["stock"], 0)


if __name__ == "__main__":
    unittest.main()

