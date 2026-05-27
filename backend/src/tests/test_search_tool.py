import unittest
import json
import os
import socket
import sys
from unittest.mock import patch, MagicMock

# Add src to path so we can import backend modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.tools.search_tool import search_candidates

class TestSearchTool(unittest.TestCase):
    @patch('closedloop.graph.tools.search_tool.httpx.Client')
    @patch('closedloop.graph.tools.search_tool.get_config')
    @patch('closedloop.graph.tools.search_tool.LoggerManager.setup')
    def test_search_candidates(self, _mock_logger_setup, mock_get_config, mock_client_class):
        fake_config = type("FakeConfig", (), {"PLAN_SUB_API_URL": "http://localhost:8001/plan"})()
        mock_get_config.return_value = fake_config

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "results": [
                {
                    "combo_id": "c1",
                    "name": "Combo 1",
                    "price": 100,
                    "duration_mins": 60,
                    "features": "Feat 1",
                    "description": "Desc 1"
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        command = search_candidates.invoke({
            "category": "restaurant",
            "user_request": "便宜的",
            "tool_call_id": "call_123",
            "state": {},
            "top_k": 5,
        })
        
        self.assertIsNotNone(command)
        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        
        tool_message = messages[0]
        self.assertEqual(tool_message.tool_call_id, "call_123")
        
        content = json.loads(tool_message.content)
        self.assertEqual(content["status"], "success")
        
        results = content["result"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "c1")
        self.assertEqual(results[0]["name"], "Combo 1")
        mock_client.post.assert_called_once_with(
            "http://localhost:8001/search",
            json={
                "category": "restaurant",
                "user_request": "便宜的",
                "top_k": 5,
                "session_id": "default",
            },
        )

    @patch('closedloop.graph.tools.search_tool.httpx.Client')
    @patch('closedloop.graph.tools.search_tool.get_config')
    @patch('closedloop.graph.tools.search_tool.LoggerManager.setup')
    def test_search_candidates_retry_next_candidate_url(self, _mock_logger_setup, mock_get_config, mock_client_class):
        fake_config = type("FakeConfig", (), {"PLAN_SUB_API_URL": "http://plan_sub_backend:8001/plan"})()
        mock_get_config.return_value = fake_config

        mock_client = MagicMock()
        dns_error = socket.gaierror(-2, "Name or service not known")
        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        ok_response.json.return_value = {
            "status": "success",
            "results": [{"id": "a1", "name": "Activity 1", "description": "desc"}],
        }
        mock_client.post.side_effect = [dns_error, ok_response]
        mock_client.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        command = search_candidates.invoke({
            "category": "activity",
            "user_request": "儿童",
            "tool_call_id": "call_234",
            "state": {},
            "top_k": 5,
        })

        messages = command.update.get("messages", [])
        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0].content)
        self.assertEqual(content["status"], "success")
        self.assertEqual(content["result"]["results"][0]["id"], "a1")

        called_urls = [call.args[0] for call in mock_client.post.call_args_list]
        self.assertEqual(
            called_urls,
            [
                "http://plan_sub_backend:8001/search",
                "http://localhost:8001/search",
            ],
        )

    @patch('closedloop.graph.tools.search_tool.httpx.Client')
    @patch('closedloop.graph.tools.search_tool.get_config')
    @patch('closedloop.graph.plan_subgraph.search_indexer.SearchIndexer.get_instance')
    @patch('closedloop.graph.tools.search_tool.LoggerManager.setup')
    def test_search_candidates_fallback_after_all_candidates_fail(self, _mock_logger_setup, mock_get_indexer, mock_get_config, mock_client_class):
        fake_config = type("FakeConfig", (), {"PLAN_SUB_API_URL": "http://plan_sub_backend:8001/plan"})()
        mock_get_config.return_value = fake_config

        mock_client = MagicMock()
        mock_client.post.side_effect = socket.gaierror(-2, "Name or service not known")
        mock_client.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.category_docs = {
            "default": {
                "restaurant": [
                    {"id": "r1", "name": "亲子餐厅", "description": "有儿童设施", "features": "儿童区"},
                ]
            }
        }
        mock_indexer_instance._prepare_text.return_value = "亲子餐厅 有儿童设施 儿童区"
        mock_get_indexer.return_value = mock_indexer_instance

        command = search_candidates.invoke({
            "category": "restaurant",
            "user_request": "儿童",
            "tool_call_id": "call_345",
            "state": {},
            "top_k": 5,
        })

        messages = command.update.get("messages", [])
        content = json.loads(messages[0].content)
        self.assertEqual(content["status"], "success")
        self.assertEqual(content["result"]["results"][0]["id"], "r1")
        self.assertGreaterEqual(mock_client.post.call_count, 1)
        mock_get_indexer.assert_called_once()

if __name__ == '__main__':
    unittest.main()
