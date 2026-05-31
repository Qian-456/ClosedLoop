import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.search_tool import SearchCandidatesInput, search_candidates


class TestSearchTool(unittest.TestCase):
    @patch("httpx.Client")
    @patch("closedloop.graph.tools.search_tool.logger")
    @patch("closedloop.graph.tools.search_tool.get_config")
    @patch("closedloop.graph.tools.search_tool.LoggerManager.setup")
    def test_search_candidates_sends_ranked_only_candidates_with_subcatory(
        self,
        _mock_logger_setup,
        mock_get_config,
        mock_logger,
        mock_httpx_client,
    ):
        mock_get_config.return_value = type(
            "FakeConfig",
            (),
            {
                "SEARCH_SUB_API_URL": "http://127.0.0.1:8002/search",
                "TOOL_HTTP_TIMEOUT_SECS": 3.0,
            },
        )()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "status": "success",
            "results": [
                {
                    "combo_id": "state_combo",
                    "name": "亲子儿童乐园套餐",
                    "description": "适合带娃午餐",
                    "features": "儿童乐园 宝宝椅",
                    "price": 128,
                    "duration_mins": 90,
                    "suitable_groups": ["family"],
                    "child_facility_tags": ["儿童乐园", "宝宝椅"],
                    "distance_km": 1.5,
                    "subcatory": "lunch",
                }
            ],
        }
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__.return_value = mock_client

        command = search_candidates.invoke(
            {
                "category": "restaurant",
                "user_request": "儿童乐园",
                "subcatory": "lunch",
                "tool_call_id": "call_123",
                "state": {
                    "constraints": {
                        "group_type": "family",
                        "budget": 300,
                        "preferred_distance": "2km-5km",
                        "time_period": "12:00",
                        "duration_hours": [4, 6],
                        "child_count": 1,
                        "child_profiles": [["F", 5]],
                    },
                    "candidates": {
                        "ranked_lunch_combos": [
                            {
                                "combo_id": "state_combo",
                                "name": "亲子儿童乐园套餐",
                                "description": "适合带娃午餐",
                                "features": "儿童乐园 宝宝椅",
                                "price": 128,
                                "duration_mins": 90,
                                "suitable_groups": ["family"],
                                "child_facility_tags": ["儿童乐园", "宝宝椅"],
                                "distance_km": 1.5,
                            }
                        ]
                    },
                },
                "top_k": 5,
            },
            config={"configurable": {"thread_id": "thread-1"}},
        )

        mock_client.post.assert_called_once()
        self.assertEqual(mock_httpx_client.call_args.kwargs.get("timeout"), 3.0)
        called_url = mock_client.post.call_args.args[0]
        self.assertEqual(called_url, "http://127.0.0.1:8002/search")
        payload = mock_client.post.call_args.kwargs.get("json", {})
        self.assertEqual(payload.get("session_id"), "thread-1")
        self.assertEqual(payload.get("category"), "restaurant")
        self.assertEqual(payload.get("user_request"), "儿童乐园")
        self.assertEqual(payload.get("subcatory"), "lunch")
        self.assertTrue(payload.get("candidates"))
        self.assertTrue(all(item.get("subcatory") == "lunch" for item in payload.get("candidates", [])))

        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertEqual(content["status"], "success")
        self.assertEqual(content["result"]["results"][0]["id"], "state_combo")
        self.assertEqual(content["result"]["results"][0]["name"], "亲子儿童乐园套餐")
        self.assertEqual(content["result"]["results"][0]["subcatory"], "lunch")
        self.assertTrue(
            any(
                "msg=search_sub_request" in str(call.args[0])
                and "count=1" in str(call.args[0])
                for call in mock_logger.info.call_args_list
            )
        )

    def test_search_candidates_input_rejects_invalid_subcatory_for_category(self):
        with self.assertRaises(Exception):
            SearchCandidatesInput(category="restaurant", user_request="儿童乐园", top_k=5, subcatory="light")

    @patch("httpx.Client")
    @patch("closedloop.graph.tools.search_tool.logger")
    @patch("closedloop.graph.tools.search_tool.get_config")
    @patch("closedloop.graph.tools.search_tool.LoggerManager.setup")
    def test_search_candidates_sends_empty_candidates_when_no_ranked_candidates(
        self,
        _mock_logger_setup,
        mock_get_config,
        mock_logger,
        mock_httpx_client,
    ):
        mock_get_config.return_value = type(
            "FakeConfig",
            (),
            {
                "SEARCH_SUB_API_URL": "http://127.0.0.1:8002/search",
                "TOOL_HTTP_TIMEOUT_SECS": 3.0,
            },
        )()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "status": "success",
            "results": [
                {
                    "package_id": "pkg_1",
                    "name": "亲子绘本活动",
                    "description": "安静互动",
                    "features": "室内 亲子",
                    "price": 99,
                    "duration_mins": 60,
                    "suitable_groups": ["family"],
                    "age_range": ["3-6", "7-10"],
                    "distance_km": 1.0,
                    "subcatory": "normal",
                }
            ],
        }
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__.return_value = mock_client

        command = search_candidates.invoke(
            {
                "category": "activity",
                "user_request": "亲子活动",
                "subcatory": "normal",
                "tool_call_id": "call_234",
                "state": {
                    "constraints": {
                        "group_type": "family",
                        "budget": 300,
                        "preferred_distance": "2km-5km",
                        "time_period": "14:00",
                        "duration_hours": [4, 6],
                        "child_count": 1,
                        "child_profiles": [["F", 5]],
                    },
                    "candidates": {},
                },
                "top_k": 5,
            },
            config={"configurable": {"thread_id": "thread-1"}},
        )

        mock_client.post.assert_called_once()
        self.assertEqual(mock_httpx_client.call_args.kwargs.get("timeout"), 3.0)
        payload = mock_client.post.call_args.kwargs.get("json", {})
        self.assertEqual(payload.get("session_id"), "thread-1")
        self.assertEqual(payload.get("subcatory"), "normal")
        self.assertEqual(payload.get("candidates"), [])

        messages = command.update.get("messages", [])
        content = json.loads(messages[0].content)
        self.assertEqual(content["status"], "success")
        self.assertEqual(content["result"]["results"][0]["id"], "pkg_1")
        self.assertEqual(content["result"]["results"][0]["name"], "亲子绘本活动")
        self.assertEqual(content["result"]["results"][0]["subcatory"], "normal")
        self.assertTrue(
            any(
                "msg=search_sub_request" in str(call.args[0])
                and "count=0" in str(call.args[0])
                for call in mock_logger.info.call_args_list
            )
        )
        self.assertTrue(
            any(
                "msg=candidate_pool_empty" in str(call.args[0])
                for call in mock_logger.warning.call_args_list
            )
        )

    @patch("httpx.Client")
    @patch("closedloop.graph.tools.search_tool.logger")
    @patch("closedloop.graph.tools.search_tool.get_config")
    @patch("closedloop.graph.tools.search_tool.LoggerManager.setup")
    def test_search_candidates_returns_error_when_search_service_returns_empty(
        self,
        _mock_logger_setup,
        mock_get_config,
        mock_logger,
        mock_httpx_client,
    ):
        mock_get_config.return_value = type(
            "FakeConfig",
            (),
            {
                "SEARCH_SUB_API_URL": "http://127.0.0.1:8002/search",
                "TOOL_HTTP_TIMEOUT_SECS": 3.0,
            },
        )()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"status": "success", "results": []}
        mock_client.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__.return_value = mock_client

        command = search_candidates.invoke(
            {
                "category": "restaurant",
                "user_request": "儿童设施",
                "subcatory": "lunch",
                "tool_call_id": "call_345",
                "state": {
                    "constraints": {
                        "group_type": "family",
                        "budget": 300,
                        "dietary_restrictions": ["辣"],
                        "preferred_distance": "<2km",
                        "time_period": "12:00",
                        "duration_hours": [4, 6],
                        "child_count": 1,
                        "child_profiles": [["F", 5]],
                    },
                    "candidates": {
                        "ranked_lunch_combos": [
                            {
                                "combo_id": "combo_ok",
                                "name": "亲子清淡套餐",
                                "description": "清淡口味，适合家庭",
                                "features": "儿童乐园 宝宝椅",
                                "tags": ["清淡"],
                                "price": 128,
                                "duration_mins": 90,
                                "suitable_groups": ["family"],
                                "child_facility_tags": ["儿童乐园", "宝宝椅"],
                                "distance_km": 1.2,
                            },
                        ]
                    },
                },
                "top_k": 5,
            }
        )

        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertEqual(content["error"], "没有找到结果")
        self.assertIn("请尝试换一个搜索词", content["detail"])
        self.assertTrue(
            any(
                "msg=query_no_match" in str(call.args[0])
                for call in mock_logger.info.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
