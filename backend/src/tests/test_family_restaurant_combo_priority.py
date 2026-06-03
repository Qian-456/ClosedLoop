import unittest
import sys
import os
 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
 
from closedloop.contracts.state import Constraints
from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations
 
 
class TestFamilyRestaurantComboPriority(unittest.TestCase):
    def test_family_2a1c_prefers_exact_family_combo(self):
        constraints = Constraints(
            group_type="family",
            budget=1000.0,
            time_period="14:00",
            adult_count=2,
            child_count=1,
            child_profiles=[],
        )
 
        queues = {
            "activity": [],
            "activity_light": [],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [
                {
                    "combo_id": "c_range_highscore",
                    "name": "2-4人共享餐",
                    "price": 100.0,
                    "description": "适合多人聚餐",
                    "features": "分量足",
                    "duration_mins": 60,
                    "score": 95,
                    "expected_wait_minutes": 0,
                    "restaurant_id": "rest_1",
                    "restaurant_name": "测试餐厅",
                    "address": "测试地址",
                    "longitude": 0.0,
                    "latitude": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "combo_id": "c_family_lowscore",
                    "name": "2大1小家庭套餐",
                    "price": 120.0,
                    "description": "更适合带娃家庭",
                    "features": "儿童餐具",
                    "duration_mins": 60,
                    "score": 60,
                    "expected_wait_minutes": 0,
                    "restaurant_id": "rest_1",
                    "restaurant_name": "测试餐厅",
                    "address": "测试地址",
                    "longitude": 0.0,
                    "latitude": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["restaurant:dinner"]}]
 
        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(74.0, 74.0),
            constraints=constraints,
            start_time=18.0,
        )
 
        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["combo"][0]["combo_id"], "c_family_lowscore")
 
    def test_family_2a1c_falls_back_to_people_range_match(self):
        constraints = Constraints(
            group_type="family",
            budget=1000.0,
            time_period="14:00",
            adult_count=2,
            child_count=1,
            child_profiles=[],
        )
 
        queues = {
            "activity": [],
            "activity_light": [],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [
                {
                    "combo_id": "c_no_range_highscore",
                    "name": "豪华套餐",
                    "price": 100.0,
                    "description": "招牌菜合集",
                    "features": "大满足",
                    "duration_mins": 60,
                    "score": 95,
                    "expected_wait_minutes": 0,
                    "restaurant_id": "rest_1",
                    "restaurant_name": "测试餐厅",
                    "address": "测试地址",
                    "longitude": 0.0,
                    "latitude": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "combo_id": "c_range_lowscore",
                    "name": "2-4人共享餐",
                    "price": 120.0,
                    "description": "适合多人聚餐",
                    "features": "分量足",
                    "duration_mins": 60,
                    "score": 60,
                    "expected_wait_minutes": 0,
                    "restaurant_id": "rest_1",
                    "restaurant_name": "测试餐厅",
                    "address": "测试地址",
                    "longitude": 0.0,
                    "latitude": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["restaurant:dinner"]}]
 
        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(74.0, 74.0),
            constraints=constraints,
            start_time=18.0,
        )
 
        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["combo"][0]["combo_id"], "c_range_lowscore")
 
 
if __name__ == "__main__":
    unittest.main()
