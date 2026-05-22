import re
import unittest

from closedloop.utils.mock_db import load_mock_data


PEOPLE_PATTERN = re.compile(
    r"(单人|一人|双人|两人|三人|四人|五人|六人|\d+人|\d+大\d+小|\d+大|\d+小|三口之家|四口之家)"
)


def _count_sections(desc: str) -> int:
    if not isinstance(desc, str) or not desc:
        return 0
    parts = [p.strip() for p in desc.split("；") if p.strip()]
    return sum(1 for p in parts if "：" in p)


class TestRestaurantComboStandardization(unittest.TestCase):
    def test_restaurant_distribution_by_sub_category(self):
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        def _count(allowed: set[str]) -> int:
            return sum(1 for r in restaurants if (r.get("sub_category") in allowed))

        self.assertEqual(_count({"粤菜", "茶餐厅"}), 3)
        self.assertEqual(_count({"江浙菜", "本帮菜"}), 3)
        self.assertEqual(_count({"家常菜", "社区小馆"}), 2)
        self.assertEqual(_count({"商场家庭餐厅", "连锁简餐"}), 2)

        self.assertEqual(_count({"西餐"}), 2)
        self.assertEqual(_count({"Brunch"}), 1)
        self.assertEqual(_count({"景观餐厅"}), 1)
        self.assertEqual(_count({"甜品下午茶"}), 1)
        self.assertEqual(_count({"日式定食"}), 1)
        self.assertEqual(_count({"融合菜"}), 1)

        self.assertEqual(_count({"东北菜"}), 2)
        self.assertEqual(_count({"韩餐烤肉"}), 1)
        self.assertEqual(_count({"披萨炸鸡"}), 1)
        self.assertEqual(_count({"火锅"}), 1)
        self.assertEqual(_count({"烤鱼"}), 1)
        self.assertEqual(_count({"猪肚鸡"}), 1)

        self.assertEqual(_count({"亲子餐厅"}), 1)
        self.assertEqual(_count({"儿童套餐友好"}), 1)
        self.assertEqual(_count({"商场儿童友好"}), 1)
        self.assertEqual(_count({"烘焙轻食亲子"}), 1)

        self.assertEqual(_count({"咖啡简餐"}), 1)
        self.assertEqual(_count({"日式拉面乌冬"}), 1)
        self.assertEqual(_count({"面包烘焙简餐"}), 1)
        self.assertEqual(_count({"粉面饭轻餐"}), 1)

    def test_all_combo_names_have_people_expression(self):
        restaurants = load_mock_data("restaurants.json")
        self.assertEqual(len(restaurants), 32)

        for r in restaurants:
            combos = r.get("combos", []) or []
            self.assertGreater(len(combos), 0)
            for c in combos:
                name = c.get("name", "")
                self.assertRegex(name, PEOPLE_PATTERN)

    def test_combo_description_is_sectionalized(self):
        restaurants = load_mock_data("restaurants.json")
        for r in restaurants:
            for c in r.get("combos", []) or []:
                desc = c.get("description", "")
                self.assertGreaterEqual(_count_sections(desc), 2)

    def test_combo_features_present_and_not_copy_description(self):
        restaurants = load_mock_data("restaurants.json")
        for r in restaurants:
            for c in r.get("combos", []) or []:
                desc = c.get("description", "")
                feat = c.get("features", "")
                self.assertIsInstance(feat, str)
                self.assertTrue(feat.strip())
                self.assertNotEqual(feat.strip(), desc.strip())


if __name__ == "__main__":
    unittest.main()
