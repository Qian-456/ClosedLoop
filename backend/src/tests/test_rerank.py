import unittest
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.plan_subgraph.rerank import score_item, rerank_node, _get_capacity_from_name

class TestRerankNode(unittest.TestCase):

    def setUp(self):
        self.base_constraints = Constraints(
            group_type="family",
            adult_count=2,
            child_count=1,
            child_profiles=[("F", 5)],
            budget=500.0,
            dietary_restrictions=[],
            preferred_distance="2km-5km",
            time_period="13:00",
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
        score = score_item(self.restaurant_item, {"name": "温馨三口之家套餐"}, self.base_constraints)
        # rating: 4.5 / 5 * 65 = 58.5
        # distance: pref="2km-5km", actual=3.0 -> ratio = (5-3)/(5-2) = 2/3. 2/3 * 20 = 13.333
        # suitable_groups: family in suitable -> +15
        # activity_preferences: ["打卡点"] 命中 tags ["打卡点"] -> +5
        # capacity: "温馨三口之家套餐" -> 2.6; effective_people = 2.4; diff = 0.2 -> penalty 小
        self.assertEqual(score, 89)

    def test_score_item_matches_chinese_suitable_groups(self):
        family_restaurant = self.restaurant_item.copy()
        family_restaurant["suitable_groups"] = ["家庭亲子"]
        self.assertEqual(score_item(family_restaurant, {"name": "温馨三口之家套餐"}, self.base_constraints), 89)

        friends_constraints = self.base_constraints.model_copy(
            update={"group_type": "friends", "child_count": 0, "child_profiles": []}
        )
        friends_restaurant = self.restaurant_item.copy()
        friends_restaurant["suitable_groups"] = ["朋友聚会"]
        self.assertEqual(score_item(friends_restaurant, {"name": "温馨三口之家套餐"}, friends_constraints), 79)

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
        self.assertEqual(_get_capacity_from_name("4人畅吃派对"), 4.0)
        self.assertEqual(_get_capacity_from_name("俩人套餐"), 2.0)
        self.assertEqual(_get_capacity_from_name("两大一小亲子套餐"), 2.4)
        self.assertEqual(_get_capacity_from_name("单人/双人韩式大头贴"), 1.5)
        self.assertEqual(_get_capacity_from_name("1-2人套票"), 1.5)
        self.assertEqual(_get_capacity_from_name("2-3人套票"), 2.5)
        self.assertEqual(_get_capacity_from_name("3-4人套票"), 3.5)
        self.assertEqual(_get_capacity_from_name("2~3人套票"), 2.5)
        self.assertEqual(_get_capacity_from_name("2到3人套票"), 2.5)
        
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
        self.assertEqual(score, 89)

        # Friends match
        friends_constraints = self.base_constraints.model_copy(
            update={"group_type": "friends", "child_count": 0, "child_profiles": []}
        )
        inner_item_friends = {"name": "双人餐", "features": "专为情侣约会打造"}
        score_friends = score_item(item_no_groups, inner_item_friends, friends_constraints)
        # rating 58.5 + dist 13.333 + fit 15 (features matched) 
        # capacity: "双人餐" returns capacity 2.0. effective_people is 2.4.
        # diff = 0.4 -> penalty = 0.16*10 + 0.4*5 = 1.6 + 2.0 = 3.6
        self.assertEqual(score_friends, 91)

    def test_score_item_group_mismatch_penalty(self):
        item = self.restaurant_item.copy()
        ok = score_item(
            item,
            {"name": "家庭欢乐餐", "features": "非常适合三口之家，老少皆宜。"},
            self.base_constraints,
        )
        bad = score_item(
            item,
            {"name": "家庭欢乐餐", "features": "情侣约会专享双人餐，浪漫氛围。"},
            self.base_constraints,
        )
        self.assertGreater(ok, bad)

    def test_score_item_capacity_penalty(self):
        constraints = self.base_constraints.model_copy(update={"activity_preferences": []})
        item = self.restaurant_item.copy()
        item["tags"] = []

        base_no_penalty = score_item(item, {"name": "三口之家套餐"}, constraints)
        score_2 = score_item(item, {"name": "双人套餐"}, constraints)
        score_4 = score_item(item, {"name": "四人套餐"}, constraints)

        self.assertGreater(base_no_penalty, score_2)
        self.assertGreater(score_2, score_4)

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

    def test_rerank_node_no_longer_builds_indices_synchronously(self):
        high_rating = self.restaurant_item.copy()
        high_rating["id"] = "r_high"
        high_rating["name"] = "High Rest"
        high_rating["rating"] = 4.9
        high_rating["combos"] = [{"combo_id": "c1", "name": "Combo 1", "price": 100, "suitable_time_slots": ["dinner"]}]

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [high_rating],
                "nearby_activities": [],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node", "filter_node"],
            },
        )

        new_state = rerank_node(state)

        self.assertIn("ranked_dinner_combos", new_state["candidates"])

    def test_rerank_node_keeps_features(self):
        rest = self.restaurant_item.copy()
        rest["id"] = "r_feat"
        rest["name"] = "Feat Rest"
        rest["rating"] = 4.7
        rest["combos"] = [
            {
                "combo_id": "c_feat",
                "name": "家庭晚餐",
                "price": 100,
                "description": "desc",
                "features": "适合三口之家",
                "duration_mins": 60,
                "duration_std_dev": 10.0,
                "suitable_time_slots": ["dinner"],
            }
        ]

        act = {
            "id": "a_feat",
            "type": "activity",
            "name": "活动场地",
            "rating": 4.6,
            "distance_km": 3.0,
            "tags": [],
            "suitable_groups": [],
            "location": {"address": "x"},
            "packages": [
                {
                    "package_id": "p_feat",
                    "name": "单人50枚游戏币(抓娃娃)",
                    "price": 39.9,
                    "description": "desc",
                    "features": "逛街途中的可爱记录",
                    "duration_mins": 30,
                    "duration_std_dev": 10.0,
                    "start_time": None,
                }
            ],
        }

        gift_shop = {
            "id": "s_feat",
            "type": "gift_shop",
            "name": "礼物店",
            "rating": 4.7,
            "distance_km": 3.0,
            "tags": [],
            "suitable_groups": [],
            "location": {"address": "x"},
            "gifts": [
                {
                    "gift_id": "g_feat",
                    "name": "盲盒",
                    "price": 69.0,
                    "description": "desc",
                    "features": "拆开瞬间的未知感",
                    "stock": 200,
                }
            ],
        }

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [rest],
                "nearby_activities": [act],
                "nearby_gifts": [gift_shop],
                "processed_steps": ["retrieve_candidates_node", "filter_node"],
            },
        )

        new_state = rerank_node(state)

        ranked_dinner = new_state["candidates"]["ranked_dinner_combos"]
        self.assertEqual(ranked_dinner[0]["combo_id"], "c_feat")
        self.assertEqual(ranked_dinner[0]["features"], "适合三口之家")

        ranked_packages = new_state["candidates"]["ranked_packages"]
        ranked_light_packages = new_state["candidates"]["ranked_light_packages"]
        self.assertEqual(len(ranked_packages), 0)
        self.assertEqual(ranked_light_packages[0]["package_id"], "p_feat")
        self.assertEqual(ranked_light_packages[0]["features"], "逛街途中的可爱记录")

        ranked_gifts = new_state["candidates"]["ranked_gifts"]
        self.assertEqual(ranked_gifts[0]["gift_id"], "g_feat")
        self.assertEqual(ranked_gifts[0]["features"], "拆开瞬间的未知感")

if __name__ == '__main__':
    unittest.main()
