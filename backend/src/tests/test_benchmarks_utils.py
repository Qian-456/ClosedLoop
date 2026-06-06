import os
import sys
import unittest

# Add src to path so we can import backend modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.utils.benchmarks import (
    build_default_constraints_cases,
    percentile,
    summarize_latencies,
)


class TestBenchmarksUtils(unittest.TestCase):
    def test_percentile_nearest_rank(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(percentile(values, 0), 1.0)
        self.assertEqual(percentile(values, 50), 3.0)
        self.assertEqual(percentile(values, 100), 5.0)
        self.assertEqual(percentile(values, 99), 5.0)

    def test_percentile_rejects_invalid(self):
        with self.assertRaises(ValueError):
            percentile([], 50)
        with self.assertRaises(ValueError):
            percentile([1], -1)
        with self.assertRaises(ValueError):
            percentile([1], 101)

    def test_summarize_latencies(self):
        latencies = [100.0, 120.0, 110.0, 90.0, 200.0]
        summary = summarize_latencies(latencies, success_count=5, error_count=0)
        self.assertEqual(summary.count, 5)
        self.assertEqual(summary.success_count, 5)
        self.assertEqual(summary.error_count, 0)
        self.assertAlmostEqual(summary.min_ms, 90.0)
        self.assertAlmostEqual(summary.max_ms, 200.0)
        self.assertAlmostEqual(summary.p50_ms, 110.0)
        self.assertAlmostEqual(summary.p99_ms, 200.0)

    def test_build_default_cases_has_required_fields(self):
        cases = build_default_constraints_cases()
        self.assertEqual(len(cases), 20)
        for case in cases:
            self.assertIn("group_type", case)
            self.assertIn("budget", case)
            self.assertIn("time_period", case)


if __name__ == "__main__":
    unittest.main()
