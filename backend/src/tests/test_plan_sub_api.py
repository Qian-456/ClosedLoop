import os
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path so we can import backend modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from closedloop.graph.tools.plan_sub_api import build_plan_sub_candidate_urls, request_plan_sub_json


class TestPlanSubApi(unittest.TestCase):
    def test_build_plan_sub_candidate_urls_for_item_in_local_mode(self):
        urls = build_plan_sub_candidate_urls(
            "http://localhost:8001/plan",
            f"/item/combo_001",
            network_mode="local",
        )

        self.assertEqual(
            urls,
            [
                "http://localhost:8001/item/combo_001",
                "http://127.0.0.1:8001/item/combo_001",
            ],
        )

    def test_build_plan_sub_candidate_urls_for_item_in_docker_mode(self):
        urls = build_plan_sub_candidate_urls(
            "http://plan_sub_backend:8001/plan",
            f"/item/combo_001",
            network_mode="docker",
        )

        self.assertEqual(
            urls,
            [
                "http://plan_sub_backend:8001/item/combo_001",
            ],
        )

    @patch("closedloop.graph.tools.plan_sub_api.httpx.Client")
    def test_request_plan_sub_json_retries_next_candidate_in_docker_mode(self, mock_client_class):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"status": "success"}
        mock_client.request.side_effect = [
            socket.gaierror(-5, "No address associated with hostname"),
            mock_response,
        ]
        mock_client.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        result = request_plan_sub_json(
            method="GET",
            configured_url="http://plan-sub-primary:8001/plan",
            target_path="/item/combo_001",
            phase="adjust_plan_item",
            params={"session_id": "s1"},
            timeout=5.0,
            network_mode="docker",
        )

        self.assertEqual(result, {"status": "success"})
        called_urls = [call.args[1] for call in mock_client.request.call_args_list]
        self.assertEqual(
            called_urls,
            [
                "http://plan-sub-primary:8001/item/combo_001",
                "http://plan_sub_backend:8001/item/combo_001",
            ],
        )

    @patch("closedloop.graph.tools.plan_sub_api.time.perf_counter")
    @patch("closedloop.graph.tools.plan_sub_api.httpx.Client")
    def test_request_plan_sub_json_should_shrink_timeout_by_remaining_budget(
        self,
        mock_client_class,
        mock_perf_counter,
    ):
        mock_perf_counter.side_effect = [
            0.0,  # started_at
            0.0,  # before first request
            0.8,  # before second request
        ]

        mock_client = MagicMock()
        mock_client.request.side_effect = [
            httpx.ConnectTimeout("timeout"),
            httpx.ConnectTimeout("timeout"),
        ]
        mock_client.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        with self.assertRaises(Exception):
            request_plan_sub_json(
                method="GET",
                configured_url="http://localhost:8001/plan",
                target_path="/item/combo_001",
                phase="adjust_plan_item",
                params={"session_id": "s1"},
                timeout=1.0,
                network_mode="local",
            )

        first_timeout = mock_client.request.call_args_list[0].kwargs.get("timeout")
        second_timeout = mock_client.request.call_args_list[1].kwargs.get("timeout")
        self.assertAlmostEqual(first_timeout, 1.0, places=3)
        self.assertAlmostEqual(second_timeout, 0.2, places=3)


if __name__ == "__main__":
    unittest.main()
