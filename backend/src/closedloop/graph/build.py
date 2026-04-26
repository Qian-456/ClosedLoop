from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.extract import extract_constraints

def build_graph():
    """
    Build the LangGraph workflow.
    Currently only contains a single node: extract_constraints.
    """
    # 1. Initialize StateGraph with our TypedDict
    workflow = StateGraph(ClosedLoopState)

    # 2. Add nodes
    workflow.add_node("extract_constraints", extract_constraints)

    # 3. Define edges
    workflow.add_edge(START, "extract_constraints")
    workflow.add_edge("extract_constraints", END)

    # 4. Compile the graph
    app = workflow.compile()

    return app
