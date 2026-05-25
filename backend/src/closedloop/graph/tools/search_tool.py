import json
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer

from langchain_core.runnables import RunnableConfig

class SearchCandidatesInput(BaseModel):
    category: Literal["restaurant", "activity", "gift_shop"] = Field(
        ..., description="搜索类别"
    )
    user_request: str = Field(
        ..., description="用户的自然语言搜索词，例如 '找个便宜点的' 或 '有儿童乐园的'"
    )
    top_k: int = Field(default=15, description="最多返回的结果数量")
    offset: int = Field(default=0, description="分页偏移量")

@tool(args_schema=SearchCandidatesInput)
def search_candidates(
    category: Literal["restaurant", "activity", "gift_shop"],
    user_request: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config: RunnableConfig,
    top_k: int = 15,
    offset: int = 0,
) -> Command:
    """
    根据用户的自然语言需求，在指定类别（restaurant, activity, gift_shop）的候选池中进行混合检索（语义 + BM25）。
    """
    config_app = get_config()
    LoggerManager.setup(config_app)
    
    session_id = config.get("configurable", {}).get("thread_id", "default")

    logger.info(f"phase=search_candidates | category={category} | query={user_request} | top_k={top_k} | offset={offset} | session_id={session_id}")

    indexer = SearchIndexer.get_instance()
    results = indexer.search(category=category, query=user_request, top_k=top_k, offset=offset, session_id=session_id)
    
    simplified_results = []
    for item in results:
        item_id = item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id")
        name = item.get("name")
        price = item.get("price")
        duration_mins = item.get("duration_mins") or item.get("receive_duration_mins")
        features = item.get("features")
        description = item.get("description")
        
        # 将影响 Agent 判断的关键字段也吐回去
        child_facilities = item.get("child_facility_tags", [])
        suitable_groups = item.get("suitable_groups", [])
        kid_menu_status = item.get("kid_menu_status")
        stroller_friendly_status = item.get("stroller_friendly_status")
        
        simplified_results.append({
            "id": str(item_id),
            "name": name,
            "price": price,
            "duration_mins": duration_mins,
            "features": features,
            "description": description,
            "child_facilities": child_facilities,
            "suitable_groups": suitable_groups,
            "kid_menu_status": kid_menu_status,
            "stroller_friendly_status": stroller_friendly_status,
        })

    logger.info(f"phase=search_candidates | found={len(simplified_results)}")
    
    result_data = {
        "results": simplified_results,
        "total_returned": len(simplified_results),
        "offset": offset
    }

    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "search_candidates",
            "status": "success",
            "result": result_data,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )

    update = {
        "current_step": "search_candidates",
        "messages": [transfer_message],
    }

    return Command(update=update)
