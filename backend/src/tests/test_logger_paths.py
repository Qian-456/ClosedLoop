import os
import shutil
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.core.config import REPO_ROOT_DIR, SRC_DIR
from closedloop.core.logger import LoggerManager, logger


class TestLoggerPaths(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()

        self.test_log_dir = os.path.join(SRC_DIR, "logs_test_logger_paths")
        if os.path.isdir(self.test_log_dir):
            shutil.rmtree(self.test_log_dir, ignore_errors=True)

        self.test_log_dir_dup = os.path.join(SRC_DIR, "backend", "src", "logs_test_logger_paths")
        if os.path.isdir(self.test_log_dir_dup):
            shutil.rmtree(self.test_log_dir_dup, ignore_errors=True)

    def tearDown(self):
        try:
            os.chdir(self._cwd)
        except Exception:
            pass

        logger.remove()

        for d in [self.test_log_dir, self.test_log_dir_dup]:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)

    def test_relative_paths_never_double_under_backend_src(self):
        """Relative paths should not be duplicated by current working directory."""
        os.chdir(SRC_DIR)

        cfg = SimpleNamespace(
            logging=SimpleNamespace(
                LOG_LEVEL="INFO",
                LOG_DIR="backend/src/logs_test_logger_paths",
                LOG_ROTATION="100 MB",
                LOG_RETENTION="1 days",
                LOG_ELK_ENABLED=True,
                LOG_ELK_JSON_PATH="backend/src/logs_test_logger_paths/elk.jsonl",
                LOG_ELK_LEVEL="DEBUG",
            )
        )

        LoggerManager._initialized = False
        LoggerManager.setup(cfg)
        logger.info("phase=test_logger_paths | msg=write_once")

        expected_dir = os.path.join(REPO_ROOT_DIR, "backend", "src", "logs_test_logger_paths")
        self.assertTrue(os.path.isdir(expected_dir))
        self.assertFalse(os.path.isdir(self.test_log_dir_dup))

        self.assertTrue(os.path.isfile(os.path.join(expected_dir, "app.log")))
        self.assertTrue(os.path.isfile(os.path.join(expected_dir, "error.log")))
        self.assertTrue(os.path.isfile(os.path.join(expected_dir, "elk.jsonl")))

    def test_relative_paths_under_src_for_simple_logs_dir(self):
        """Relative paths without backend/src prefix should be resolved under SRC_DIR."""
        os.chdir(REPO_ROOT_DIR)

        cfg = SimpleNamespace(
            logging=SimpleNamespace(
                LOG_LEVEL="INFO",
                LOG_DIR="logs_test_logger_paths",
                LOG_ROTATION="100 MB",
                LOG_RETENTION="1 days",
                LOG_ELK_ENABLED=False,
            )
        )

        LoggerManager._initialized = False
        LoggerManager.setup(cfg)
        logger.info("phase=test_logger_paths | msg=write_once")

        expected_dir = os.path.join(SRC_DIR, "logs_test_logger_paths")
        self.assertTrue(os.path.isdir(expected_dir))
        self.assertTrue(os.path.isfile(os.path.join(expected_dir, "app.log")))
        self.assertTrue(os.path.isfile(os.path.join(expected_dir, "error.log")))


if __name__ == "__main__":
    unittest.main()

