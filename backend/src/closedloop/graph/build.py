from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.extract import extract_constraints
from closedloop.graph.nodes.retrieve import retrieve_candidates

def build_graph():
    """
    构建 LangGraph 工作流。
    当前包含节点：extract_constraints -> retrieve_candidates
    """
    # 1. 使用我们的 TypedDict 初始化 StateGraph
    workflow = StateGraph(ClosedLoopState)

    # 2. 添加节点
    workflow.add_node("extract_constraints", extract_constraints)
    workflow.add_node("retrieve_candidates", retrieve_candidates)

    # 3. 定义边
    workflow.add_edge(START, "extract_constraints")
    workflow.add_edge("extract_constraints", "retrieve_candidates")
    workflow.add_edge("retrieve_candidates", END)

    # 4. 编译图
    app = workflow.compile()

    return app
