import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.graph.plan_subgraph.planner_utils import compute_time_window_params, compute_time_score


class TestTimeRangeScoring(unittest.TestCase):
    def test_time_window_params_4_to_6_hours(self):
        duration_range_mins = (240.0, 360.0)
        params = compute_time_window_params(duration_range_mins)

        self.assertAlmostEqual(params["hard_min_mins"], 225.0)
        self.assertAlmostEqual(params["hard_max_mins"], 375.0)
        self.assertAlmostEqual(params["mid_mins"], 300.0)
        self.assertAlmostEqual(params["full_min_mins"], 240.0)
        self.assertAlmostEqual(params["full_max_mins"], 360.0)

    def test_time_score_full_zone_is_100(self):
        params = compute_time_window_params((240.0, 360.0))
        self.assertAlmostEqual(compute_time_score(240.0, params), 100.0)
        self.assertAlmostEqual(compute_time_score(300.0, params), 100.0)
        self.assertAlmostEqual(compute_time_score(360.0, params), 100.0)

    def test_time_score_hard_boundary_is_60(self):
        params = compute_time_window_params((240.0, 360.0))
        self.assertAlmostEqual(compute_time_score(225.0, params), 60.0, places=2)
        self.assertAlmostEqual(compute_time_score(375.0, params), 60.0, places=2)

    def test_time_score_outside_hard_boundary_is_0(self):
        params = compute_time_window_params((240.0, 360.0))
        self.assertAlmostEqual(compute_time_score(224.0, params), 0.0)
        self.assertAlmostEqual(compute_time_score(376.0, params), 0.0)

    def test_time_score_monotonic_decreasing_outside_full_zone(self):
        params = compute_time_window_params((240.0, 360.0))

        s1 = compute_time_score(360.0, params)
        s2 = compute_time_score(370.0, params)
        s3 = compute_time_score(375.0, params)

        self.assertGreaterEqual(s1, s2)
        self.assertGreaterEqual(s2, s3)
        self.assertGreaterEqual(s3, 60.0)


if __name__ == "__main__":
    unittest.main()
