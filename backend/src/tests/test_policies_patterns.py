import unittest

from closedloop.graph.policies import match_patterns


class TestPoliciesPatterns(unittest.TestCase):
    def test_match_patterns_friends_covers_lunch_tea_dinner_and_sml(self):
        start_times = [12.0, 15.0, 18.0]
        durations = [(2.5, 3.5), (3.5, 5.0), (5.0, 6.5)]
        for start_h in start_times:
            for d in durations:
                patterns = match_patterns(
                    group_type="friends",
                    child_profiles=[],
                    start_time_hours=start_h,
                    duration_hours_range=d,
                )
                self.assertTrue(patterns)
                self.assertTrue(all(p["group"] == "friends" for p in patterns))

    def test_match_patterns_family_covers_lunch_tea_dinner_and_sml(self):
        start_times = [12.0, 15.0, 18.0]
        durations = [(2.5, 3.5), (3.5, 5.0), (5.0, 6.5)]
        for start_h in start_times:
            for d in durations:
                patterns = match_patterns(
                    group_type="family",
                    child_profiles=[],
                    start_time_hours=start_h,
                    duration_hours_range=d,
                )
                self.assertTrue(patterns)
                self.assertTrue(all(p["group"] == "family_kids" for p in patterns))


if __name__ == "__main__":
    unittest.main()
