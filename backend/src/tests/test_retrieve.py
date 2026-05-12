import unittest
from unittest.mock import patch
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.nodes.retrieve import (
    retrieve_candidates_node,
    filter_node,
    hard_filter,
    rule_filter,
)

class TestRetrieveCandidates(unittest.TestCase):
    
    def setUp(self):
        self.base_constraints = Constraints(
            group_type="family",
            budget=300.0,
            dietary_restrictions=["辣", "海鲜"],
            preferred_distance="2km-5km",
            time_period="12:00-18:00",
            duration_hours=2.0,
            activity_preferences=["游乐", "室内"],
            adult_count=2,
            child_count=1,
            child_ages=[5],
        )
        
        self.restaurant_item = {
            "restaurant_id": "r1",
            "type": "restaurant",
            "combos": [
                {"combo_id": "c1", "price": 100},
                {"combo_id": "c2", "price": 250}
            ],
            "location": {"distance_to_center_km": 3.0},
            "distance_km": 3.0,
            "tags": ["家庭亲子", "清淡"],
            "avoid_tags": ["吵闹"],
            "suitable_groups": ["family", "friends"],
            "rating": 4.5,
            "duration_minutes": 60
        }
        
        self.activity_item = {
            "venue_id": "a1",
            "type": "activity",
            "packages": [
                {"package_id": "p1", "price": 150}
            ],
            "location": {"distance_to_center_km": 4.0},
            "distance_km": 4.0,
            "tags": ["游乐", "室内"],
            "avoid_tags": [],
            "suitable_groups": ["family"],
            "min_child_age": 3,
            "max_child_age": 10,
            "rating": 4.8,
            "duration_minutes": 120
        }
        
        self.addon_item = {
            "shop_id": "o1",
            "type": "gift_shop",
            "gifts": [
                {"gift_id": "g1", "price": 80}
            ],
            "tags": ["儿童", "蛋糕"],
            "supported_target_types": ["restaurant"],
            "location": {"distance_to_center_km": 2.0},
            "distance_km": 2.0,
            "duration_minutes": 20,
            "suitable_groups": ["家庭亲子"],
            "description": "生日蛋糕"
        }

    def test_hard_filter_pass(self):
        # 正常通过: 餐厅 budget 300 * 0.7 = 210
        # combos: c1=100 (<=210, pass), c2=250 (>210, fail) -> rest should pass with c1
        cheap_restaurant = self.restaurant_item.copy()
        cheap_restaurant["combos"] = [c.copy() for c in cheap_restaurant["combos"]]
        self.assertTrue(hard_filter(cheap_restaurant, self.base_constraints))
        self.assertEqual(len(cheap_restaurant["combos"]), 1)
        self.assertEqual(cheap_restaurant["combos"][0]["combo_id"], "c1")
        
        # activity: p1=150 (<=210, pass)
        activity_copy = self.activity_item.copy()
        self.assertTrue(hard_filter(activity_copy, self.base_constraints))
        
        # gift: g1=80 (<= 300*0.3 = 90, pass)
        cheap_addon = self.addon_item.copy()
        self.assertTrue(hard_filter(cheap_addon, self.base_constraints))

    def test_hard_filter_budget_fail(self):
        # 超出预算: 餐厅只有超过 210 的套餐
        expensive_restaurant = self.restaurant_item.copy()
        expensive_restaurant["combos"] = [{"combo_id": "c1", "price": 250}]
        self.assertFalse(hard_filter(expensive_restaurant, self.base_constraints))
        
        # add-on 总价超出预算: 100 > 90 (300 * 0.3)
        expensive_addon = self.addon_item.copy()
        expensive_addon["gifts"] = [{"gift_id": "g1", "price": 100}]
        self.assertFalse(hard_filter(expensive_addon, self.base_constraints))

    def test_hard_filter_distance_fail(self):
        # preferred_distance: "2km-5km" -> max is 6.0
        far_restaurant = self.restaurant_item.copy()
        far_restaurant["distance_km"] = 7.0
        self.assertFalse(hard_filter(far_restaurant, self.base_constraints))
        
        # "<2km" -> max 3.0
        strict_constraints = self.base_constraints.model_copy(update={"preferred_distance": "<2km"})
        activity_copy = self.activity_item.copy()
        activity_copy["distance_km"] = 4.0
        self.assertFalse(hard_filter(activity_copy, strict_constraints)) # 4.0 > 3.0

    def test_hard_filter_time_fail(self):
        # 营业时间不匹配: constraints "12:00-18:00"
        closed_restaurant = self.restaurant_item.copy()
        closed_restaurant["open_time"] = "19:00"
        closed_restaurant["close_time"] = "23:00"
        self.assertFalse(hard_filter(closed_restaurant, self.base_constraints))

    def test_rule_filter_pass(self):
        self.assertTrue(rule_filter(self.restaurant_item, self.base_constraints))
        self.assertTrue(rule_filter(self.activity_item, self.base_constraints))

    def test_rule_filter_family_bar_fail(self):
        # 家庭带孩子不应该去酒吧
        bar_restaurant = self.restaurant_item.copy()
        bar_restaurant["tags"] = ["酒吧", "精酿"]
        self.assertFalse(rule_filter(bar_restaurant, self.base_constraints))

    def test_rule_filter_age_based_fail(self):
        # 孩子 5 岁 (<12) 不能去夜宵/密室/盲盒
        late_night_restaurant = self.restaurant_item.copy()
        late_night_restaurant["tags"] = ["夜宵", "深夜"]
        self.assertFalse(rule_filter(late_night_restaurant, self.base_constraints))
        
        # 测试盲盒过滤
        blind_box_shop = self.activity_item.copy()
        blind_box_shop["packages"] = [{"package_id": "p1", "name": "盲盒端盒", "description": "随机抽取"}]
        self.assertFalse(rule_filter(blind_box_shop, self.base_constraints))
        
        # 孩子 5 岁 (<6) 不能去恐怖/刺激/剧本杀/重口味
        scary_activity = self.activity_item.copy()
        scary_activity["tags"] = ["恐怖", "密室"]
        self.assertFalse(rule_filter(scary_activity, self.base_constraints))
        
        heavy_taste_restaurant = self.restaurant_item.copy()
        heavy_taste_restaurant["tags"] = ["重口味"]
        self.assertFalse(rule_filter(heavy_taste_restaurant, self.base_constraints))
        
        # 修改约束：孩子 14 岁
        teen_constraints = self.base_constraints.model_copy(update={"child_ages": [14]})
        # 14岁可以去密室、夜宵、剧本杀、盲盒
        self.assertTrue(rule_filter(late_night_restaurant, teen_constraints))
        self.assertTrue(rule_filter(blind_box_shop, teen_constraints))
        
        # 但是 14 岁 (<16) 不能去网吧/极限失重
        internet_cafe = self.activity_item.copy()
        internet_cafe["tags"] = ["网吧", "电竞"]
        self.assertFalse(rule_filter(internet_cafe, teen_constraints))
        
        vr_extreme = self.activity_item.copy()
        vr_extreme["packages"] = [{"package_id": "v1", "name": "VR失重体验", "description": "极限刺激"}]
        self.assertFalse(rule_filter(vr_extreme, teen_constraints))
        
        # 测试对所有未成年人的酒精和成人向过滤 (即便 17 岁)
        almost_adult_constraints = self.base_constraints.model_copy(update={"child_ages": [17]})
        alcohol_restaurant = self.restaurant_item.copy()
        alcohol_restaurant["combos"] = [{"combo_id": "c1", "name": "红酒牛排", "description": "送精选红酒一瓶"}]
        self.assertFalse(rule_filter(alcohol_restaurant, almost_adult_constraints))
        
        # 测试在描述或名字中包含敏感词的情况
        scary_description_activity = self.activity_item.copy()
        scary_description_activity["packages"] = [
            {"package_id": "p2", "name": "普通的活动", "description": "带有一点点恐怖元素", "price": 100}
        ]
        # 因为包含了"恐怖"，对于 5 岁的小孩应该被拦截
        self.assertFalse(rule_filter(scary_description_activity, self.base_constraints))
        
        scary_name_restaurant = self.restaurant_item.copy()
        scary_name_restaurant["combos"] = [
            {"combo_id": "c3", "name": "深夜烧烤狂欢", "price": 100}
        ]
        # 对于 5 岁小孩应该拦截
        self.assertFalse(rule_filter(scary_name_restaurant, self.base_constraints))

    def test_rule_filter_dietary_fail(self):
        # 饮食禁忌: "辣"
        spicy_restaurant = self.restaurant_item.copy()
        spicy_restaurant["tags"] = ["热辣", "火锅"]
        self.assertFalse(rule_filter(spicy_restaurant, self.base_constraints))

        # 饮食禁忌: "生冷"
        cold_constraints = self.base_constraints.model_copy(update={"dietary_restrictions": ["生冷"]})
        cold_restaurant = self.restaurant_item.copy()
        cold_restaurant["tags"] = ["沙拉", "轻食"]
        self.assertFalse(rule_filter(cold_restaurant, cold_constraints))

        # 饮食禁忌: "甜"
        sweet_constraints = self.base_constraints.model_copy(update={"dietary_restrictions": ["甜"]})
        sweet_restaurant = self.restaurant_item.copy()
        sweet_restaurant["tags"] = ["甜点", "奶茶"]
        self.assertFalse(rule_filter(sweet_restaurant, sweet_constraints))



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
    def test_filter_node_requires_retrieve_step_and_does_not_load_db(self, mock_load):
        mock_load.side_effect = AssertionError("filter_node 不应加载 MockDB 数据")

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

        new_state = filter_node(state)

        self.assertNotIn("processed_steps", new_state)
        self.assertEqual(
            new_state["candidates"]["processed_steps"],
            ["retrieve_candidates_node", "filter_node"],
        )

        restaurants = new_state["candidates"]["nearby_restaurants"]
        # The filter node should preserve the order and not add scores
        self.assertEqual([x["id"] for x in restaurants], ["r_low", "r_high"])
        self.assertFalse(any("score" in x for x in restaurants))

    def test_filter_node_returns_empty_when_processed_steps_not_exactly_retrieve(self):
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
        new_state = filter_node(state)
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
        new_state_missing_steps = filter_node(state_missing_steps)
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_restaurants"], [])
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_activities"], [])
        self.assertEqual(new_state_missing_steps["candidates"]["nearby_gifts"], [])

if __name__ == '__main__':
    unittest.main()
