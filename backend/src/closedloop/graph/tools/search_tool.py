import json
import httpx
import socket
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger

from langchain_core.runnables import RunnableConfig

class SearchCandidatesInput(BaseModel):
    category: Literal["restaurant", "activity", "gift_shop"] = Field(
        ..., description="搜索类别"
    )
    user_request: str = Field(
        ..., description="用户的自然语言搜索词，例如 '找个便宜点的' 或 '有儿童乐园的'"
    )
    top_k: int = Field(default=5, description="最多返回的结果数量")


def _normalize_search_url(base_url: str) -> str:
    """Normalize a plan endpoint into the paired search endpoint."""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return ""
    if normalized.endswith("/plan"):
        return f"{normalized[:-5]}/search"
    if normalized.endswith("/search"):
        return normalized
    return f"{normalized}/search"


def _candidate_search_urls(configured_url: str) -> list[str]:
    """Build ordered candidate search URLs for host and Docker environments."""
    candidates: list[str] = []
    seen: set[str] = set()

    raw_candidates = [
        configured_url,
        "http://plan_sub_backend:8001/plan",
        "http://localhost:8001/plan",
        "http://127.0.0.1:8001/plan",
    ]

    for raw_url in raw_candidates:
        search_url = _normalize_search_url(raw_url)
        if search_url and search_url not in seen:
            seen.add(search_url)
            candidates.append(search_url)

    return candidates


def _keyword_fallback_search(category: str, user_request: str, session_id: str, top_k: int) -> list[dict]:
    """Run an in-memory keyword fallback search on cached session docs."""
    from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer

    indexer = SearchIndexer.get_instance()
    session_docs = indexer.category_docs.get(session_id, {})
    all_items = session_docs.get(category, [])

    if not all_items:
        logger.warning(
            f"phase=search_candidates | msg=fallback_cache_empty | category={category} | session_id={session_id}"
        )
        return []

    import jieba

    split_words = [w.strip() for w in user_request.split() if w.strip()]
    keywords = split_words

    if len(split_words) <= 1:
        raw_keywords = jieba.lcut_for_search(user_request)
        keywords = [k for k in raw_keywords if k.strip()]

    if not keywords:
        keywords = [user_request]

    scored_items = []
    for item in all_items:
        text = indexer._prepare_text(item)
        score = sum(1 for keyword in keywords if keyword in text)
        if score > 0:
            scored_items.append((score, item))

    scored_items.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored_items][:top_k]

@tool(args_schema=SearchCandidatesInput)
def search_candidates(
    category: Literal["restaurant", "activity", "gift_shop"],
    user_request: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
    config: RunnableConfig,
    top_k: int = 5,
) -> Command:
    """
    根据用户的自然语言需求，在指定类别（restaurant, activity, gift_shop）的候选池中进行混合检索（语义 + BM25）。
    """
    config_app = get_config()
    LoggerManager.setup(config_app)
    
    session_id = config.get("configurable", {}).get("thread_id", "default")

    logger.info(f"phase=search_candidates | category={category} | query={user_request} | top_k={top_k} | session_id={session_id}")

    payload = {
        "category": category,
        "user_request": user_request,
        "top_k": top_k,
        "session_id": session_id
    }
    
    results = []
    search_urls = _candidate_search_urls(
        getattr(config_app, "PLAN_SUB_API_URL", "http://localhost:8001/plan")
    )
    last_error = None

    try:
        with httpx.Client(timeout=2.8, trust_env=False, proxy=None) as client:
            for search_url in search_urls:
                try:
                    logger.info(
                        f"phase=search_candidates | msg=search_api_attempt | url={search_url} | session_id={session_id}"
                    )
                    resp = client.post(search_url, json=payload)
                    resp.raise_for_status()
                    search_output = resp.json()
                    results = search_output.get("results", [])
                    logger.info(
                        f"phase=search_candidates | msg=search_api_success | url={search_url} | count={len(results)}"
                    )
                    break
                except socket.gaierror as e:
                    last_error = e
                    logger.warning(
                        f"phase=search_candidates | msg=search_api_dns_failed | url={search_url} | error={e}"
                    )
                except httpx.ConnectError as e:
                    last_error = e
                    logger.warning(
                        f"phase=search_candidates | msg=search_api_connect_failed | url={search_url} | error={e}"
                    )
                except httpx.HTTPError as e:
                    last_error = e
                    logger.warning(
                        f"phase=search_candidates | msg=search_api_http_failed | url={search_url} | error={e}"
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"phase=search_candidates | msg=search_api_failed | url={search_url} | error={e}"
                    )

        if not results:
            raise RuntimeError(last_error or "all_search_api_candidates_failed")
    except Exception as e:
        logger.error(f"phase=search_candidates | msg=fallback_to_keyword_search | error={e}")
        try:
            results = _keyword_fallback_search(category, user_request, session_id, top_k)
        except Exception as fallback_e:
            logger.error(f"phase=search_candidates | msg=fallback_search_failed | error={fallback_e}")
            results = []

        logger.error(f"phase=search_candidates | error={e}")
        # 如果兜底也空了（比如 all_items 原本就为空，或者匹配不到结果），或者兜底代码出错，返回一个提示给 Agent
        if not results:
            fail_msg = ToolMessage(
                content=json.dumps({"error": "没有找到结果", "detail": "查询失败、超时或当前候选池为空，请尝试换一个搜索词或者不使用额外条件重新规划。"}, ensure_ascii=False),
                tool_call_id=tool_call_id
            )
            return Command(
                update={
                    "candidates": state.get("candidates", {}),
                    "messages": [fail_msg]
                }
            )
    
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
        "total_returned": len(simplified_results)
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
