import os
import sys
import time
from typing import Any, Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.search_subgraph.builder import build_subgraph_search
from closedloop.graph.search_subgraph.ranker import _extract_negative_terms, _extract_raw_keywords


config = get_config()
LoggerManager.setup(config)


class SearchRequest(BaseModel):
    session_id: str = "default"
    category: str
    user_request: str
    subcatory: Optional[str] = None
    top_k: int = 5
    candidates: list[dict[str, Any]]


def _truncate_text(text: str, max_len: int = 120) -> str:
    content = (text or "").strip()
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=f"{config.PROJECT_NAME} - Search Subgraph API", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "search_sub_backend"}


@app.post("/search")
def run_search(req: SearchRequest):
    started_at = time.perf_counter()
    keywords_preview = _extract_raw_keywords(req.user_request)[:8]
    negative_terms = _extract_negative_terms(req.user_request)
    logger.info(
        f"phase=search_sub_api | session_id={req.session_id} | category={req.category} | top_k={req.top_k} | subcatory={req.subcatory} | query={_truncate_text(req.user_request)} | keyword_count={len(_extract_raw_keywords(req.user_request))} | negative_term_count={len(negative_terms)} | keywords={keywords_preview}"
    )

    state = {
        "session_id": req.session_id,
        "category": req.category,
        "user_request": req.user_request,
        "subcatory": req.subcatory,
        "top_k": req.top_k,
        "candidates": req.candidates,
    }

    try:
        run_config = {"configurable": {"thread_id": req.session_id}}
        out = build_subgraph_search().invoke(state, config=run_config)
        results = out.get("results", []) if isinstance(out, dict) else []
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"phase=search_sub_api | result=success | session_id={req.session_id} | returned={len(results)} | elapsed_ms={elapsed_ms}"
        )
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"phase=search_sub_api | error={e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("search_sub_main:app", host="0.0.0.0", port=8002, reload=True)
