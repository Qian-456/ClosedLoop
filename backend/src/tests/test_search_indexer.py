import unittest
from unittest.mock import patch, MagicMock
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
