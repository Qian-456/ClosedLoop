import unittest

from closedloop.graph.policies import match_patterns


class TestPoliciesPatterns(unittest.TestCase):
    def test_match_patterns_solo_covers_lunch_tea_dinner_and_sml(self):
        start_times = [12.0, 15.0, 18.0]
        durations = [(2.5, 3.5), (3.5, 5.0), (5.0, 6.5)]
        for start_h in start_times:
            for d in durations:
                patterns = match_patterns(
                    group_type="solo",
                    child_profiles=[],
                    start_time_hours=start_h,
                    duration_hours_range=d,
                )
                self.assertTrue(patterns)
                self.assertTrue(all(p["group"] == "solo" for p in patterns))

    def test_match_patterns_couple_covers_lunch_tea_dinner_and_sml(self):
        start_times = [12.0, 15.0, 18.0]
        durations = [(2.5, 3.5), (3.5, 5.0), (5.0, 6.5)]
        for start_h in start_times:
            for d in durations:
                patterns = match_patterns(
                    group_type="couple",
                    child_profiles=[],
                    start_time_hours=start_h,
                    duration_hours_range=d,
                )
                self.assertTrue(patterns)
                self.assertTrue(all(p["group"] == "couple" for p in patterns))


if __name__ == "__main__":
    unittest.main()
