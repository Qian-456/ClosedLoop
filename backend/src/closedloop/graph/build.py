from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.extract import extract_constraints

def build_graph():
    """
    构建 LangGraph 工作流。
    当前仅包含单个节点：extract_constraints。
    """
    # 1. 使用我们的 TypedDict 初始化 StateGraph
    workflow = StateGraph(ClosedLoopState)

    # 2. 添加节点
    workflow.add_node("extract_constraints", extract_constraints)

    # 3. 定义边
    workflow.add_edge(START, "extract_constraints")
    workflow.add_edge("extract_constraints", END)

    # 4. 编译图
    app = workflow.compile()

    return app
