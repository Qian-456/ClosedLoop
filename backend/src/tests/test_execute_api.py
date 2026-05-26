import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app



def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestExecuteAPI(unittest.TestCase):
    def test_execute_sse_and_persist_decrement(self):
        with TestClient(app) as client, tempfile.TemporaryDirectory() as tmpdir:
            restaurants = [
                {
                    "restaurant_id": "r1",
                    "name": "餐厅A",
                    "location": {
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "address": "某路1号",
                        "distance_to_center_km": 1.0,
                        "zone_name": "商圈",
                    },
                    "rating": 4.5,
                    "tags": ["亲子"],
                    "combos": [
                        {
                            "combo_id": "combo_1",
                            "name": "双人套餐",
                            "price": 100.0,
                            "description": "desc",
                            "features": "feat",
                            "duration_mins": 60,
                            "duration_std_dev": 5.0,
                            "suitable_time_slots": ["lunch"],
                            "requires_booking": True,
                        }
                    ],
                }
            ]
            activities = [
                {
                    "venue_id": "v1",
                    "name": "场馆A",
                    "category": "博物馆",
                    "location": {
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "address": "某路2号",
                        "distance_to_center_km": 2.0,
                        "zone_name": "商圈",
                    },
                    "is_free": False,
                    "rating": 4.3,
                    "reviews_count": 10,
                    "operating_hours": "10:00-18:00",
                    "tags": ["室内"],
                    "packages": [
                        {
                            "package_id": "package_1",
                            "name": "门票",
                            "price": 50.0,
                            "description": "desc",
                            "features": "feat",
                            "requires_booking": True,
                            "available_stock": 1,
                            "start_time": "15:10",
                            "duration_mins": 90,
                            "duration_std_dev": 10.0,
                        }
                    ],
                }
            ]
            add_ons = [
                {
                    "shop_id": "s1",
                    "name": "礼物店A",
                    "location": {
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "address": "某路3号",
                        "distance_to_center_km": 3.0,
                        "zone_name": "商圈",
                    },
                    "rating": 4.0,
                    "tags": ["礼物"],
                    "delivery_time_mins": 30,
                    "delivery_time_std_dev": 5.0,
                    "delivery_radius_km": 5.0,
                    "gifts": [
                        {
                            "gift_id": "gift_1",
                            "name": "花束",
                            "price": 99.0,
                            "receive_duration_mins": 10,
                            "receive_duration_std_dev": 3.0,
                            "description": "desc",
                            "features": "feat",
                            "stock": 1,
                        }
                    ],
                }
            ]
            reservations = [
                {
                    "target_type": "combo",
                    "target_id": "combo_1",
                    "time_slots": [
                        {
                            "start_time": "13:00",
                            "end_time": "15:00",
                            "capacity_total": 10,
                            "capacity_remaining": 1,
                            "queue_required": False,
                            "wait_minutes": 0,
                        }
                    ],
                },
                {
                    "target_type": "package",
                    "target_id": "package_1",
                    "time_slots": [
                        {
                            "start_time": "15:00",
                            "end_time": "17:00",
                            "capacity_total": 10,
                            "capacity_remaining": 1,
                            "queue_required": False,
                            "wait_minutes": 0,
                        }
                    ],
                },
            ]

            _write_json(os.path.join(tmpdir, "restaurants.json"), restaurants)
            _write_json(os.path.join(tmpdir, "activities.json"), activities)
            _write_json(os.path.join(tmpdir, "add_ons.json"), add_ons)
            _write_json(os.path.join(tmpdir, "reservations.json"), reservations)

            fake_config = type(
                "FakeConfig",
                (),
                {"data": type("Data", (), {"MOCK_DB_REPO_DIR": tmpdir})()},
            )()

            payload = {
                "plan_id": "plan_A",
                "steps": [
                    {
                        "item_id": "combo_1",
                        "item_type": "restaurant",
                        "start_time": "14:00",
                        "end_time": "15:00",
                    },
                    {
                        "item_id": "package_1",
                        "item_type": "activity",
                        "start_time": "15:10",
                        "end_time": "16:40",
                    },
                    {
                        "item_id": "gift_1",
                        "item_type": "gift_shop",
                        "start_time": "16:00",
                        "end_time": "16:10",
                    },
                    {
                        "item_id": "commute_x",
                        "item_type": "commute",
                        "start_time": "16:10",
                        "end_time": "16:20",
                        "commute_mode": "taxi",
                    },
                ],
            }

            with (
                patch("closedloop.execution.mock_executor.get_config", return_value=fake_config),
                patch("closedloop.execution.mock_executor.random.uniform", return_value=0.0),
            ):
                start_resp = client.post("/execute/start", json=payload)
                self.assertEqual(start_resp.status_code, 200)
                execution_id = start_resp.json().get("execution_id")
                self.assertTrue(execution_id)

                events: list[dict] = []
                r = client.get(f"/execute/events/{execution_id}")
                self.assertEqual(r.status_code, 200)
                for block in r.text.split("\n\n"):
                    block = block.strip()
                    if not block:
                        continue
                    if block.startswith("data:"):
                        raw = block[len("data:") :].strip()
                        events.append(json.loads(raw))

                phases = [e.get("data", {}).get("phase") for e in events if e.get("type") == "item_update"]
                self.assertIn("checking", phases)
                self.assertIn("reserving", phases)
                self.assertIn("done", phases)

                gift_done = None
                for e in events:
                    if e.get("type") != "item_update":
                        continue
                    d = e.get("data", {})
                    if d.get("item_id") == "gift_1" and d.get("phase") == "done":
                        gift_done = d
                        break
                self.assertIsNotNone(gift_done)
                self.assertEqual(gift_done.get("delivery_time"), "15:50")

                taxi_done = None
                for e in events:
                    if e.get("type") != "item_update":
                        continue
                    d = e.get("data", {})
                    if d.get("item_id") == "commute_x" and d.get("phase") == "done":
                        taxi_done = d
                        break
                self.assertIsNotNone(taxi_done)

            new_activities = _read_json(os.path.join(tmpdir, "activities.json"))
            self.assertEqual(new_activities[0]["packages"][0]["available_stock"], 0)

            new_add_ons = _read_json(os.path.join(tmpdir, "add_ons.json"))
            self.assertEqual(new_add_ons[0]["gifts"][0]["stock"], 0)

            new_reservations = _read_json(os.path.join(tmpdir, "reservations.json"))
            combo_slot = next(r for r in new_reservations if r["target_id"] == "combo_1")["time_slots"][0]
            pkg_slot = next(r for r in new_reservations if r["target_id"] == "package_1")["time_slots"][0]
            self.assertEqual(combo_slot["capacity_remaining"], 0)
            self.assertEqual(pkg_slot["capacity_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
