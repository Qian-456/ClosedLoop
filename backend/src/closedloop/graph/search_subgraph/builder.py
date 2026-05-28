from langgraph.graph import END, START, StateGraph

from closedloop.graph.search_subgraph.contracts import SearchSubgraphOutput, SearchSubgraphState
from closedloop.graph.search_subgraph.ranker import ranked_only_search_node


def build_subgraph_search():
    """构建站内搜索子图（ranked-only 规则引擎版本）。"""
    workflow = StateGraph(SearchSubgraphState, output_schema=SearchSubgraphOutput)

    workflow.add_node("ranked_only_search_node", ranked_only_search_node)
    workflow.add_edge(START, "ranked_only_search_node")
    workflow.add_edge("ranked_only_search_node", END)

    return workflow.compile()


def build_search_subgraph():
    """构建站内搜索子图（兼容旧调用名称）。"""
    return build_subgraph_search()
