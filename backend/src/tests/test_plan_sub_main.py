import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plan_sub_main import PlanRequest, run_plan_subgraph


class TestPlanSubMain(unittest.TestCase):
    @patch("plan_sub_main.logger")
    @patch("plan_sub_main.SearchIndexer")
    @patch("plan_sub_main.build_subgraph_plan")
    def test_run_plan_subgraph_returns_candidates_and_logs_summary(
        self,
        mock_build_subgraph_plan,
        mock_search_indexer,
        mock_logger,
    ):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "itinerary": {"status": "ok", "plans": [{"id": "A"}]},
            "candidates": {
                "ranked_dinner_combos": [{"combo_id": "c1"}],
                "ranked_packages": [{"package_id": "p1"}],
                "ranked_light_packages": [],
                "ranked_gifts": [],
            },
        }
        mock_build_subgraph_plan.return_value = mock_graph

        mock_indexer = MagicMock()
        mock_search_indexer.get_instance.return_value = mock_indexer

        resp = run_plan_subgraph(
            PlanRequest(
                constraints={"group_type": "friends", "budget": 200, "time_period": "18:00"},
                top_k=1,
                session_id="thread-123",
            )
        )

        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["itinerary"], mock_graph.invoke.return_value["itinerary"])
        self.assertEqual(resp["candidates"], mock_graph.invoke.return_value["candidates"])
        mock_indexer.schedule_plan_indices.assert_called_once_with(
            mock_graph.invoke.return_value["candidates"],
            session_id="thread-123",
        )
        self.assertTrue(
            any(
                "restaurant_count=1" in str(call.args[0])
                and "activity_count=1" in str(call.args[0])
                and "gift_count=0" in str(call.args[0])
                for call in mock_logger.info.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
