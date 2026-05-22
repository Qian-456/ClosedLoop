import json
import os
import unittest


class TestAfternoonTeaFamilyDataRegression(unittest.TestCase):
    def test_family_afternoon_tea_combo_count_at_least_4(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        path = os.path.join(repo_root, "mock_db", "restaurants.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for r in data:
            if "family" not in (r.get("suitable_groups") or []):
                continue
            for c in (r.get("combos") or []):
                if "afternoon_tea" in (c.get("suitable_time_slots") or []):
                    count += 1

        self.assertGreaterEqual(count, 4)


if __name__ == "__main__":
    unittest.main()

