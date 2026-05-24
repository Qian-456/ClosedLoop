import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.plan_subgraph.planner_utils import generate_and_score_combinations


class TestPlannerUtilsGiftDelivery(unittest.TestCase):
    def test_gift_delivery_radius_prunes_out_of_range(self):
        queues = {
            "activity": [
                {
                    "package_id": "a1",
                    "name": "活动1",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 10.0, "latitude": 0.0},
                },
                {
                    "package_id": "a2",
                    "name": "活动2",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 5.0, "latitude": 0.0},
                },
            ],
            "gift_shop": [
                {
                    "gift_id": "g1",
                    "name": "鲜花",
                    "score": 80,
                    "price": 50.0,
                    "delivery_radius_km": 1.0,
                    "receive_duration_mins": 10,
                    "receive_duration_std_dev": 3.0,
                    "location": {"longitude": 12.0, "latitude": 0.0},
                }
            ],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity", "gift_shop", "activity"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(0.0, 1000.0),
        )

        self.assertEqual(missing_types, set())
        self.assertEqual(valid_count, 0)
        self.assertEqual(plans, [])

    def test_gift_does_not_change_position_and_commutes_skip_gift(self):
        queues = {
            "activity": [
                {
                    "package_id": "a1",
                    "name": "活动1",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 10.0, "latitude": 0.0},
                },
                {
                    "package_id": "a2",
                    "name": "活动2",
                    "duration_mins": 60,
                    "score": 80,
                    "price": 0.0,
                    "location": {"longitude": 5.0, "latitude": 0.0},
                },
            ],
            "gift_shop": [
                {
                    "gift_id": "g1",
                    "name": "鲜花",
                    "score": 80,
                    "price": 50.0,
                    "delivery_radius_km": 5.0,
                    "receive_duration_mins": 10,
                    "receive_duration_std_dev": 3.0,
                    "location": {"longitude": 12.0, "latitude": 0.0},
                }
            ],
            "breakfast": [],
            "lunch": [],
            "afternoon_tea": [],
            "dinner": [],
            "late_night": [],
        }
        patterns = [{"pattern_id": "P1", "steps": ["activity", "gift_shop", "activity"]}]

        plans, valid_count, missing_types = generate_and_score_combinations(
            queues=queues,
            patterns=patterns,
            budget=1000.0,
            required_duration_range_mins=(0.0, 1000.0),
        )

        self.assertEqual(missing_types, set())
        self.assertGreater(valid_count, 0)
        self.assertGreaterEqual(len(plans), 1)

        plan = plans[0]
        commutes = plan["commutes"]
        self.assertEqual(len(commutes), 4)

        self.assertEqual(commutes[0]["distance"], 10.0)
        self.assertEqual(commutes[1]["distance"], 0.0)
        self.assertEqual(commutes[1]["time"], 0.0)
        self.assertEqual(commutes[2]["distance"], 5.0)
        self.assertEqual(commutes[3]["distance"], 5.0)


if __name__ == "__main__":
    unittest.main()

