import unittest

from closedloop.graph.nodes.planner import _rewrite_commutes_for_taxi_preference


class TestCommuteRewriteTaxiPreference(unittest.TestCase):
    """
    Validate taxi preference commute rewrite behavior.
    """

    def test_rewrite_keeps_delivery_segments(self):
        """
        Ensure delivery-like segments (mode=None) remain time=0/cost=0 to avoid fake commutes.
        """
        commutes = [
            {"time": 0.0, "cost": 0.0, "mode": None, "distance": 0.0},
            {"time": 12.0, "cost": 0.0, "mode": "walking", "distance": 1.0},
            {"time": 7.0, "cost": 10.0, "mode": "taxi", "distance": 2.0},
            {"time": 25.0, "cost": 10.0, "mode": "taxi", "distance": 6.0},
        ]

        rewritten = _rewrite_commutes_for_taxi_preference(commutes)
        self.assertEqual(len(rewritten), 4)
        self.assertEqual(rewritten[0]["mode"], None)
        self.assertEqual(rewritten[0]["time"], 0.0)
        self.assertEqual(rewritten[0]["cost"], 0.0)
        self.assertEqual(rewritten[0]["distance"], 0.0)


if __name__ == "__main__":
    unittest.main()

