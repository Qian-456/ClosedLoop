import re
import unittest

from closedloop.utils.mock_db import load_mock_data


class TestActivityPackagesDistribution(unittest.TestCase):
    """
    Validate activity packages count and semantic distribution alignment.
    """

    def _infer_profile(self, review_keywords: list[str]) -> str:
        kws = set(review_keywords or [])
        if "适合单人" in kws:
            return "solo_quiet"
        if "适合约会" in kws:
            return "couple_photo"
        if "适合亲子" in kws:
            return "family"
        if "适合青少年" in kws:
            return "teen_11_17"
        if "适合朋友聚会" in kws:
            return "friends_lively"
        if "通用兜底" in kws:
            return "universal"
        return "unknown"

    def _join_package_text(self, packages: list[dict]) -> str:
        parts: list[str] = []
        for p in packages or []:
            parts.append(str(p.get("name") or ""))
            parts.append(str(p.get("description") or ""))
            parts.append(str(p.get("features") or ""))
        return " ".join(parts)

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

    def test_activity_package_semantics(self):
        """
        Ensure packages avoid group-mismatch trigger words for the inferred activity profile.
        """
        activities = load_mock_data("activities.json")
        self.assertEqual(len(activities), 40)

        for a in activities:
            profile = self._infer_profile(a.get("review_keywords") or [])
            packages = a.get("packages") or []
            text = self._join_package_text(packages)

            if profile == "solo_quiet":
                forbidden = ("约会", "情侣", "双人", "亲子", "家庭", "团建", "聚会", "多人")
                self.assertTrue(any(k in text for k in ("单人", "一人", "独处")))
                self.assertFalse(any(k in text for k in forbidden), msg=f"activity_id={a.get('id')} hit forbidden={forbidden}")
            elif profile == "couple_photo":
                forbidden = ("单人", "一人", "独处", "工作餐", "亲子", "家庭", "团建", "聚会", "多人")
                self.assertTrue(any(k in text for k in ("双人", "情侣", "约会")))
                self.assertFalse(any(k in text for k in forbidden), msg=f"activity_id={a.get('id')} hit forbidden={forbidden}")
            elif profile == "family":
                forbidden = ("单人", "一人", "独处", "约会", "情侣", "双人")
                self.assertTrue(any(k in text for k in ("亲子", "家庭", "大", "小")))
                self.assertFalse(any(k in text for k in forbidden), msg=f"activity_id={a.get('id')} hit forbidden={forbidden}")
            elif profile == "friends_lively":
                forbidden = ("单人", "一人", "独处", "约会", "情侣", "亲子", "家庭", "2大1小", "2大2小")
                self.assertTrue(any(k in text for k in ("聚会", "团建", "多人", "三人", "四人", "五人", "六人")))
                self.assertFalse(any(k in text for k in forbidden), msg=f"activity_id={a.get('id')} hit forbidden={forbidden}")
            elif profile == "teen_11_17":
                forbidden = ("亲子", "家庭", "2大1小", "2大2小", "约会", "情侣", "单人", "独处")
                self.assertTrue(re.search(r"\d+\s*[-~到]\s*\d+\s*人", text) is not None)
                self.assertFalse(any(k in text for k in forbidden), msg=f"activity_id={a.get('id')} hit forbidden={forbidden}")
            elif profile == "universal":
                has_flexible = any(
                    re.search(r"\d+\s*[-~到]\s*\d+\s*人", p.get("name") or "") for p in packages
                ) or any("单人/双人" in (p.get("name") or "") or "单人 / 双人" in (p.get("name") or "") for p in packages)
                self.assertTrue(has_flexible, msg=f"activity_id={a.get('id')} expected flexible people expr in package name")
            else:
                self.fail(f"activity_id={a.get('id')} unknown profile from review_keywords={a.get('review_keywords')}")


if __name__ == "__main__":
    unittest.main()

