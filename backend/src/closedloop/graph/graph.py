from __future__ import annotations

import json
from typing import Any

from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.nodes.retrieve import retrieve_candidates_node, filter_node
from closedloop.graph.nodes.rerank import rerank_node
from closedloop.graph.nodes.planner import planner_node
from closedloop.graph.nodes.copywriting import copywriting_node


def plan_agent_node(state: ClosedLoopState) -> ClosedLoopState:
    config = get_config()
    LoggerManager.setup(config)

    raw_constraints: Any = state.get("constraints")
    if raw_constraints is None:
        raw_constraints = state.get("input")
    if raw_constraints is None:
        raw_constraints = {}

    constraints_dict: dict[str, Any] = {}
    try:
        if isinstance(raw_constraints, Constraints):
            obj = raw_constraints
        elif isinstance(raw_constraints, dict):
            obj = Constraints(**raw_constraints)
        elif hasattr(Constraints, "model_validate"):
            obj = Constraints.model_validate(raw_constraints)
        else:
            obj = Constraints.parse_obj(raw_constraints)

        if hasattr(obj, "model_dump"):
            constraints_dict = obj.model_dump()
        else:
            constraints_dict = obj.dict()
    except Exception as e:
        logger.error(f"phase=plan_agent_node | error=constraints_validation_failed | error={e}")
        constraints_dict = {}

    state["constraints"] = constraints_dict

    user_input = state.get("user_input")
    if not isinstance(user_input, str) or not user_input.strip():
        if constraints_dict:
            state["user_input"] = json.dumps(constraints_dict, ensure_ascii=False)
        else:
            state["user_input"] = ""

    processed_steps = state.setdefault("processed_steps", [])
    if isinstance(processed_steps, list):
        processed_steps.append("plan_agent_node")

    logger.info("phase=plan_agent_node | status=ok")
    return state


def subgraph_plan():
    workflow = StateGraph(ClosedLoopState)

    workflow.add_node("plan_agent_node", plan_agent_node)
    workflow.add_node("retrieve_candidates_node", retrieve_candidates_node)
    workflow.add_node("filter_node", filter_node)
    workflow.add_node("rerank_node", rerank_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("copywriting_node", copywriting_node)

    workflow.add_edge(START, "plan_agent_node")
    workflow.add_edge("plan_agent_node", "retrieve_candidates_node")
    workflow.add_edge("retrieve_candidates_node", "filter_node")
    workflow.add_edge("filter_node", "rerank_node")
    workflow.add_edge("rerank_node", "planner_node")
    workflow.add_edge("planner_node", "copywriting_node")
    workflow.add_edge("copywriting_node", END)

    return workflow.compile()
