from langgraph.graph import END, START, StateGraph

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.plan_agent import plan_agent_node


def build_graph():
    """
    构建顶层 Agent Graph。

    顶层图只负责编排 planner agent，由 agent 通过工具调用进入规划子图。
    """
    workflow = StateGraph(ClosedLoopState)

    workflow.add_node("plan_agent_node", plan_agent_node)

    workflow.add_edge(START, "plan_agent_node")
    workflow.add_edge("plan_agent_node", END)

    return workflow.compile()
