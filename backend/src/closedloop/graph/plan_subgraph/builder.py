from langgraph.graph import END, START, StateGraph
from typing_extensions import NotRequired, TypedDict

from closedloop.contracts.state import PlanState
from closedloop.graph.plan_subgraph.planner import planner_node
from closedloop.graph.plan_subgraph.rerank import rerank_node
from closedloop.graph.plan_subgraph.retrieve import filter_node, retrieve_candidates_node


class PlanSubgraphOutput(TypedDict):
    """规划子图对外只返回 itinerary。"""

    itinerary: NotRequired[dict]


def build_subgraph_plan():
    """
    构建结构化规划子图。

    子图入口要求 state 已经包含 constraints，因此这里不再接入
    extract_constraints 节点；当前也暂不接入文案节点。
    """
    workflow = StateGraph(PlanState, output_schema=PlanSubgraphOutput)

    workflow.add_node("retrieve_candidates_node", retrieve_candidates_node)
    workflow.add_node("filter_node", filter_node)
    workflow.add_node("rerank_node", rerank_node)
    workflow.add_node("planner_node", planner_node)

    workflow.add_edge(START, "retrieve_candidates_node")
    workflow.add_edge("retrieve_candidates_node", "filter_node")
    workflow.add_edge("filter_node", "rerank_node")
    workflow.add_edge("rerank_node", "planner_node")
    workflow.add_edge("planner_node", END)

    return workflow.compile()
