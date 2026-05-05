import unittest
from closedloop.contracts.state import Constraints, ClosedLoopState
from closedloop.graph.nodes.rerank import score_item, rerank_node

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
        # rating: 4.5 * 10 = 45
        # distance: pref="2km-5km", min=2.0, max=5.0, actual=3.0 -> ratio = (5.0 - 3.0)/(5.0 - 2.0) = 2.0 / 3.0 = 0.666...
        # score = 0.666... * 20 = 13.333... -> int(13.333...) = 13
        # suitable_groups: family in suitable -> +15
        # tags: "打卡点" in tags, but tag_matching_score is hardcoded to 0
        # commercial_score: 0
        # capacity: no name provided, capacity=0, diff=0, penalty=0
        # total: 45 + 13 + 15 + 0 + 0 = 73
        self.assertEqual(score, 73)

    def test_score_item_matches_chinese_suitable_groups(self):
        family_restaurant = self.restaurant_item.copy()
        family_restaurant["suitable_groups"] = ["家庭亲子"]
        self.assertEqual(score_item(family_restaurant, {}, self.base_constraints), 73)

        friends_constraints = self.base_constraints.model_copy(update={"group_type": "friends"})
        friends_restaurant = self.restaurant_item.copy()
        friends_restaurant["suitable_groups"] = ["朋友聚会"]
        self.assertEqual(score_item(friends_restaurant, {}, friends_constraints), 73)

    def test_score_item_capacity_penalty(self):
        # Base constraints: 2 adults + 1 child (age 5 -> 0.4) = 2.4 effective people
        # Base score for this restaurant (from test_score_item) is 73.
        
        # Test 1: "双人套餐" -> capacity 2.0. diff = 0.4, penalty = 4
        score_2 = score_item(self.restaurant_item, {"name": "双人套餐"}, self.base_constraints)
        self.assertEqual(score_2, 73 - 4)

        # Test 2: "三人套餐" -> capacity 3.0. diff = 0.6, penalty = 6
        score_3 = score_item(self.restaurant_item, {"name": "三人套餐"}, self.base_constraints)
        self.assertEqual(score_3, 73 - 6)
        
        # Test 3: "四人套餐" -> capacity 4.0. diff = 1.6, penalty = 16
        score_4 = score_item(self.restaurant_item, {"name": "四人套餐"}, self.base_constraints)
        self.assertEqual(score_4, 73 - 16)
        
        # Change constraints to 3 adults + 1 child (age 5) = 3.4 effective people
        constraints_3_1 = self.base_constraints.model_copy(update={"adult_count": 3})
        
        # "双人套餐" -> capacity 2.0. diff = 1.4, penalty = 14
        score_2_new = score_item(self.restaurant_item, {"name": "双人套餐"}, constraints_3_1)
        self.assertEqual(score_2_new, 73 - 14)
        
        # "三人套餐" -> capacity 3.0. diff = 0.4, penalty = 4
        score_3_new = score_item(self.restaurant_item, {"name": "三人套餐"}, constraints_3_1)
        self.assertEqual(score_3_new, 73 - 4)

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
        high_rating["combos"] = [{"combo_id": "c1", "name": "Combo 1", "price": 100}]

        low_rating = self.restaurant_item.copy()
        low_rating["id"] = "r_low"
        low_rating["name"] = "Low Rest"
        low_rating["rating"] = 4.0
        low_rating["combos"] = [{"combo_id": "c2", "name": "Combo 2", "price": 50}]

        state = ClosedLoopState(
            user_input="Test input",
            constraints=self.base_constraints,
            candidates={
                "nearby_restaurants": [low_rating, high_rating], # Input is unordered
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

        ranked_combos = new_state["candidates"]["ranked_combos"]
        # The rerank node should output flattened combos sorted by score descending
        self.assertEqual(len(ranked_combos), 2)
        self.assertEqual([x["combo_id"] for x in ranked_combos], ["c1", "c2"])
        
        # Check if parent context was properly mapped
        self.assertEqual(ranked_combos[0]["restaurant_id"], "r_high")
        self.assertEqual(ranked_combos[0]["restaurant_name"], "High Rest")
        self.assertTrue(all("score" in x for x in ranked_combos))
        self.assertGreater(ranked_combos[0]["score"], ranked_combos[1]["score"])

if __name__ == '__main__':
    unittest.main()