import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager
from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer

config = get_config()
LoggerManager.setup(config)

indexer = SearchIndexer.get_instance()
print("Building global vectors...")
indexer.build_global_vectors(force_rebuild=True)
print("Done.")
