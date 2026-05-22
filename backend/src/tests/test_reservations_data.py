import unittest

from closedloop.utils.mock_db import load_mock_data


class TestReservationsData(unittest.TestCase):
    def test_restaurant_combos_have_requires_booking(self):
        restaurants = load_mock_data("restaurants.json")
        self.assertGreater(len(restaurants), 0)

        for r in restaurants:
            combos = r.get("combos", [])
            self.assertIsInstance(combos, list)
            self.assertGreater(len(combos), 0)
            for c in combos:
                self.assertIn("requires_booking", c)
                self.assertIsInstance(c["requires_booking"], bool)

    def test_activity_packages_have_requires_booking(self):
        activities = load_mock_data("activities.json")
        self.assertGreater(len(activities), 0)

        for v in activities:
            packages = v.get("packages", [])
            self.assertIsInstance(packages, list)
            self.assertGreater(len(packages), 0)
            for p in packages:
                self.assertIn("requires_booking", p)
                self.assertIsInstance(p["requires_booking"], bool)

    def test_reservations_schema_and_alignment(self):
        restaurants = load_mock_data("restaurants.json")
        activities = load_mock_data("activities.json")
        reservations = load_mock_data("reservations.json")

        booking_combo_ids: set[str] = set()
        for r in restaurants:
            for c in r.get("combos", []):
                if c.get("requires_booking") is True and c.get("combo_id"):
                    booking_combo_ids.add(c["combo_id"])

        booking_package_ids: set[str] = set()
        for v in activities:
            for p in v.get("packages", []):
                if p.get("requires_booking") is True and p.get("package_id"):
                    booking_package_ids.add(p["package_id"])

        seen_combo_ids: set[str] = set()
        seen_package_ids: set[str] = set()

        self.assertIsInstance(reservations, list)
        for rec in reservations:
            self.assertIn("target_type", rec)
            self.assertIn("target_id", rec)
            self.assertIn("time_slots", rec)

            target_type = rec["target_type"]
            target_id = rec["target_id"]
            time_slots = rec["time_slots"]

            self.assertIn(target_type, ("combo", "package"))
            self.assertIsInstance(target_id, str)
            self.assertIsInstance(time_slots, list)
            self.assertGreater(len(time_slots), 0)

            if target_type == "combo":
                self.assertIn(target_id, booking_combo_ids)
                self.assertNotIn(target_id, seen_combo_ids)
                seen_combo_ids.add(target_id)
            else:
                self.assertIn(target_id, booking_package_ids)
                self.assertNotIn(target_id, seen_package_ids)
                seen_package_ids.add(target_id)

            for slot in time_slots:
                self.assertIn("start_time", slot)
                self.assertIn("end_time", slot)
                self.assertIn("capacity_total", slot)
                self.assertIn("capacity_remaining", slot)
                self.assertIn("queue_required", slot)
                self.assertIn("wait_minutes", slot)

                self.assertIsInstance(slot["start_time"], str)
                self.assertIsInstance(slot["end_time"], str)
                self.assertIsInstance(slot["capacity_total"], int)
                self.assertIsInstance(slot["capacity_remaining"], int)
                self.assertIsInstance(slot["queue_required"], bool)
                self.assertIsInstance(slot["wait_minutes"], int)

                self.assertGreater(slot["capacity_total"], 0)
                self.assertGreaterEqual(slot["capacity_remaining"], 0)
                self.assertLessEqual(slot["capacity_remaining"], slot["capacity_total"])

        self.assertEqual(seen_combo_ids, booking_combo_ids)
        self.assertEqual(seen_package_ids, booking_package_ids)


if __name__ == "__main__":
    unittest.main()

