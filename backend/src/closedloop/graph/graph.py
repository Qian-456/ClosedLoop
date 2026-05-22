from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END

from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.core.config import get_config
from closedloop.core.llm import build_agent
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.nodes.retrieve import retrieve_candidates_node, filter_node
from closedloop.graph.nodes.rerank import rerank_node
from closedloop.graph.nodes.planner import planner_node
from closedloop.graph.nodes.copywriting import copywriting_node
from closedloop.graph.prompts.extract import EXTRACT_CONSTRAINTS_SYSTEM_PROMPT
from closedloop.graph.prompts.plan_agent import PLAN_AGENT_SYSTEM_PROMPT


class _ExtractConstraintsToolInput(BaseModel):
    user_input: str = Field(...)


@tool("extract_constraints", args_schema=_ExtractConstraintsToolInput)
def _extract_constraints_tool(user_input: str) -> dict[str, Any]:
    agent = build_agent(response_format=Constraints)
    response = agent.invoke(
        {
            "messages": [
                SystemMessage(content=EXTRACT_CONSTRAINTS_SYSTEM_PROMPT),
                HumanMessage(content=user_input),
            ]
        }
    )
    parsed: Any = response
    if isinstance(response, dict) and "structured_response" in response:
        parsed = response["structured_response"]
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    if hasattr(parsed, "dict"):
        return parsed.dict()
    if isinstance(parsed, dict):
        return parsed
    return {}


def _coerce_constraints_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Constraints):
        obj = raw
    elif isinstance(raw, dict):
        obj = Constraints(**raw)
    elif hasattr(Constraints, "model_validate"):
        obj = Constraints.model_validate(raw)
    else:
        obj = Constraints.parse_obj(raw)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj.dict()


def _extract_tool_result(response: Any) -> Any:
    if isinstance(response, dict):
        steps = response.get("intermediate_steps")
        if isinstance(steps, list) and steps:
            for step in reversed(steps):
                if isinstance(step, (list, tuple)) and len(step) == 2:
                    obs = step[1]
                    if isinstance(obs, dict):
                        return obs
                    if isinstance(obs, str):
                        try:
                            return json.loads(obs)
                        except Exception:
                            pass
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            for m in reversed(messages):
                if isinstance(m, ToolMessage):
                    content = m.content
                    if isinstance(content, dict):
                        return content
                    if isinstance(content, str):
                        try:
                            return json.loads(content)
                        except Exception:
                            return content
        for k in ("output", "result", "final"):
            v = response.get(k)
            if v is not None:
                return v
    return None


def plan_agent_node(state: ClosedLoopState) -> ClosedLoopState:
    config = get_config()
    LoggerManager.setup(config)

    raw_user_input = state.get("user_input")
    if not isinstance(raw_user_input, str):
        raw_user_input = "" if raw_user_input is None else str(raw_user_input)
    raw_user_input = raw_user_input.strip()

    raw_constraints: Any = state.get("constraints")
    constraints_dict: dict[str, Any] = {}

    if raw_constraints:
        try:
            constraints_dict = _coerce_constraints_dict(raw_constraints)
        except Exception as e:
            logger.error(f"phase=plan_agent_node | error=constraints_validation_failed | error={e}")
            constraints_dict = {}

    if not constraints_dict:
        agent = build_agent(tools=[_extract_constraints_tool], temperature=0.2)
        response = agent.invoke(
            {
                "messages": [
                    SystemMessage(content=PLAN_AGENT_SYSTEM_PROMPT),
                    HumanMessage(content=raw_user_input),
                ]
            }
        )
        tool_result = _extract_tool_result(response)
        try:
            constraints_dict = _coerce_constraints_dict(tool_result)
        except Exception as e:
            logger.error(f"phase=plan_agent_node | error=tool_constraints_invalid | error={e}")
            constraints_dict = {}

        if not constraints_dict:
            try:
                constraints_dict = _extract_constraints_tool(user_input=raw_user_input)
                constraints_dict = _coerce_constraints_dict(constraints_dict)
            except Exception as e:
                logger.error(f"phase=plan_agent_node | error=extract_constraints_fallback_failed | error={e}")
                constraints_dict = {}

    state["constraints"] = constraints_dict
    state["user_input"] = raw_user_input

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
