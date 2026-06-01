import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.execute_tool import _planned_item_cost


class TestExecuteCostConsistency(unittest.TestCase):
    def test_gift_cost_should_include_delivery_fee(self):
        """礼物预期费用必须包含配送费。"""
        item = {
            "type": "gift_shop",
            "id": "gift_1",
            "cost": 88.0,
            "gift_price": 78.0,
            "delivery_fee": 10.0,
        }

        self.assertEqual(_planned_item_cost(item), 88.0)

    def test_gift_cost_should_fallback_to_cost_when_fee_missing(self):
        """历史数据缺少配送拆分时，使用 plan item 的完整 cost。"""
        item = {
            "type": "gift_shop",
            "id": "gift_1",
            "cost": 88.0,
        }

        self.assertEqual(_planned_item_cost(item), 88.0)

    def test_non_gift_cost_should_use_plan_item_cost(self):
        item = {
            "type": "activity",
            "id": "package_1",
            "cost": 119.9,
            "price": 99.0,
        }

        self.assertEqual(_planned_item_cost(item), 119.9)


if __name__ == "__main__":
    unittest.main()
