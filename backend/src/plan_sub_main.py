import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import time

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.plan_subgraph.builder import build_subgraph_plan
from closedloop.graph.plan_subgraph.search_indexer import SearchIndexer
from closedloop.contracts.state import PlanState

# 初始化配置与日志
config = get_config()
LoggerManager.setup(config)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 构建全局向量缓存
    indexer = SearchIndexer.get_instance()
    indexer.build_global_vectors(force_rebuild=getattr(config, "FORCE_REBUILD_VECTORS", False))
    yield

app = FastAPI(title=f"{config.PROJECT_NAME} - Plan Subgraph API", lifespan=lifespan)


def _count_plan_candidates(candidates: Dict[str, Any] | None) -> Dict[str, int]:
    """Summarize ranked candidate counts for plan observability."""
    candidate_state = candidates or {}
    return {
        "restaurant_count": sum(
            len(candidate_state.get(key, []) or [])
            for key in (
                "ranked_breakfast_combos",
                "ranked_lunch_combos",
                "ranked_afternoon_tea_combos",
                "ranked_dinner_combos",
                "ranked_late_night_combos",
            )
        ),
        "activity_count": sum(
            len(candidate_state.get(key, []) or [])
            for key in ("ranked_light_packages", "ranked_packages")
        ),
        "gift_count": len(candidate_state.get("ranked_gifts", []) or []),
    }

class PlanRequest(BaseModel):
    user_input: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    candidates: Optional[Dict[str, Any]] = None
    itinerary: Optional[Dict[str, Any]] = None
    past_itinerary: Optional[List[Dict[str, Any]]] = None
    top_k: Optional[int] = 1
    session_id: str = "default"

class SearchRequest(BaseModel):
    category: str
    user_request: str
    top_k: int = 5
    session_id: str = "default"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "plan_sub_backend"}

@app.post("/plan")
def run_plan_subgraph(req: PlanRequest):
    started_at = time.perf_counter()
    logger.info(f"phase=plan_sub_api | input_top_k={req.top_k} | session_id={req.session_id}")
    
    subgraph_state: PlanState = {}
    if req.user_input is not None:
        subgraph_state["user_input"] = req.user_input
    if req.constraints is not None:
        subgraph_state["constraints"] = req.constraints
    if req.candidates is not None:
        subgraph_state["candidates"] = req.candidates
    if req.itinerary is not None:
        subgraph_state["itinerary"] = req.itinerary
    if req.past_itinerary is not None:
        subgraph_state["past_itinerary"] = req.past_itinerary
    if req.top_k is not None:
        subgraph_state["top_k"] = req.top_k

    try:
        run_config = {"configurable": {"thread_id": req.session_id}}
        subgraph_output = build_subgraph_plan().invoke(subgraph_state, config=run_config)
        result = subgraph_output.get("itinerary", {}) if isinstance(subgraph_output, dict) else {}
        candidates: Dict[str, Any] = {}
        if isinstance(subgraph_output, dict):
            candidates = subgraph_output.get("candidates", {}) or {}
            candidate_counts = _count_plan_candidates(candidates)
            logger.info(
                f"phase=plan_sub_api | msg=plan_candidates_ready | session_id={req.session_id} "
                f"| restaurant_count={candidate_counts['restaurant_count']} "
                f"| activity_count={candidate_counts['activity_count']} "
                f"| gift_count={candidate_counts['gift_count']}"
            )
            try:
                SearchIndexer.get_instance().schedule_plan_indices(candidates, session_id=req.session_id)
            except Exception as e:
                logger.error(
                    f"phase=plan_sub_api | msg=schedule_plan_indices_failed | session_id={req.session_id} | error={e}"
                )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"phase=plan_sub_api | result=success | session_id={req.session_id} | elapsed_ms={elapsed_ms}"
        )
        return {"status": "success", "itinerary": result, "candidates": candidates}
    except Exception as e:
        logger.error(f"phase=plan_sub_api | error={e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
def run_search(req: SearchRequest):
    logger.info(
        f"phase=search_api | category={req.category} | query={req.user_request} | top_k={req.top_k} | session_id={req.session_id}"
    )
    try:
        indexer = SearchIndexer.get_instance()
        results = indexer.search(
            category=req.category,
            query=req.user_request,
            top_k=req.top_k,
            session_id=req.session_id
        )
        logger.info(
            f"phase=search_api | result=success | category={req.category} | count={len(results)} | session_id={req.session_id}"
        )
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"phase=search_api | error={e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/item/{item_id}")
def get_item(item_id: str, session_id: str = "default"):
    logger.info(f"phase=get_item_api | item_id={item_id} | session_id={session_id}")
    try:
        indexer = SearchIndexer.get_instance()
        item = indexer.get_item(item_id, session_id=session_id)
        if item:
            logger.info(f"phase=get_item_api | result=success | item_id={item_id} | session_id={session_id}")
            return {"status": "success", "item": item}
        else:
            logger.warning(f"phase=get_item_api | result=not_found | item_id={item_id} | session_id={session_id}")
            return {"status": "not_found", "item": {}}
    except Exception as e:
        logger.error(f"phase=get_item_api | error={e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("plan_sub_main:app", host="0.0.0.0", port=8001, reload=True)
