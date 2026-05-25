import json
import os
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager
from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer

def test_search():
    config = get_config()
    LoggerManager.setup(config)
    
    # 加载测试数据
    with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    indexer = SearchIndexer.get_instance()
    
    # 构建测试索引
    session_id = "test_search_algo"
    print("Building index...")
    indexer.build_index("restaurant", data, session_id=session_id)
    
    # 模拟搜索
    query = "有儿童设施"
    print(f"\nSearching for: {query}")
    results = indexer.search("restaurant", query, top_k=5, session_id=session_id)
    
    print("\nSearch Results:")
    for i, r in enumerate(results):
        tags = r.get('child_facility_tags', [])
        name = r.get('name', 'Unknown')
        print(f"{i+1}. {name} | 儿童设施: {tags}")

if __name__ == '__main__':
    test_search()