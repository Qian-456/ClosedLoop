import unittest
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.nodes.rerank import score_item, rerank_node, _get_capacity_from_name

class TestRerankNode(unittest.TestCase):

    def setUp(self):
        self.base_constraints = Constraints(
            group_type="family",
            adult_count=2,
            child_count=1,
            child_ages=[5],
            budget=500.0,
            dietary_restrictions=[],
            preferred_distance="2km-5km",
            time_period="13:00-18:00",
            activity_preferences=["打卡点"]
        )

        self.restaurant_item = {
            "id": "r1",
            "type": "restaurant",
            "rating": 4.5,
            "distance_km": 3.0,
            "suitable_groups": ["family"],
            "tags": ["打卡点"]
        }

    def test_score_item(self):
        score = score_item(self.restaurant_item, {}, self.base_constraints)
        # rating: 4.5 / 5 * 65 = 58.5
        # distance: pref="2km-5km", actual=3.0 -> ratio = (5-3)/(5-2) = 2/3. 2/3 * 20 = 13.333 -> 13
        # suitable_groups: family in suitable -> +15
        # capacity: empty name returns capacity 1.0. Base effective_people (2 adult, 1 child(age 5=0.4)) = 2.4.
        # diff = |1.0 - 2.4| = 1.4 -> penalty = (1.4**2)*10 + 1.4*5 = 1.96*10 + 7 = 19.6 + 7 = 26.6 -> 26
        # organic_score: min(100, 58.5 + 13.333 + 15 - 26.6) = 60.233 -> 60
        self.assertEqual(score, 60)

    def test_score_item_matches_chinese_suitable_groups(self):
        family_restaurant = self.restaurant_item.copy()
        family_restaurant["suitable_groups"] = ["家庭亲子"]
        self.assertEqual(score_item(family_restaurant, {}, self.base_constraints), 60)

        friends_constraints = self.base_constraints.model_copy(update={"group_type": "friends"})
        friends_restaurant = self.restaurant_item.copy()
        friends_restaurant["suitable_groups"] = ["朋友聚会"]
        # Friends effective people: child_count=1 -> 2.4.
        # Penalty: diff = 1.4 -> 26.6
        # organic_score: 58.5 + 13.333 + 15 - 26.6 = 60.233 -> 60
        self.assertEqual(score_item(friends_restaurant, {}, friends_constraints), 60)

    def test_get_capacity_from_name(self):
        # 测试明确的 X大Y小
        self.assertEqual(_get_capacity_from_name("2大1小温馨家庭餐(含儿童玩具)"), 2.4) # 正则先匹配了 2大1小，2 + 1*0.4 = 2.4
        self.assertEqual(_get_capacity_from_name("1大1小亲子套票"), 1.4)
        self.assertEqual(_get_capacity_from_name("3大2小家庭豪华餐"), 3.8)
        
        # 测试具体数字
        self.assertEqual(_get_capacity_from_name("单人解馋小火锅"), 1.0)
        self.assertEqual(_get_capacity_from_name("情侣浪漫双人餐"), 2.0)
        self.assertEqual(_get_capacity_from_name("温馨三口之家套餐"), 2.6)
        self.assertEqual(_get_capacity_from_name("青年四人欢聚套餐"), 4.0)
        self.assertEqual(_get_capacity_from_name("八人豪华包厢宴"), 8.0)
        
        # 测试通用家庭
        self.assertEqual(_get_capacity_from_name("家庭健康轻食餐"), 2.6)
        self.assertEqual(_get_capacity_from_name("家庭广式晚餐"), 2.6)
        
        # 测试无法匹配的边缘情况（默认返回1.0）
        self.assertEqual(_get_capacity_from_name(""), 1.0)
        self.assertEqual(_get_capacity_from_name("神秘盲盒套餐"), 1.0)

    def test_score_item_matches_features(self):
        # 即使没有 suitable_groups，只要 features 包含关键词，依然可以加 15 分
        item_no_groups = self.restaurant_item.copy()
        item_no_groups["suitable_groups"] = []
        
        inner_item = {"name": "家庭欢乐餐", "features": "非常适合三口之家，老少皆宜的口味。"}
        score = score_item(item_no_groups, inner_item, self.base_constraints)
        
        # rating 58.5 + dist 13.333 + fit 15 (features matched)
        # capacity: "家庭欢乐餐" returns capacity 2.6. effective_people is 2.4.
        # diff = 0.2 -> penalty = 0.04*10 + 0.2*5 = 0.4 + 1.0 = 1.4
        # 58.5 + 13.333 + 15 - 1.4 = 85.433 -> 85
        self.assertEqual(score, 85)

        # Friends match
        friends_constraints = self.base_constraints.model_copy(update={"group_type": "friends"})
        inner_item_friends = {"name": "双人餐", "features": "专为情侣约会打造"}
        score_friends = score_item(item_no_groups, inner_item_friends, friends_constraints)
        # rating 58.5 + dist 13.333 + fit 15 (features matched) 
        # capacity: "双人餐" returns capacity 2.0. effective_people is 2.4.
        # diff = 0.4 -> penalty = 0.16*10 + 0.4*5 = 1.6 + 2.0 = 3.6
        # 58.5 + 13.333 + 15 - 3.6 = 83.233 -> 83
        self.assertEqual(score_friends, 83)

    def test_score_item_business_group(self):
        business_constraints = self.base_constraints.model_copy(update={"group_type": "business"})
        
        # 1. Test feature matching
        item_no_groups = self.restaurant_item.copy()
        item_no_groups["suitable_groups"] = []
        inner_item_business = {"name": "高端双人餐", "features": "环境高端，适合商务洽谈"}
        score_business_feat = score_item(item_no_groups, inner_item_business, business_constraints)
        # rating 58.5 + dist 13.333 + fit 15 (features matched)
        # capacity: "高端双人餐" returns capacity 2.0. effective_people is 2.4.
        # diff = 0.4 -> penalty = 0.16*10 + 0.4*5 = 1.6 + 2.0 = 3.6
        # 58.5 + 13.333 + 15 - 3.6 = 83.233 -> 83
        self.assertEqual(score_business_feat, 83)

        # 2. Test suitable_groups matching (the fixed bug)
        item_with_groups = self.restaurant_item.copy()
        item_with_groups["suitable_groups"] = ["商务宴请", "高端人士"]
        inner_item_no_feat = {"name": "高端双人餐", "features": "普通描述"}
        score_business_group = score_item(item_with_groups, inner_item_no_feat, business_constraints)
        # It should still get the +15 fit score from suitable_groups
        self.assertEqual(score_business_group, 83)
        
        # 3. Test English "business" keyword
        item_with_eng_group = self.restaurant_item.copy()
        item_with_eng_group["suitable_groups"] = ["business trip"]
        score_business_eng = score_item(item_with_eng_group, inner_item_no_feat, business_constraints)
        self.assertEqual(score_business_eng, 83)

    def test_score_item_capacity_penalty(self):
        # Base constraints: 2 adults + 1 child (age 5 -> 0.4) = 2.4 effective people
        # Base organic score (without penalty) for friends_restaurant in test_score_item:
        # rating 58.5 + dist 13.333 + fit 15 = 86.833
        base_organic = 86.833
        
        # Test 1: "双人套餐" -> capacity 2.0. diff = 0.4, penalty = 3.6
        score_2 = score_item(self.restaurant_item, {"name": "双人套餐"}, self.base_constraints)
        self.assertEqual(score_2, int(base_organic - 3.6)) # 83

        # Test 2: "三人套餐" -> capacity 3.0. diff = 0.6, penalty = 0.36*10 + 0.6*5 = 3.6 + 3.0 = 6.6
        score_3 = score_item(self.restaurant_item, {"name": "三人套餐"}, self.base_constraints)
        self.assertEqual(score_3, int(base_organic - 6.6)) # 80
        
        # Test 3: "四人套餐" -> capacity 4.0. diff = 1.6, penalty = 2.56*10 + 1.6*5 = 25.6 + 8.0 = 33.6
        score_4 = score_item(self.restaurant_item, {"name": "四人套餐"}, self.base_constraints)
        self.assertEqual(score_4, int(base_organic - 33.6)) # 53
        
        # Change constraints to 3 adults + 1 child (age 5) = 3.4 effective people
        constraints_3_1 = self.base_constraints.model_copy(update={"adult_count": 3})
        
        # "双人套餐" -> capacity 2.0. diff = 1.4, penalty = 1.96*10 + 1.4*5 = 19.6 + 7.0 = 26.6
        score_2_new = score_item(self.restaurant_item, {"name": "双人套餐"}, constraints_3_1)
        self.assertEqual(score_2_new, int(base_organic - 26.6)) # 60
        
        # "三人套餐" -> capacity 3.0. diff = 0.4, penalty = 3.6
        score_3_new = score_item(self.restaurant_item, {"name": "三人套餐"}, constraints_3_1)
        self.assertEqual(score_3_new, int(base_organic - 3.6)) # 83

    def test_rerank_node_requires_filter_step(self):
        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [self.restaurant_item],
                "nearby_activities": [],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node"], # Missing filter_node
            },
        )
        new_state = rerank_node(state)
        # Should return early without processing
        self.assertEqual(new_state["candidates"]["processed_steps"], ["retrieve_candidates_node"])

    def test_rerank_node_sorts_by_score(self):
        high_rating = self.restaurant_item.copy()
        high_rating["id"] = "r_high"
        high_rating["name"] = "High Rest"
        high_rating["rating"] = 4.9
        high_rating["combos"] = [{"combo_id": "c1", "name": "Combo 1", "price": 100, "suitable_time_slots": ["dinner", "late_night"]}]

        low_rating = self.restaurant_item.copy()
        low_rating["id"] = "r_low"
        low_rating["name"] = "Low Rest"
        low_rating["rating"] = 4.0
        low_rating["combos"] = [{"combo_id": "c2", "name": "Combo 2", "price": 50, "suitable_time_slots": ["lunch", "dinner"]}]

        tea_rating = self.restaurant_item.copy()
        tea_rating["id"] = "r_tea"
        tea_rating["name"] = "Tea Rest"
        tea_rating["rating"] = 4.7
        tea_rating["combos"] = [{"combo_id": "c3", "name": "Combo Tea", "price": 80, "suitable_time_slots": ["afternoon_tea", "lunch"]}]

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [low_rating, high_rating, tea_rating], # Input is unordered
                "nearby_activities": [],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node", "filter_node"],
            },
        )

        new_state = rerank_node(state)

        self.assertEqual(
            new_state["candidates"]["processed_steps"],
            ["retrieve_candidates_node", "filter_node", "rerank_node"],
        )

        ranked_lunch = new_state["candidates"]["ranked_lunch_combos"]
        ranked_dinner = new_state["candidates"]["ranked_dinner_combos"]
        ranked_tea = new_state["candidates"]["ranked_afternoon_tea_combos"]
        ranked_late_night = new_state["candidates"]["ranked_late_night_combos"]
        ranked_breakfast = new_state["candidates"]["ranked_breakfast_combos"]
        
        # Check separated lists
        self.assertEqual(len(ranked_lunch), 2)
        self.assertEqual([x["combo_id"] for x in ranked_lunch], ["c3", "c2"])
        
        # Check if parent context was properly mapped in one of the lists
        self.assertEqual(ranked_dinner[0]["restaurant_id"], "r_high")
        self.assertEqual(ranked_dinner[0]["restaurant_name"], "High Rest")
        self.assertTrue(all("score" in x for x in ranked_dinner))
        self.assertGreater(ranked_dinner[0]["score"], ranked_dinner[1]["score"])

        self.assertEqual(len(ranked_dinner), 2)
        self.assertEqual([x["combo_id"] for x in ranked_dinner], ["c1", "c2"])

        self.assertEqual(len(ranked_tea), 1)
        self.assertEqual([x["combo_id"] for x in ranked_tea], ["c3"])

        self.assertEqual(len(ranked_late_night), 1)
        self.assertEqual([x["combo_id"] for x in ranked_late_night], ["c1"])

        self.assertEqual(len(ranked_breakfast), 0)

if __name__ == '__main__':
    unittest.main()