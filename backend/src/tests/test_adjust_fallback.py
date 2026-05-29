import json
import os
import sys
import unittest

# 添加 backend/src 到 sys.path 以便能够导入 closedloop 的包
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

class TestAdjustFallback(unittest.TestCase):
    def test_authoritative_mock_db_dir_should_exist(self):
        """Ensure the authoritative mock db directory exists in backend/src/mock_db."""
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../mock_db"))

        self.assertTrue(os.path.isdir(repo_dir))

        db_files = {
            "restaurants.json": ["combos"],
            "activities.json": ["packages"],
            "add_ons.json": ["gifts"],
        }

        for file_name, sub_keys in db_files.items():
            file_path = os.path.join(repo_dir, file_name)
            self.assertTrue(os.path.isfile(file_path))

            with open(file_path, "r", encoding="utf-8") as f:
                mock_data = json.load(f)

            self.assertIsInstance(mock_data, list)
            self.assertGreater(len(mock_data), 0)

            parent = mock_data[0]
            self.assertIsInstance(parent, dict)
            for sub_key in sub_keys:
                self.assertIn(sub_key, parent)


if __name__ == "__main__":
    unittest.main()
