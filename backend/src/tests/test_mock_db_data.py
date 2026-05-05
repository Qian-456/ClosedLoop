import unittest

from closedloop.utils.mock_db import load_mock_data


class TestMockDbData(unittest.TestCase):
    """
    Validate mock_db dataset integrity and basic realism constraints.
    """

    def test_activities_count_and_schema(self):
        """
        Ensure activities.json has 15 items and required keys exist.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 15)

        required_keys = {
            "venue_id",
            "name",
            "category",
            "packages",
            "rating",
            "operating_hours",
            "tags",
            "location",
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
            "restaurant_id",
            "name",
            "combos",
            "rating",
            "tags",
            "location",
        }
        for item in restaurants:
            self.assertTrue(required_keys.issubset(set(item.keys())))


if __name__ == "__main__":
    unittest.main()

