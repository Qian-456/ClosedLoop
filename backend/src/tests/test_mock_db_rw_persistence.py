import json
import os
import tempfile
import unittest
from unittest.mock import patch


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestMockDbRwPersistence(unittest.TestCase):
    def test_seed_should_not_overwrite_existing_rw_files(self):
        """Ensure rw dir keeps modified data and won't be reset by seeding."""
        from closedloop.execution import mock_executor

        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as rw_dir:
            repo_activities = [
                {
                    "venue_id": "v1",
                    "packages": [{"package_id": "pkg_1", "available_stock": 10, "requires_booking": False}],
                }
            ]
            rw_activities = [
                {
                    "venue_id": "v1",
                    "packages": [{"package_id": "pkg_1", "available_stock": 0, "requires_booking": False}],
                }
            ]
            _write_json(os.path.join(repo_dir, "activities.json"), repo_activities)
            _write_json(os.path.join(repo_dir, "restaurants.json"), [])
            _write_json(os.path.join(repo_dir, "add_ons.json"), [])
            _write_json(os.path.join(repo_dir, "reservations.json"), [])

            _write_json(os.path.join(rw_dir, "activities.json"), rw_activities)

            fake_config = type(
                "FakeConfig",
                (),
                {"data": type("Data", (), {"MOCK_DB_REPO_DIR": repo_dir, "MOCK_DB_RW_DIR": rw_dir})()},
            )()

            with patch("closedloop.execution.mock_executor.get_config", return_value=fake_config):
                resolved = mock_executor._resolve_repo_dir()
                self.assertEqual(os.path.abspath(resolved), os.path.abspath(rw_dir))

            after = _read_json(os.path.join(rw_dir, "activities.json"))
            self.assertEqual(after[0]["packages"][0]["available_stock"], 0)


class TestIsDirWritable(unittest.TestCase):
    def test_is_dir_writable_should_check_replace(self):
        """Ensure writability check fails when atomic replace is not permitted."""
        from closedloop.execution import mock_executor

        with tempfile.TemporaryDirectory() as d:
            with patch("closedloop.execution.mock_executor.os.replace", side_effect=OSError(30, "Read-only file system")):
                self.assertFalse(mock_executor._is_dir_writable(d))


if __name__ == "__main__":
    unittest.main()

