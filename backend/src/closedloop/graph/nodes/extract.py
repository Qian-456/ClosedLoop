from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.core.llm import build_agent
from closedloop.contracts.state import ClosedLoopState, Constraints
from closedloop.graph.prompts.extract import EXTRACT_CONSTRAINTS_SYSTEM_PROMPT
from langchain.messages import SystemMessage, HumanMessage

def extract_constraints(state: ClosedLoopState) -> ClosedLoopState:
    """
    从用户输入中提取约束条件的节点。
    """
    config = get_config()
    LoggerManager.setup(config)

    logger.info(f"phase=extract_constraints | input={state['user_input']}")

    agent = build_agent(response_format=Constraints)

    try:
        response = agent.invoke({
            "messages": [
                SystemMessage(content=EXTRACT_CONSTRAINTS_SYSTEM_PROMPT), 
                HumanMessage(content=state['user_input'])
            ]
        })
        parsed_output = response
        if isinstance(response, dict) and "structured_response" in response:
            parsed_output = response["structured_response"]
            
        if hasattr(parsed_output, "model_dump"): # 兼容 pydantic v2
            state["constraints"] = parsed_output.model_dump()
        elif hasattr(parsed_output, "dict"): # 兼容 pydantic v1
            state["constraints"] = parsed_output.dict()
        elif isinstance(parsed_output, dict):
            state["constraints"] = parsed_output
        else:
            state["constraints"] = {}
            
        # 过滤未知的饮食禁忌并记录 warning
        if "constraints" in state and "dietary_restrictions" in state["constraints"]:
            allowed_dietary = {"辣", "海鲜", "生冷", "甜", "快餐", "牛"}
            filtered_dietary = []
            for d in state["constraints"]["dietary_restrictions"]:
                if d in allowed_dietary:
                    filtered_dietary.append(d)
                else:
                    logger.warning(f"phase=extract_constraints | warn=unsupported_dietary_restriction | value={d}")
            state["constraints"]["dietary_restrictions"] = filtered_dietary

        logger.info(f"phase=extract_constraints | output={state['constraints']}")
    except Exception as e:
        logger.error(f"phase=extract_constraints | error={e}")
        state["constraints"] = {}
        
    return state
