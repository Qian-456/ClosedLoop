import unittest

from closedloop.utils.mock_db import load_mock_data


class TestMockDbData(unittest.TestCase):
    """
    Validate mock_db dataset integrity and basic realism constraints.
    """

    def test_activities_count_and_schema(self):
        """
        Ensure activities.json has 40 items and required keys exist.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 40)

        required_keys = {
            "id",
            "name",
            "category",
            "sub_category",
            "district",
            "address",
            "latitude",
            "longitude",
            "business_hours",
            "indoor",
            "review_keywords",
            "is_free",
            "packages",
            "rating",
            "reviews_count",
            "tags",
        }
        for item in activities:
            self.assertTrue(required_keys.issubset(set(item.keys())))

    def test_restaurants_count_and_reservation_ratio(self):
        """
        Ensure restaurants.json has 32 items and required keys exist.
        """
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        required_keys = {
            "id",
            "name",
            "combos",
            "category",
            "sub_category",
            "district",
            "address",
            "latitude",
            "longitude",
            "business_hours",
            "indoor",
            "review_keywords",
            "rating",
            "tags",
        }
        for item in restaurants:
            self.assertTrue(required_keys.issubset(set(item.keys())))


if __name__ == "__main__":
    unittest.main()
