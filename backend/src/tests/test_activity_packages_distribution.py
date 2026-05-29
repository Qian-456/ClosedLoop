import re
import unittest

from closedloop.utils.mock_db import load_mock_data


class TestActivityPackagesDistribution(unittest.TestCase):
    """
    Validate activity packages count and semantic distribution alignment.
    """

    def _infer_profile(self, activity: dict) -> str:
        """Infer the generator-side profile from stable activity fields."""
        sub_category = str(activity.get("sub_category") or "")
        tags = set(activity.get("tags") or [])
        suitable_groups = set(activity.get("suitable_groups") or [])
        age_range = set(activity.get("age_range") or [])
        package_names = self._paid_package_names(activity)
        package_text = " ".join(package_names)

        if sub_category in ("商场综合体", "城市公园/湖边步道", "大型书城", "综合娱乐中心") or {"多选项", "兜底"} & tags:
            return "universal"
        if any(k in package_text for k in ("1大1小", "2大1小", "2大2小", "亲子", "家庭")):
            return "family"
        if "11-17" in age_range:
            return "teen_11_17"
        if {"3-6", "7-10"} & age_range or "family" in suitable_groups:
            return "family"
        if "friends" in suitable_groups:
            return "friends_lively"
        return "unknown"

    def _join_package_text(self, packages: list[dict]) -> str:
        parts: list[str] = []
        for p in packages or []:
            parts.append(str(p.get("name") or ""))
            parts.append(str(p.get("description") or ""))
            parts.append(str(p.get("features") or ""))
        return " ".join(parts)

    def _paid_package_names(self, activity: dict) -> list[str]:
        """Return paid package names for easier distribution assertions."""
        if bool(activity.get("is_free") is True):
            return []
        return [str(p.get("name") or "") for p in (activity.get("packages") or [])]

    def test_activity_package_count(self):
        """
        Ensure free activities have exactly 2 packages, paid activities have exactly 3 packages.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 40)

        for a in activities:
            is_free = bool(a.get("is_free") is True)
            packages = a.get("packages") or []
            self.assertIsInstance(packages, list)
            if is_free:
                self.assertEqual(len(packages), 2, msg=f"activity_id={a.get('id')} expected 2 packages")
            else:
                self.assertEqual(len(packages), 3, msg=f"activity_id={a.get('id')} expected 3 packages")

    def test_paid_activity_packages_should_use_explicit_people_expressions(self):
        """
        Ensure paid activity packages carry explicit people expressions instead of implicit defaults.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 40)

        allowed_patterns = (
            "双人",
            "三人",
            "四人",
            "1大1小",
            "2大1小",
            "2大2小",
        )

        for activity in activities:
            if bool(activity.get("is_free") is True):
                continue

            package_names = self._paid_package_names(activity)
            self.assertEqual(len(package_names), 3, msg=f"activity_id={activity.get('id')} expected 3 paid packages")
            self.assertTrue(
                all(any(pattern in name for pattern in allowed_patterns) for name in package_names),
                msg=f"activity_id={activity.get('id')} expected explicit people expressions: {package_names}",
            )

    def test_family_paid_activities_should_not_default_to_single_person_packages(self):
        """Ensure paid family activities no longer use single-person packages by default."""
        activities = load_mock_data("activities.json")

        family_paid = [
            a for a in activities
            if "family" == self._infer_profile(a)
            and not bool(a.get("is_free") is True)
        ]
        self.assertGreater(len(family_paid), 0)

        for activity in family_paid:
            package_names = self._paid_package_names(activity)
            self.assertEqual(len(package_names), 3)
            self.assertFalse(
                any(any(k in name for k in ("单人", "一人", "独处")) for name in package_names),
                msg=f"activity_id={activity.get('id')} should not contain single-person paid packages: {package_names}",
            )
            self.assertTrue(
                any("2大1小" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} expected at least one 2大1小 package: {package_names}",
            )

    def test_friends_paid_activities_should_center_on_four_people_with_small_group_options(self):
        """Ensure paid friends activities keep 4-person mainline and retain 2/3-person options."""
        activities = load_mock_data("activities.json")

        friends_paid = [
            a for a in activities
            if "friends_lively" == self._infer_profile(a)
            and not bool(a.get("is_free") is True)
        ]
        self.assertGreater(len(friends_paid), 0)

        for activity in friends_paid:
            package_names = self._paid_package_names(activity)
            self.assertEqual(len(package_names), 3)
            self.assertTrue(
                any("四人" in name or "4人" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} expected a 4-person main package: {package_names}",
            )
            self.assertTrue(
                any(any(k in name for k in ("双人", "2人", "三人", "3人")) for name in package_names),
                msg=f"activity_id={activity.get('id')} expected a 2-3 person fallback package: {package_names}",
            )
            self.assertFalse(
                any("六人团建包场" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} should not default to six-person team building: {package_names}",
            )

    def test_universal_paid_activities_should_use_mixed_small_group_packages(self):
        """Ensure paid universal activities use 2/3/4-person mixes instead of large-party defaults."""
        activities = load_mock_data("activities.json")

        universal_paid = [
            a for a in activities
            if "universal" == self._infer_profile(a)
            and not bool(a.get("is_free") is True)
        ]
        self.assertGreater(len(universal_paid), 0)

        for activity in universal_paid:
            package_names = self._paid_package_names(activity)
            self.assertEqual(len(package_names), 3)
            self.assertTrue(
                any("双人" in name or "2人" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} expected a 2-person package: {package_names}",
            )
            self.assertTrue(
                any("三人" in name or "3人" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} expected a 3-person package: {package_names}",
            )
            self.assertTrue(
                any("四人" in name or "4人" in name for name in package_names),
                msg=f"activity_id={activity.get('id')} expected a 4-person package: {package_names}",
            )


if __name__ == "__main__":
    unittest.main()
