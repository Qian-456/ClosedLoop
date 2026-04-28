import unittest
from unittest.mock import patch
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.nodes.retrieve import retrieve_candidates, hard_filter, rule_filter, score_item

class TestRetrieveCandidates(unittest.TestCase):
    
    def setUp(self):
        self.base_constraints = Constraints(
            group_type="family",
            people_count=3,
            budget=300.0,
            dietary_restrictions=["辣", "海鲜"],
            preferred_distance="2km-5km",
            time_period="12:00-18:00",
            duration_hours=2.0,
            activity_preferences=["游乐", "室内"],
            child_age=5
        )
        
        self.restaurant_item = {
            "id": "r1",
            "type": "restaurant",
            "avg_price_per_person": 60,
            "distance_km": 3.0,
            "open_time": "10:00",
            "close_time": "22:00",
            "tags": ["家庭亲子", "清淡"],
            "avoid_tags": ["吵闹"],
            "suitable_groups": ["family", "friends"],
            "rating": 4.5,
            "duration_minutes": 60
        }
        
        self.activity_item = {
            "id": "a1",
            "type": "activity",
            "price_per_person": 50,
            "distance_km": 4.0,
            "open_time": "09:00",
            "close_time": "20:00",
            "tags": ["游乐", "室内"],
            "avoid_tags": [],
            "suitable_groups": ["family"],
            "min_child_age": 3,
            "max_child_age": 10,
            "rating": 4.8,
            "duration_minutes": 120
        }
        
        self.addon_item = {
            "id": "o1",
            "type": "add_on",
            "price": 80,
            "tags": ["儿童", "蛋糕"],
            "supported_target_types": ["restaurant"],
            "description": "生日蛋糕"
        }

    def test_hard_filter_pass(self):
        # 正常通过: 餐厅 60 * 3 = 180 <= 300 * 0.7 (210)
        cheap_restaurant = self.restaurant_item.copy()
        cheap_restaurant["avg_price_per_person"] = 60
        self.assertTrue(hard_filter(cheap_restaurant, self.base_constraints))
        self.assertTrue(hard_filter(self.activity_item, self.base_constraints))
        
        cheap_addon = self.addon_item.copy()
        cheap_addon["price"] = 50 # <= 300 * 0.3 (90)
        self.assertTrue(hard_filter(cheap_addon, self.base_constraints))

    def test_hard_filter_budget_fail(self):
        # 超出预算: 餐厅 80 * 3 = 240 > 210 (300 * 0.7)
        expensive_restaurant = self.restaurant_item.copy()
        expensive_restaurant["avg_price_per_person"] = 80
        self.assertFalse(hard_filter(expensive_restaurant, self.base_constraints))
        
        # add-on 总价超出预算: 100 > 90 (300 * 0.3)
        expensive_addon = self.addon_item.copy()
        expensive_addon["price"] = 100
        self.assertFalse(hard_filter(expensive_addon, self.base_constraints))

    def test_hard_filter_distance_fail(self):
        # preferred_distance: "2km-5km" -> max is 6.0
        far_restaurant = self.restaurant_item.copy()
        far_restaurant["distance_km"] = 7.0
        self.assertFalse(hard_filter(far_restaurant, self.base_constraints))
        
        # "<2km" -> max 3.0
        strict_constraints = self.base_constraints.model_copy(update={"preferred_distance": "<2km"})
        self.assertFalse(hard_filter(self.activity_item, strict_constraints)) # 4.0 > 3.0

    def test_hard_filter_time_fail(self):
        # 营业时间不匹配: constraints "12:00-18:00"
        closed_restaurant = self.restaurant_item.copy()
        closed_restaurant["open_time"] = "19:00"
        closed_restaurant["close_time"] = "23:00"
        self.assertFalse(hard_filter(closed_restaurant, self.base_constraints))

    def test_hard_filter_child_age_fail(self):
        # 孩子年龄不符
        toddler_activity = self.activity_item.copy()
        toddler_activity["min_child_age"] = 8
        self.assertFalse(hard_filter(toddler_activity, self.base_constraints)) # child_age is 5

    def test_rule_filter_pass(self):
        self.assertTrue(rule_filter(self.restaurant_item, self.base_constraints))
        self.assertTrue(rule_filter(self.activity_item, self.base_constraints))

    def test_rule_filter_family_bar_fail(self):
        # 家庭带孩子不应该去酒吧
        bar_restaurant = self.restaurant_item.copy()
        bar_restaurant["tags"] = ["酒吧", "精酿"]
        self.assertFalse(rule_filter(bar_restaurant, self.base_constraints))

    def test_rule_filter_dietary_fail(self):
        # 饮食禁忌: "辣"
        spicy_restaurant = self.restaurant_item.copy()
        spicy_restaurant["tags"] = ["热辣", "火锅"]
        self.assertFalse(rule_filter(spicy_restaurant, self.base_constraints))

    def test_score_item(self):
        score = score_item(self.restaurant_item, self.base_constraints)
        # rating: 4.5 * 10 = 45
        # distance: max(0, 10 - 3) * 2 = 14
        # suitable_groups: family in suitable -> +15
        # duration match: None (duration check not added to total score initially?) 
        self.assertEqual(score, 45 + 14 + 15)

    @patch('closedloop.graph.nodes.retrieve.load_mock_data')
    def test_retrieve_candidates_node(self, mock_load):
        # Mock data
        mock_load.side_effect = lambda f: {
            "restaurants.json": [self.restaurant_item],
            "activities.json": [self.activity_item],
            "add_ons.json": [self.addon_item]
        }[f]
        
        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints
        )
        
        new_state = retrieve_candidates(state)
        
        self.assertIn("candidates", new_state)
        candidates = new_state["candidates"]
        
        self.assertIn("nearby_restaurants", candidates)
        self.assertEqual(len(candidates["nearby_restaurants"]), 1)
        self.assertEqual(candidates["nearby_restaurants"][0]["id"], "r1")
        
        self.assertIn("nearby_activities", candidates)
        self.assertEqual(len(candidates["nearby_activities"]), 1)
        
        self.assertIn("nearby_gifts", candidates)
        self.assertEqual(len(candidates["nearby_gifts"]), 1)

if __name__ == '__main__':
    unittest.main()
