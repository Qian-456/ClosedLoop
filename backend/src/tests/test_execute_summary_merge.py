import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.execute_tool import _merge_previous_execution_summary


class TestExecuteSummaryMerge(unittest.TestCase):
    def test_previous_failures_should_not_pollute_reexecution(self):
        """补齐重试时，旧失败不能继续参与本轮一致性校验。"""
        previous_summary = {
            "execution_id": "old_exec",
            "replacements": [{"original_id": "gift_old", "new_item_id": "gift_new"}],
            "failures": [{"item_id": "gift_old"}],
            "items": [
                {"item_id": "combo_1", "reserved": True},
                {"item_id": "gift_old", "reserved": False},
            ],
        }

        merged = _merge_previous_execution_summary(previous_summary)

        self.assertEqual(merged["failures"], [])
        self.assertEqual(merged["replacements"], [{"original_id": "gift_old", "new_item_id": "gift_new"}])
        self.assertEqual(merged["items"], [{"item_id": "combo_1", "reserved": True}])


if __name__ == "__main__":
    unittest.main()
