import unittest

from closedloop.utils.mock_db import load_mock_data


ALLOWED_KID_MENU_STATUS = {"explicit", "possible", "none", "unknown"}
ALLOWED_STROLLER_FRIENDLY_STATUS = {"yes", "likely", "no", "unknown"}


class TestRestaurantChildFields(unittest.TestCase):
    def test_restaurants_have_child_fields(self):
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        for item in restaurants:
            self.assertIn("kid_menu_status", item)
            self.assertIn("stroller_friendly_status", item)
            self.assertIn("child_facility_tags", item)
            self.assertIn("child_friendly_score_derived", item)

            self.assertIn(item["kid_menu_status"], ALLOWED_KID_MENU_STATUS)
            self.assertIn(item["stroller_friendly_status"], ALLOWED_STROLLER_FRIENDLY_STATUS)

            self.assertIsInstance(item["child_facility_tags"], list)
            self.assertTrue(all(isinstance(x, str) for x in item["child_facility_tags"]))

            derived = item["child_friendly_score_derived"]
            self.assertIsInstance(derived, dict)
            self.assertIn("score", derived)
            self.assertIn("confidence", derived)
            self.assertIn("source", derived)

            self.assertIsInstance(derived["score"], (int, float))
            self.assertGreaterEqual(derived["score"], 0.0)
            self.assertLessEqual(derived["score"], 5.0)

            self.assertIsInstance(derived["confidence"], (int, float))
            self.assertGreaterEqual(derived["confidence"], 0.0)
            self.assertLessEqual(derived["confidence"], 1.0)

            source = derived["source"]
            self.assertIsInstance(source, dict)
            self.assertIn("sub_category", source)
            self.assertIn("matched_review_keywords", source)
            self.assertIn("rule", source)


if __name__ == "__main__":
    unittest.main()

