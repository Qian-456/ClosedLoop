import json
import os
import unittest

from closedloop.core.config import REPO_ROOT_DIR, get_config


def _resolve_repo_dir(path_value: str) -> str:
    """Resolve a repo-relative mock db directory into an absolute path."""
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(REPO_ROOT_DIR, path_value))


class TestAfternoonTeaFamilyDataRegression(unittest.TestCase):
    def test_afternoon_tea_combo_quality_and_count(self):
        config = get_config()
        path = os.path.join(_resolve_repo_dir(config.data.MOCK_DB_REPO_DIR), "restaurants.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        allowed_keywords = ("甜品", "下午茶", "咖啡", "奶茶", "烘焙", "面包")
        tea_combo_count = 0
        bad_slot_combo_ids: list[str] = []
        bad_sub_category_restaurant_ids: list[str] = []

        for r in data:
            sub_category = str(r.get("sub_category") or "")
            for c in (r.get("combos") or []):
                if "afternoon_tea" in (c.get("suitable_time_slots") or []):
                    tea_combo_count += 1
                    slots = c.get("suitable_time_slots") or []
                    if slots != ["afternoon_tea"]:
                        bad_slot_combo_ids.append(str(c.get("combo_id") or ""))
                    if not any(k in sub_category for k in allowed_keywords):
                        bad_sub_category_restaurant_ids.append(str(r.get("id") or ""))

        self.assertGreaterEqual(tea_combo_count, 20)
        self.assertEqual(bad_slot_combo_ids[:3], [])
        self.assertEqual(bad_sub_category_restaurant_ids[:3], [])


if __name__ == "__main__":
    unittest.main()
