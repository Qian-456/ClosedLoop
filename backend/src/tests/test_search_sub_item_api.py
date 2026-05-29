import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from search_sub_main import SearchRequest, get_item, run_search


class TestSearchSubItemApi(unittest.TestCase):
    @patch("search_sub_main.logger")
    @patch("search_sub_main.build_subgraph_search")
    def test_get_item_returns_cached_candidate_after_search(
        self,
        mock_build_subgraph_search,
        _mock_logger,
    ):
        candidate = {
            "combo_id": "combo_1",
            "name": "亲子儿童乐园套餐",
            "description": "适合带娃午餐",
            "features": "儿童乐园 宝宝椅",
            "tags": ["儿童乐园", "宝宝椅"],
            "price": 128,
        }

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"results": [candidate]}
        mock_build_subgraph_search.return_value = mock_graph

        run_search(
            SearchRequest(
                session_id="thread-1",
                category="restaurant",
                user_request="儿童乐园",
                top_k=5,
                candidates=[candidate],
            )
        )

        resp = get_item(item_id="combo_1", session_id="thread-1")
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["item"]["combo_id"], "combo_1")
        self.assertEqual(resp["item"]["name"], "亲子儿童乐园套餐")


if __name__ == "__main__":
    unittest.main()

