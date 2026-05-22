import unittest

from closedloop.utils.mock_db import load_mock_data


ALLOWED_GROUPS = {"solo", "couple", "family", "friends", "business", "teen"}
ALLOWED_AGE_RANGES = {"3-6", "7-10", "11-17", "adult"}
ALLOWED_KID_MENU_STATUS = {"explicit", "possible", "none", "unknown"}
ALLOWED_STROLLER_FRIENDLY_STATUS = {"yes", "likely", "no", "unknown"}
ALLOWED_GIFT_TYPES = {"flower", "cake", "toy", "snack", "blind_box", "coffee"}


class TestPoiProfileFields(unittest.TestCase):
    def _assert_derived_score(self, value: dict):
        self.assertIsInstance(value, dict)
        self.assertIn("score", value)
        self.assertIn("confidence", value)
        self.assertIn("source", value)

        self.assertIsInstance(value["score"], (int, float))
        self.assertGreaterEqual(value["score"], 0.0)
        self.assertLessEqual(value["score"], 5.0)

        self.assertIsInstance(value["confidence"], (int, float))
        self.assertGreaterEqual(value["confidence"], 0.0)
        self.assertLessEqual(value["confidence"], 1.0)

        source = value["source"]
        self.assertIsInstance(source, dict)
        self.assertIn("sub_category", source)
        self.assertIn("matched_review_keywords", source)
        self.assertIn("rule", source)
        self.assertIsInstance(source["matched_review_keywords"], list)
        self.assertIsInstance(source["rule"], str)

    def _assert_common_fields(self, item: dict):
        self.assertIn("suitable_groups", item)
        self.assertIn("experience_tag", item)
        self.assertIn("romantic_score_derived", item)
        self.assertIn("photo_score_derived", item)
        self.assertIn("onsite_walking_level_estimated", item)
        self.assertIn("noise_level_estimated", item)

        self.assertIsInstance(item["suitable_groups"], list)
        self.assertTrue(set(item["suitable_groups"]).issubset(ALLOWED_GROUPS))
        self.assertIsInstance(item["experience_tag"], list)
        self.assertTrue(all(isinstance(x, str) for x in item["experience_tag"]))

        self._assert_derived_score(item["romantic_score_derived"])
        self._assert_derived_score(item["photo_score_derived"])
        self._assert_derived_score(item["onsite_walking_level_estimated"])
        self._assert_derived_score(item["noise_level_estimated"])

    def _assert_restaurant_child_fields(self, item: dict):
        self.assertIn("kid_menu_status", item)
        self.assertIn("stroller_friendly_status", item)
        self.assertIn("child_facility_tags", item)
        self.assertIn("child_friendly_score_derived", item)

        self.assertIn(item["kid_menu_status"], ALLOWED_KID_MENU_STATUS)
        self.assertIn(item["stroller_friendly_status"], ALLOWED_STROLLER_FRIENDLY_STATUS)
        self.assertIsInstance(item["child_facility_tags"], list)
        self.assertTrue(all(isinstance(x, str) for x in item["child_facility_tags"]))
        self._assert_derived_score(item["child_friendly_score_derived"])

    def _assert_gift_shop_special_fields(self, item: dict):
        self.assertIn("gift_type", item)
        self.assertIn("delivery_to_restaurant", item)
        self.assertIn("surprise_score_derived", item)

        self.assertIn(item["gift_type"], ALLOWED_GIFT_TYPES)
        self.assertIsInstance(item["delivery_to_restaurant"], bool)
        self._assert_derived_score(item["surprise_score_derived"])

    def test_restaurants_have_profile_fields(self):
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)
        for item in restaurants:
            self._assert_common_fields(item)
            self._assert_restaurant_child_fields(item)

    def test_activities_have_profile_fields_and_age_range(self):
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 40)
        for item in activities:
            self._assert_common_fields(item)
            self.assertIn("age_range", item)
            self.assertIsInstance(item["age_range"], list)
            self.assertGreater(len(item["age_range"]), 0)
            self.assertTrue(set(item["age_range"]).issubset(ALLOWED_AGE_RANGES))

    def test_gift_shops_have_profile_fields(self):
        gifts = load_mock_data("add_ons.json")
        self.assertEqual(len(gifts), 16)
        for item in gifts:
            self._assert_common_fields(item)
            self._assert_gift_shop_special_fields(item)


if __name__ == "__main__":
    unittest.main()
