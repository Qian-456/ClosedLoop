import unittest
import concurrent.futures
import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path so we can import backend modules.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer, MilvusHybridSearcher

class TestSearchIndexer(unittest.TestCase):
    @patch('closedloop.graph.plan_subgraph.search_indexer.MilvusClient')
    @patch('closedloop.graph.plan_subgraph.search_indexer.DashScopeEmbedding')
    def test_build_index_and_search(self, mock_dashscope, mock_milvus_client):
        # Setup mocks
        mock_embed_instance = MagicMock()
        mock_embed_instance.get_text_embedding.return_value = [0.1] * 1536
        mock_embed_instance.get_text_embedding_batch.return_value = [[0.1] * 1536, [0.1] * 1536]
        mock_dashscope.return_value = mock_embed_instance
        
        mock_client_instance = MagicMock()
        mock_client_instance.has_collection.return_value = False
        mock_milvus_client.return_value = mock_client_instance
        
        # We need to mock the MilvusClient.create_schema to return a schema
        mock_schema = MagicMock()
        mock_milvus_client.create_schema.return_value = mock_schema

        indexer = SearchIndexer()
        
        # Test build index
        items = [
            {"id": "1", "name": "Item 1", "description": "Desc 1", "features": "Feat 1"},
            {"id": "2", "name": "Item 2", "description": "Desc 2", "features": "Feat 2"}
        ]
        
        # Building index
        indexer.build_index("restaurant", items)
        
        # Assertions
        mock_milvus_client.assert_called()
        mock_client_instance.create_collection.assert_called_once()
        self.assertEqual(len(indexer.category_docs["default"]["restaurant"]), 2)
        
        # Mock search hybrid search
        mock_hybrid_searcher = MagicMock()
        mock_hit_1 = MagicMock()
        mock_hit_1.id = "1"
        mock_hit_2 = MagicMock()
        mock_hit_2.id = "2"
        mock_hybrid_searcher.search.return_value = [mock_hit_2, mock_hit_1]

        # Change has_collection to True for search phase
        mock_client_instance.has_collection.return_value = True

        with patch('closedloop.graph.plan_subgraph.search_indexer.MilvusHybridSearcher', return_value=mock_hybrid_searcher):
            results = indexer.search("restaurant", "query", top_k=2)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["id"], "2")
            self.assertEqual(results[1]["id"], "1")

    @patch('closedloop.graph.plan_subgraph.search_indexer.MilvusClient')
    @patch('closedloop.graph.plan_subgraph.search_indexer.DashScopeEmbedding')
    def test_build_index_preserves_items_when_embedding_timeout(self, mock_dashscope, mock_milvus_client):
        mock_embed_instance = MagicMock()
        mock_embed_instance.get_text_embedding.side_effect = concurrent.futures.TimeoutError()
        mock_dashscope.return_value = mock_embed_instance

        mock_client_instance = MagicMock()
        mock_client_instance.has_collection.return_value = False
        mock_milvus_client.return_value = mock_client_instance
        mock_schema = MagicMock()
        mock_milvus_client.create_schema.return_value = mock_schema

        indexer = SearchIndexer()
        items = [
            {"id": "1", "name": "Item 1", "description": "Desc 1", "features": "Feat 1"},
            {"id": "2", "name": "Item 2", "description": "Desc 2", "features": "Feat 2"},
        ]

        indexer.build_index("restaurant", items)

        mock_client_instance.insert.assert_called_once()
        inserted_payload = mock_client_instance.insert.call_args.kwargs["data"]
        self.assertEqual(len(inserted_payload), 2)
        self.assertEqual(inserted_payload[0]["id"], "1")
        self.assertEqual(inserted_payload[1]["id"], "2")
        self.assertNotEqual(inserted_payload[0]["dense_vector"], [0.0] * indexer.dim)

    @patch('closedloop.graph.plan_subgraph.search_indexer.MilvusClient')
    @patch('closedloop.graph.plan_subgraph.search_indexer.DashScopeEmbedding')
    def test_build_index_degrades_to_cache_when_flush_collection_disappears(self, mock_dashscope, mock_milvus_client):
        mock_embed_instance = MagicMock()
        mock_embed_instance.get_text_embedding.return_value = [0.1] * 1536
        mock_dashscope.return_value = mock_embed_instance

        mock_client_instance = MagicMock()
        mock_client_instance.has_collection.side_effect = (
            lambda name: str(name).startswith("closedloop_restaurant_")
        )
        mock_client_instance.flush.side_effect = Exception(
            "collection not found[collection=466585545529300046]"
        )
        mock_milvus_client.return_value = mock_client_instance
        mock_schema = MagicMock()
        mock_milvus_client.create_schema.return_value = mock_schema

        indexer = SearchIndexer()
        items = [
            {"id": "1", "name": "Item 1", "description": "Desc 1", "features": "Feat 1"},
        ]

        with patch('closedloop.graph.plan_subgraph.search_indexer.logger') as mock_logger:
            indexer.build_index("restaurant", items, session_id="Jason-session012/fde3")

        self.assertEqual(indexer.category_docs["Jason-session012/fde3"]["restaurant"], items)
        self.assertEqual(mock_client_instance.flush.call_count, 3)
        mock_client_instance.create_index.assert_not_called()
        mock_client_instance.load_collection.assert_not_called()

        error_messages = [
            str(call.args[0])
            for call in mock_logger.error.call_args_list
            if call.args
        ]
        self.assertFalse(any("milvus_build_failed" in msg for msg in error_messages))
        warning_messages = [
            str(call.args[0])
            for call in mock_logger.warning.call_args_list
            if call.args
        ]
        self.assertTrue(
            any("session_index_build_degraded_cache_only" in msg for msg in warning_messages)
        )

    @patch('closedloop.graph.plan_subgraph.search_indexer.MilvusClient')
    @patch('closedloop.graph.plan_subgraph.search_indexer.MilvusHybridSearcher')
    @patch('closedloop.graph.plan_subgraph.search_indexer.DashScopeEmbedding')
    def test_search_fallback(self, mock_dashscope, mock_hybrid_searcher_class, mock_milvus_client):
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client_instance.has_collection.return_value = True
        mock_milvus_client.return_value = mock_client_instance

        indexer = SearchIndexer()
        indexer.category_docs = {"default": {"activity": [
            {"id": "a1", "name": "Activity 1"},
            {"id": "a2", "name": "Activity 2"},
            {"id": "a3", "name": "Activity 3"}
        ]}}
        
        # Simulate exception during search to trigger fallback
        mock_hybrid_searcher_instance = MagicMock()
        mock_hybrid_searcher_instance.search.side_effect = Exception("Milvus down")
        mock_hybrid_searcher_class.return_value = mock_hybrid_searcher_instance
        
        results = indexer.search("activity", "query", top_k=2)
        
        # Should fallback to default slicing
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "a1")
        self.assertEqual(results[1]["id"], "a2")

if __name__ == '__main__':
    unittest.main()
