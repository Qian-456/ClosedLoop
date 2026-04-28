import unittest

from closedloop.utils.mock_db import load_mock_data


class TestMockDbData(unittest.TestCase):
    """
    Validate mock_db dataset integrity and basic realism constraints.
    """

    def test_activities_count_and_schema(self):
        """
        Ensure activities.json has 20 items and required keys exist.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 20)

        required_keys = {
            "id",
            "name",
            "type",
            "category",
            "distance_km",
            "price_per_person",
            "rating",
            "open_time",
            "close_time",
            "duration_minutes",
            "tags",
            "avoid_tags",
            "suitable_groups",
            "supports_reservation",
            "location",
            "description",
        }
        for item in activities:
            self.assertTrue(required_keys.issubset(set(item.keys())))

    def test_restaurants_count_and_reservation_ratio(self):
        """
        Ensure restaurants.json has 20 items and reservation ratio is small.
        """
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 20)

        required_keys = {
            "id",
            "name",
            "type",
            "category",
            "distance_km",
            "avg_price_per_person",
            "rating",
            "open_time",
            "close_time",
            "avg_wait_minutes",
            "duration_minutes",
            "tags",
            "avoid_tags",
            "suitable_groups",
            "has_child_seat",
            "supports_reservation",
            "supports_queue",
            "location",
            "description",
        }
        for item in restaurants:
            self.assertTrue(required_keys.issubset(set(item.keys())))

        supports_reservation_count = sum(1 for r in restaurants if r.get("supports_reservation") is True)
        self.assertLessEqual(supports_reservation_count, 5)


if __name__ == "__main__":
    unittest.main()

