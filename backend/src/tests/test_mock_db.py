import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.utils import mock_db


class TestMockDb(unittest.TestCase):
    def setUp(self):
        mock_db._MOCK_DB_CACHE.clear()

    def test_load_mock_data_uses_cache_until_mtime_changes(self):
        fake_config = SimpleNamespace(data=SimpleNamespace(MOCK_DB_REPO_DIR="mock_db"))
        fake_json = '[{"id":"1","name":"A"}]'

        with patch("closedloop.utils.mock_db.get_config", return_value=fake_config), patch(
            "closedloop.utils.mock_db.os.path.exists", return_value=True
        ), patch(
            "closedloop.utils.mock_db.os.path.getmtime", side_effect=[100.0, 100.0, 200.0]
        ), patch(
            "builtins.open", mock_open(read_data=fake_json)
        ) as mocked_open:
            first = mock_db.load_mock_data("restaurants.json")
            second = mock_db.load_mock_data("restaurants.json")
            third = mock_db.load_mock_data("restaurants.json")

        self.assertEqual(first, second)
        self.assertEqual(third, first)
        self.assertEqual(mocked_open.call_count, 2)
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
