import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import re
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


def _extract_text_content(content: Any) -> str:
    """Extract plain text from streamed LangGraph message chunks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _sanitize_message_text(text: str) -> str:
    """Remove raw tool payloads from user-facing streamed text."""
    if not text:
        return ""

    sanitized = text
    sanitized = re.sub(
        r'\{[\s\S]*?"tool"\s*:\s*"[^"]+"[\s\S]*?"result"\s*:\s*\{[\s\S]*?\}[\s\S]*?\}',
        "",
        sanitized,
    )
    stripped = sanitized.strip()
    if stripped.startswith("{") and '"tool"' in stripped and '"status"' in stripped:
        return ""
    return sanitized.strip()


def _extract_tool_payload(message: Any) -> dict[str, Any] | None:
    """Parse a tool payload from a LangGraph update message when possible."""
    content = getattr(message, "content", None)
    if not isinstance(content, str):
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    if not isinstance(parsed.get("tool"), str):
        return None
    if not isinstance(parsed.get("status"), str):
        return None
    return parsed


def _build_process_summary(tool_payload: dict[str, Any]) -> str:
    """Create a concise product-facing summary for one tool event."""
    tool_name = tool_payload.get("tool", "tool")
    status = tool_payload.get("status", "unknown")
    result = tool_payload.get("result")

    if tool_name == "plan_trip":
        if isinstance(result, dict):
            plans = result.get("plans")
            if isinstance(plans, list) and plans:
                return f"已生成 {len(plans)} 套方案"
        return "正在生成方案结果"

    if tool_name == "generate_alternative_plans":
        if isinstance(result, dict):
            plans = result.get("plans")
            if isinstance(plans, list):
                return f"已补充 {len(plans)} 套备选方案"
        return "正在生成更多备选方案"

    if tool_name == "search_candidates":
        if isinstance(result, dict):
            items = result.get("items") or result.get("candidates")
            if isinstance(items, list):
                return f"已召回 {len(items)} 个候选地点"
        return "正在召回候选地点"

    if tool_name == "adjust_plan_item":
        return "已完成当前方案调整"

    if tool_name == "execute_itinerary":
        return "已同步执行结果"

    if status == "success":
        return f"{tool_name} 已完成"
    if status == "failed":
        return f"{tool_name} 执行失败"
    return f"{tool_name} 处理中"


def _step_to_status(step: str | None, node_name: str | None = None) -> dict[str, str]:
    """Map runtime graph steps to product-facing status copy."""
    value = step or node_name or ""
    mapping = {
        "search_candidates": {
            "phase": "retrieving",
            "text": "正在召回候选地点",
        },
        "plan_trip": {
            "phase": "planning",
            "text": "正在生成行程方案",
        },
        "generate_alternative_plans": {
            "phase": "planning",
            "text": "正在生成行程方案",
        },
        "adjust_plan_item": {
            "phase": "planning",
            "text": "正在调整当前方案",
        },
        "transfer_to_execute": {
            "phase": "finalizing",
            "text": "正在整理推荐结果",
        },
        "confirm_trip": {
            "phase": "finalizing",
            "text": "正在同步执行确认结果",
        },
    }
    return mapping.get(
        value,
        {
            "phase": "understanding",
            "text": "正在理解你的需求",
        },
    )


def _iter_update_entries(update_data: Any) -> list[tuple[str | None, dict[str, Any]]]:
    """Normalize LangGraph update chunks into node/update pairs."""
    if not isinstance(update_data, dict):
        return []

    normalized: list[tuple[str | None, dict[str, Any]]] = []
    for node_name, update in update_data.items():
        if isinstance(update, dict):
            normalized.append((str(node_name), update))
    return normalized


def _build_result_payload(update: dict[str, Any]) -> dict[str, Any] | None:
    """Build the frontend result payload from a state update."""
    result: dict[str, Any] = {}
    if "latest_plan_result" in update and update["latest_plan_result"] is not None:
        latest_plans = update["latest_plan_result"]
        if isinstance(latest_plans, list):
            result["itinerary"] = {
                "plans": latest_plans,
                "status": "ok",
            }
    if "itinerary" in update and update["itinerary"] is not None:
        itinerary_value = update["itinerary"]
        if isinstance(itinerary_value, dict):
            result["itinerary"] = itinerary_value
        elif isinstance(itinerary_value, list) and "itinerary" not in result:
            result["itinerary"] = {
                "plans": itinerary_value,
                "status": "ok",
            }
    if "confirmation" in update and update["confirmation"] is not None:
        result["confirmation"] = update["confirmation"]
    if "constraints" in update and update["constraints"] is not None:
        result["constraints"] = update["constraints"]
    if "current_step" in update and update["current_step"] is not None:
        result["current_step"] = update["current_step"]
    return result or None


async def _build_workflow_app():
    """Create the workflow app with sqlite checkpoint support."""
    db_path = _get_sessions_db_path()
    checkpointer = AsyncSqliteSaver.from_conn_string(db_path)
    return checkpointer, build_agent_with_async_checkpointer


async def _stream_invoke_events(request: ChatRequest) -> AsyncIterator[str]:
    """Yield normalized product events via SSE for the invoke stream endpoint."""
    logger.info(f"phase=api_invoke_stream | input={request.user_input} | thread_id={request.thread_id}")
    config_run = {"configurable": {"thread_id": request.thread_id}}

    try:
        last_status_payload: str | None = None
        last_result_payload: str | None = None
        emitted_process_signatures: set[str] = set()
        yield format_sse_event(
            "status",
            {
                "phase": "understanding",
                "text": "正在理解你的需求",
                "step": "bootstrap",
            },
        )

        db_path = _get_sessions_db_path()
        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)

            async for part in workflow_app.astream(
                {"messages": [("user", request.user_input)]},
                config=config_run,
                stream_mode=["messages", "updates", "custom"],
                version="v2",
            ):
                part_type = part.get("type")
                part_data = part.get("data")

                if part_type == "messages" and isinstance(part_data, tuple) and len(part_data) == 2:
                    message_chunk, metadata = part_data
                    content = _sanitize_message_text(
                        _extract_text_content(getattr(message_chunk, "content", ""))
                    )
                    if content:
                        logger.info(
                            f"phase=api_invoke_stream | thread_id={request.thread_id} | event=message"
                        )
                        yield format_sse_event(
                            "message",
                            {
                                "text": content,
                                "node": metadata.get("langgraph_node") if isinstance(metadata, dict) else None,
                            },
                        )
                    continue

                if part_type == "updates":
                    for node_name, update in _iter_update_entries(part_data):
                        status_payload = _step_to_status(
                            update.get("current_step") if isinstance(update, dict) else None,
                            node_name=node_name,
                        )
                        status_payload["step"] = update.get("current_step") or node_name or "unknown"
                        status_signature = json.dumps(status_payload, ensure_ascii=False, sort_keys=True)
                        if status_signature != last_status_payload:
                            last_status_payload = status_signature
                            logger.info(
                                f"phase=api_invoke_stream | thread_id={request.thread_id} | event=status | step={status_payload['step']}"
                            )
                            yield format_sse_event("status", status_payload)

                        for message in update.get("messages", []) if isinstance(update, dict) else []:
                            tool_payload = _extract_tool_payload(message)
                            if tool_payload is None:
                                continue

                            process_payload = {
                                "tool": tool_payload["tool"],
                                "status": tool_payload["status"],
                                "step": update.get("current_step") or node_name or "unknown",
                                "summary": _build_process_summary(tool_payload),
                                "raw": tool_payload,
                            }
                            process_signature = json.dumps(
                                process_payload, ensure_ascii=False, sort_keys=True
                            )
                            if process_signature in emitted_process_signatures:
                                continue
                            emitted_process_signatures.add(process_signature)
                            logger.info(
                                f"phase=api_invoke_stream | thread_id={request.thread_id} | event=process | tool={process_payload['tool']}"
                            )
                            yield format_sse_event("process", process_payload)

                        result_payload = _build_result_payload(update)
                        if result_payload is not None:
                            result_signature = json.dumps(result_payload, ensure_ascii=False, sort_keys=True)
                            if result_signature != last_result_payload:
                                last_result_payload = result_signature
                                logger.info(
                                    f"phase=api_invoke_stream | thread_id={request.thread_id} | event=result"
                                )
                                yield format_sse_event("result", result_payload)

            logger.info(f"phase=api_invoke_stream | thread_id={request.thread_id} | event=done")
            yield format_sse_event("done", {"success": True})
    except Exception as e:
        logger.error(f"phase=api_invoke_stream | thread_id={request.thread_id} | event=error | error={e}")
        yield format_sse_event(
            "error",
            {
                "message": str(e),
                "code": "STREAM_ERROR",
                "recoverable": True,
            },
        )


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
