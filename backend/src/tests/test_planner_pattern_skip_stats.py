import os
import unittest
from unittest.mock import patch

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager
from closedloop.graph.plan_subgraph import planner_utils


class TestPlannerPatternSkipStats(unittest.TestCase):
    def setUp(self):
        os.environ["LOG_PLANNER_STATS"] = "true"
        get_config.cache_clear()
        LoggerManager._initialized = False

    def tearDown(self):
        os.environ.pop("LOG_PLANNER_STATS", None)
        get_config.cache_clear()
        LoggerManager._initialized = False

    def test_pattern_skipped_reason_logged(self):
        queues = {
            "activity": [
                {"package_id": "act_1", "name": "活动1", "duration_mins": 60, "score": 80, "price": 0.0, "location": {}},
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [
            {"id": "P1", "desc": "P1", "steps": ["activity"]},
            {"id": "P2", "desc": "P2", "steps": ["gift_shop"]},
        ]

        with patch.object(planner_utils.logger, "info") as mock_info:
            plans, valid_count, missing_types = planner_utils.generate_and_score_combinations(
                queues=queues,
                patterns=patterns,
                budget=1000.0,
                required_duration_range_mins=(70.0, 70.0),
            )

        self.assertEqual(len(plans), 1)
        self.assertGreaterEqual(valid_count, 1)
        self.assertIn("gift_shop", missing_types)

        messages = [c.args[0] for c in mock_info.call_args_list if c.args]
        self.assertTrue(
            any(
                "phase=planner_pattern_skipped" in m
                and "pattern_id=P2" in m
                and "skip_reason_code=missing_gift_pool" in m
                for m in messages
            )
        )
        self.assertTrue(
            any(
                "phase=planner_candidate_pool_stats" in m and "patterns_skipped=1" in m
                for m in messages
            )
        )


if __name__ == "__main__":
    unittest.main()

