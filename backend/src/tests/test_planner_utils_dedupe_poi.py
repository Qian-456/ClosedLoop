import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations


class TestPlannerUtilsDedupePoi(unittest.TestCase):
    def test_dedupe_activity_by_venue_id(self):
        queues = {
            "activity": [
                {
                    "package_id": "p1",
                    "venue_id": "v1",
                    "name": "活动1",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "package_id": "p2",
                    "venue_id": "v1",
                    "name": "活动2",
                    "duration_mins": 60,
                    "score": 79,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "package_id": "p3",
                    "venue_id": "v2",
                    "name": "活动3",
                    "duration_mins": 60,
                    "score": 78,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity", "activity"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(146.0, 146.0),
        )

        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertEqual(len(plans), 4)
        for p in plans:
            venue_ids = [i.get("venue_id") for i in p.get("combo", [])]
            self.assertEqual(len(venue_ids), 2)
            self.assertNotEqual(venue_ids[0], venue_ids[1])

    def test_repeat_place_fallback_marked_when_no_unique_activity_candidates(self):
        queues = {
            "activity": [
                {
                    "package_id": "p1",
                    "venue_id": "v1",
                    "name": "活动1",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "package_id": "p2",
                    "venue_id": "v1",
                    "name": "活动2",
                    "duration_mins": 60,
                    "score": 79,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity", "activity"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(146.0, 146.0),
        )

        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertEqual(len(plans), 2)
        for p in plans:
            self.assertTrue(
                any(i.get("repeat_place_fallback") is True for i in p.get("combo", []))
            )

    def test_dedupe_restaurant_by_restaurant_id(self):
        queues = {
            "activity": [],
            "gift_shop": [],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [
                {
                    "combo_id": "c1",
                    "restaurant_id": "r1",
                    "name": "晚餐1",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "combo_id": "c2",
                    "restaurant_id": "r1",
                    "name": "晚餐2",
                    "duration_mins": 60,
                    "score": 79,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "combo_id": "c3",
                    "restaurant_id": "r2",
                    "name": "晚餐3",
                    "duration_mins": 60,
                    "score": 78,
                    "price": 0.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["restaurant:dinner", "restaurant:dinner"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(146.0, 146.0),
            start_time=17.0,
        )

        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertEqual(len(plans), 4)
        for p in plans:
            restaurant_ids = [i.get("restaurant_id") for i in p.get("combo", [])]
            self.assertEqual(len(restaurant_ids), 2)
            self.assertNotEqual(restaurant_ids[0], restaurant_ids[1])

    def test_dedupe_gift_shop_by_shop_id(self):
        queues = {
            "activity": [],
            "gift_shop": [
                {
                    "gift_id": "g1",
                    "shop_id": "s1",
                    "name": "礼物1",
                    "score": 80,
                    "price": 10.0,
                    "receive_duration_mins": 10,
                    "delivery_radius_km": 5.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "gift_id": "g2",
                    "shop_id": "s1",
                    "name": "礼物2",
                    "score": 79,
                    "price": 10.0,
                    "receive_duration_mins": 10,
                    "delivery_radius_km": 5.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
                {
                    "gift_id": "g3",
                    "shop_id": "s2",
                    "name": "礼物3",
                    "score": 78,
                    "price": 10.0,
                    "receive_duration_mins": 10,
                    "delivery_radius_km": 5.0,
                    "location": {"longitude": 0.0, "latitude": 0.0},
                },
            ],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["gift_shop", "gift_shop"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(32.0, 32.0),
        )

        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertEqual(len(plans), 4)
        for p in plans:
            shop_ids = [i.get("shop_id") for i in p.get("combo", [])]
            self.assertEqual(len(shop_ids), 2)
            self.assertNotEqual(shop_ids[0], shop_ids[1])


if __name__ == "__main__":
    unittest.main()
