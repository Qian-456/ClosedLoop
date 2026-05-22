import re
import unittest

from closedloop.utils.mock_db import load_mock_data


class TestRestaurantAndGiftCandidateResilience(unittest.TestCase):
    """
    Validate candidate resilience constraints for restaurants and gift shops.
    """

    def test_restaurants_have_afternoon_tea_and_late_night_coverage(self):
        """
        Ensure restaurants provide a minimum coverage for afternoon_tea and late_night slots.
        """
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        slot_counts: dict[str, int] = {}
        for r in restaurants:
            for c in r.get("combos") or []:
                for s in c.get("suitable_time_slots") or []:
                    slot_counts[s] = slot_counts.get(s, 0) + 1

        self.assertGreaterEqual(slot_counts.get("afternoon_tea", 0), 20)
        self.assertGreaterEqual(slot_counts.get("late_night", 0), 14)

    def test_restaurants_combo_count_and_budget_floor(self):
        """
        Ensure each restaurant has 5 combos and at least one low-price combo.
        """
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        for r in restaurants:
            combos = r.get("combos") or []
            self.assertEqual(len(combos), 5, msg=f"restaurant_id={r.get('id')} expected 5 combos")
            self.assertTrue(
                any((c.get("price") or 0) <= 60 for c in combos),
                msg=f"restaurant_id={r.get('id')} expected low price combo <= 60",
            )

    def test_family_friendly_restaurants_have_safe_combo(self):
        """
        Ensure kid-friendly restaurants keep at least one combo name free from mismatch trigger words.
        """
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        forbidden = ("单人", "双人", "约会", "情侣", "工作餐", "独处")
        for r in restaurants:
            if (r.get("kid_menu_status") or "unknown") not in ("possible", "yes"):
                continue
            combos = r.get("combos") or []
            self.assertTrue(
                any(not any(k in (c.get("name") or "") for k in forbidden) for c in combos),
                msg=f"restaurant_id={r.get('id')} expected at least one safe combo name",
            )

    def test_gift_shops_gifts_count_and_budget_floor(self):
        """
        Ensure each gift shop has 6 gifts and at least one low-price gift.
        """
        shops = load_mock_data("add_ons.json")
        self.assertEqual(len(shops), 16)

        for s in shops:
            gifts = s.get("gifts") or []
            self.assertEqual(len(gifts), 6, msg=f"gift_shop_id={s.get('id')} expected 6 gifts")
            self.assertTrue(
                any((g.get("price") or 0) <= 50 for g in gifts),
                msg=f"gift_shop_id={s.get('id')} expected low price gift <= 50",
            )

    def test_gift_shops_family_safe_bucket_no_blindbox_terms(self):
        """
        Ensure family/kids/culture gift shops avoid blindbox trigger terms.
        """
        shops = load_mock_data("add_ons.json")
        self.assertEqual(len(shops), 16)

        forbidden = ("盲盒", "随机", "端盒")
        kids_markers = ("3-6岁", "7-10岁", "儿童", "亲子")

        for s in shops:
            suitable_groups = set(s.get("suitable_groups") or [])
            tags = s.get("tags") or []
            is_familyish = ("family" in suitable_groups) or any(any(m in (t or "") for m in kids_markers) for t in tags)
            is_culture = (s.get("gift_type") or "") in ("culture", "stationery", "postcard")

            if not (is_familyish or is_culture):
                continue

            head_text = f"{s.get('name','')} {' '.join(tags)}"
            self.assertFalse(any(k in head_text for k in forbidden), msg=f"gift_shop_id={s.get('id')} forbidden in shop name/tags")

            for g in s.get("gifts") or []:
                text = f"{g.get('name','')} {g.get('description','')} {g.get('features','')}"
                self.assertFalse(any(k in text for k in forbidden), msg=f"gift_shop_id={s.get('id')} gift_id={g.get('gift_id')} forbidden term")


if __name__ == "__main__":
    unittest.main()
