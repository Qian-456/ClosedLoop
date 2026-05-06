from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.extract import extract_constraints
from closedloop.graph.nodes.retrieve import retrieve_candidates_node, filter_node
from closedloop.graph.nodes.rerank import rerank_node
from closedloop.graph.nodes.planner import planner_node

def build_graph():
    """
    构建 LangGraph 工作流。
    当前包含节点：extract_constraints -> retrieve_candidates_node -> filter_node -> rerank_node -> planner_node
    """
    # 1. 使用我们的 TypedDict 初始化 StateGraph
    workflow = StateGraph(ClosedLoopState)

    # 2. 添加节点
    workflow.add_node("extract_constraints", extract_constraints)
    workflow.add_node("retrieve_candidates_node", retrieve_candidates_node)
    workflow.add_node("filter_node", filter_node)
    workflow.add_node("rerank_node", rerank_node)
    workflow.add_node("planner_node", planner_node)

    # 3. 定义边
    workflow.add_edge(START, "extract_constraints")
    workflow.add_edge("extract_constraints", "retrieve_candidates_node")
    workflow.add_edge("retrieve_candidates_node", "filter_node")
    workflow.add_edge("filter_node", "rerank_node")
    workflow.add_edge("rerank_node", "planner_node")
    workflow.add_edge("planner_node", END)

    # 4. 编译图
    app = workflow.compile()

    return app
