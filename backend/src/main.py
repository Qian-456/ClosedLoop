import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.execution import ExecuteRequest, ExecutionStartResponse
from closedloop.execution.mock_executor import iter_events, start_execution
from closedloop.graph.agent import build_agent_with_async_checkpointer
from closedloop.contracts.state import ClosedLoopState
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 初始化配置与日志
config = get_config()
LoggerManager.setup(config)

app = FastAPI(title=config.PROJECT_NAME)

class ChatRequest(BaseModel):
    user_input: str
    thread_id: str = "default_session"

class ChatResponse(BaseModel):
    status: str
    state: dict


def _get_sessions_db_path() -> str:
    """Build the absolute sqlite path for graph sessions."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../mock_data/runtime/sessions.sqlite")
    )


def _serialize_message(message: Any) -> dict[str, Any]:
    """Serialize a LangGraph message into a frontend-friendly dict."""
    msg_type = getattr(message, "type", "unknown")
    content = getattr(message, "content", "")

    if not content and hasattr(message, "tool_calls") and message.tool_calls:
        tool_names = ", ".join([tool_call.get("name", "tool") for tool_call in message.tool_calls])
        content = f"*[正在调用工具: {tool_names}...]*"

    return {
        "id": getattr(message, "id", None),
        "type": msg_type,
        "content": content,
    }


def serialize_graph_state(state: ClosedLoopState | dict[str, Any]) -> dict[str, Any]:
    """Serialize graph state so the frontend can consume it directly."""
    serializable_state = dict(state)
    if "messages" in serializable_state:
        serializable_state["messages"] = [
            _serialize_message(message) for message in serializable_state["messages"]
        ]
    return serializable_state


def format_sse_event(event_name: str, data: dict[str, Any]) -> str:
    """Format one SSE event block."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


async def _build_workflow_app():
    """Create the workflow app with sqlite checkpoint support."""
    db_path = _get_sessions_db_path()
    checkpointer = AsyncSqliteSaver.from_conn_string(db_path)
    return checkpointer, build_agent_with_async_checkpointer


async def _stream_invoke_events(request: ChatRequest) -> AsyncIterator[str]:
    """Yield serialized SSE blocks for the invoke stream endpoint."""
    logger.info(f"phase=api_invoke_stream | input={request.user_input} | thread_id={request.thread_id}")
    config_run = {"configurable": {"thread_id": request.thread_id}}

    try:
        db_path = _get_sessions_db_path()
        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)
            final_state = None

            async for event in workflow_app.astream(
                {"messages": [("user", request.user_input)]},
                config=config_run,
                stream_mode="values",
            ):
                serializable_state = serialize_graph_state(event)
                final_state = serializable_state
                logger.info(
                    f"phase=api_invoke_stream | thread_id={request.thread_id} | event=state"
                )
                yield format_sse_event("state", {"state": serializable_state})

            if final_state is None:
                final_state = {}

            logger.info(f"phase=api_invoke_stream | thread_id={request.thread_id} | event=done")
            yield format_sse_event("done", {"state": final_state})
    except Exception as e:
        logger.error(f"phase=api_invoke_stream | thread_id={request.thread_id} | event=error | error={e}")
        yield format_sse_event("error", {"message": str(e)})


@app.post("/invoke", response_model=ChatResponse)
async def invoke_graph(request: ChatRequest):
    """
    Invoke the ClosedLoop graph with user input.
    """
    logger.info(f"phase=api_invoke | input={request.user_input} | thread_id={request.thread_id}")
    
    try:
        config_run = {"configurable": {"thread_id": request.thread_id}}
        db_path = _get_sessions_db_path()

        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)
            
            final_state = await workflow_app.ainvoke(
                {"messages": [("user", request.user_input)]}, 
                config=config_run
            )
        serializable_state = serialize_graph_state(final_state)
        return ChatResponse(status="success", state=serializable_state)
    except Exception as e:
        logger.error(f"phase=api_invoke | error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoke/stream")
async def invoke_graph_stream(request: ChatRequest):
    """Stream invoke state snapshots via SSE."""
    return StreamingResponse(
        _stream_invoke_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": config.PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    # 通过 uvicorn 运行（也可以使用 uv run uvicorn）
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
