import unittest
from unittest.mock import patch
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.nodes.retrieve import (
    retrieve_candidates_node,
    filter_rank_node,
    hard_filter,
    rule_filter,
    score_item,
)

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
            "type": "gift_shop",
            "price": 80,
            "tags": ["儿童", "蛋糕"],
            "supported_target_types": ["restaurant"],
            "distance_km": 2.0,
            "open_time": "10:00",
            "close_time": "21:00",
            "duration_minutes": 20,
            "suitable_groups": ["家庭亲子"],
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

    def test_score_item_matches_chinese_suitable_groups(self):
        family_restaurant = self.restaurant_item.copy()
        family_restaurant["suitable_groups"] = ["家庭亲子"]
        self.assertGreaterEqual(score_item(family_restaurant, self.base_constraints), 45 + 14 + 15)

        friends_constraints = self.base_constraints.model_copy(update={"group_type": "friends"})
        friends_restaurant = self.restaurant_item.copy()
        friends_restaurant["suitable_groups"] = ["朋友聚会"]
        self.assertGreaterEqual(score_item(friends_restaurant, friends_constraints), 45 + 14 + 15)

    @patch('closedloop.graph.nodes.retrieve.load_mock_data')
    def test_retrieve_candidates_node_loads_mock_db_applies_15km_cap_and_sets_steps(self, mock_load):
        scored_restaurant = self.restaurant_item.copy()
        scored_restaurant["score"] = 999

        scored_activity = self.activity_item.copy()
        scored_activity["score"] = 999

        far_restaurant = self.restaurant_item.copy()
        far_restaurant["id"] = "r_far"
        far_restaurant["distance_km"] = 16.0

        far_activity = self.activity_item.copy()
        far_activity["id"] = "a_far"
        far_activity["distance_km"] = 20.0

        mock_load.side_effect = lambda f: {
            "restaurants.json": [scored_restaurant, far_restaurant],
            "activities.json": [scored_activity, far_activity],
            "add_ons.json": [self.addon_item],
        }[f]

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints
        )

        new_state = retrieve_candidates_node(state)

        self.assertNotIn("processed_steps", new_state)
        self.assertIn("candidates", new_state)
        candidates = new_state["candidates"]
        self.assertIn("processed_steps", candidates)
        self.assertEqual(candidates["processed_steps"], ["retrieve_candidates_node"])

        self.assertIn("nearby_restaurants", candidates)
        self.assertEqual([x["id"] for x in candidates["nearby_restaurants"]], ["r1"])
        self.assertTrue(all("score" not in x for x in candidates["nearby_restaurants"]))

        self.assertIn("nearby_activities", candidates)
        self.assertEqual([x["id"] for x in candidates["nearby_activities"]], ["a1"])
        self.assertTrue(all("score" not in x for x in candidates["nearby_activities"]))

        self.assertIn("nearby_gifts", candidates)
        self.assertEqual([x["id"] for x in candidates["nearby_gifts"]], ["o1"])

    @patch("closedloop.graph.nodes.retrieve.load_mock_data")
    def test_filter_rank_node_requires_retrieve_step_and_does_not_load_db(self, mock_load):
        mock_load.side_effect = AssertionError("filter_rank_node 不应加载 MockDB 数据")

        high_rating = self.restaurant_item.copy()
        high_rating["id"] = "r_high"
        high_rating["rating"] = 4.9

        low_rating = self.restaurant_item.copy()
        low_rating["id"] = "r_low"
        low_rating["rating"] = 4.0

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [low_rating, high_rating],
                "nearby_activities": [],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node"],
            },
        )

        new_state = filter_rank_node(state)

        self.assertNotIn("processed_steps", new_state)
        self.assertEqual(
            new_state["candidates"]["processed_steps"],
            ["retrieve_candidates_node", "filter_rank_node"],
        )

        restaurants = new_state["candidates"]["nearby_restaurants"]
        self.assertEqual([x["id"] for x in restaurants], ["r_high", "r_low"])
        self.assertTrue(all("score" in x for x in restaurants))
        self.assertGreater(restaurants[0]["score"], restaurants[1]["score"])

    def test_filter_rank_node_returns_empty_when_processed_steps_not_exactly_retrieve(self):
        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [self.restaurant_item],
                "nearby_activities": [],
                "nearby_gifts": [],
                "processed_steps": [],
            },
        )
        new_state = filter_rank_node(state)
        self.assertEqual(new_state["candidates"]["nearby_restaurants"], [])
        self.assertEqual(new_state["candidates"]["nearby_activities"], [])
        self.assertEqual(new_state["candidates"]["nearby_gifts"], [])

        state_missing_steps = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [self.restaurant_item],
                "nearby_activities": [],
                "nearby_gifts": [],
            },
        )
        new_state_missing_steps = filter_rank_node(state_missing_steps)
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_restaurants"], [])
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_activities"], [])
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_gifts"], [])

if __name__ == '__main__':
    unittest.main()
