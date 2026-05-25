import unittest
import json
from unittest.mock import patch, MagicMock
from closedloop.graph.tools.search_tool import search_candidates

class TestSearchTool(unittest.TestCase):
    @patch('closedloop.graph.tools.search_tool.SearchIndexer')
    def test_search_candidates(self, mock_search_indexer):
        mock_indexer_instance = MagicMock()
        mock_indexer_instance.search.return_value = [
            {
                "combo_id": "c1",
                "name": "Combo 1",
                "price": 100,
                "duration_mins": 60,
                "features": "Feat 1",
                "description": "Desc 1"
            }
        ]
        mock_search_indexer.get_instance.return_value = mock_indexer_instance

        # Invoke the tool
        command = search_candidates.invoke({
            "category": "restaurant",
            "user_request": "便宜的",
            "tool_call_id": "call_123",
            "state": {},
            "top_k": 5,
            "offset": 0
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

if __name__ == '__main__':
    unittest.main()
