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
    def test_family_afternoon_tea_combo_count_at_least_4(self):
        config = get_config()
        path = os.path.join(_resolve_repo_dir(config.data.MOCK_DB_REPO_DIR), "restaurants.json")
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
