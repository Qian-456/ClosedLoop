import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk
from pydantic import BaseModel
from contextlib import asynccontextmanager, suppress
from langgraph.types import Command

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.execution import ExecuteRequest, ExecutionStartResponse
from closedloop.execution.mock_executor import commit_execution_payment, iter_events, start_execution
from closedloop.graph.agent import build_agent_with_async_checkpointer
from closedloop.contracts.state import ClosedLoopState
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 初始化配置与日志
config = get_config()
LoggerManager.setup(config)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title=config.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
        r"10\.\d+\.\d+\.\d+|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|"
        r"192\.168\.\d+\.\d+"
        r")(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_input: str = ""
    thread_id: str = "default_session"

class ChatResponse(BaseModel):
    status: str
    state: dict


class MockPaymentCommitRequest(BaseModel):
    payment_password: str


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
    
    # 保证前端收到的 itinerary 格式为 { "plans": [...] }
    if "itinerary" in serializable_state:
        itinerary_val = serializable_state["itinerary"]
        if isinstance(itinerary_val, list):
            serializable_state["itinerary"] = {
                "plans": itinerary_val,
                "status": "ok"
            }
    elif "latest_plan_result" in serializable_state:
        latest_plans = serializable_state["latest_plan_result"]
        if isinstance(latest_plans, list):
            serializable_state["itinerary"] = {
                "plans": latest_plans,
                "status": "ok"
            }
            
    return serializable_state


def format_sse_event(event_name: str, data: dict[str, Any]) -> str:
    """Format one SSE event block."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


@app.post("/execution/{execution_id}/commit")
async def commit_mock_payment(
    execution_id: str,
    request: MockPaymentCommitRequest,
) -> dict[str, Any]:
    """提交 Mock 支付，密码正确后才执行 Mock 扣减。"""

    result = await commit_execution_payment(
        execution_id=execution_id,
        payment_password=request.payment_password,
    )
    if result.get("commit_status") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    return result


def _get_block_type(block: Any) -> str:
    """Extract the raw content block type from dict or object values."""
    if isinstance(block, dict):
        return str(block.get("type") or "other")
    return str(getattr(block, "type", None) or "other")


def _get_block_text(block: Any) -> str:
    """Return streamable text from one content block."""
    if isinstance(block, dict):
        if block.get("type") == "text":
            return str(block.get("text", ""))
        if block.get("type") == "tool_call_chunk":
            return str(block.get("args", ""))
        return str(block.get("text", "") or block.get("args", "") or "")

    if getattr(block, "type", None) == "text":
        return str(getattr(block, "text", ""))
    if getattr(block, "type", None) == "tool_call_chunk":
        return str(getattr(block, "args", ""))
    return str(getattr(block, "text", "") or getattr(block, "args", "") or "")


def _extract_message_text_from_chunk(token: AIMessageChunk) -> str:
    """Extract user-visible text blocks from one AIMessageChunk."""
    if isinstance(token.content, str):
        return token.content

    parts: list[str] = []
    if isinstance(token.content, list):
        for block in token.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "".join(parts)


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
        if isinstance(result, dict):
            if result.get("payment_status") == "pending" or result.get("payment_required") is True:
                return "已生成待支付执行命令"
            execution_summary = result.get("execution_summary")
            if isinstance(execution_summary, dict):
                replacements = execution_summary.get("replacements") or []
                failures = execution_summary.get("failures") or []
                if isinstance(replacements, list) and isinstance(failures, list):
                    return f"执行完成：替换 {len(replacements)} 项，失败 {len(failures)} 项"
        return "执行完成"

    if status == "success":
        return f"{tool_name} 已完成"
    if status == "failed":
        return f"{tool_name} 执行失败"
    return f"{tool_name} 处理中"


def _map_tool_title(tool_name: str) -> str:
    """Map internal tool names to user-facing titles."""
    mapping = {
        "plan_trip": "规划方案",
        "search_candidates": "召回候选地点",
        "generate_alternative_plans": "生成备选方案",
        "adjust_plan_item": "调整方案",
        "transfer_to_execute": "切换执行确认",
        "confirm_trip": "整理执行结果",
        "execute_itinerary": "执行行程",
    }
    return mapping.get(tool_name, tool_name)


def _resolve_bubble_phase(step_or_node: str | None) -> str:
    """Resolve the bubble phase from a runtime step or node."""
    value = step_or_node or ""
    supported_phases = {
        "search_candidates",
        "plan_trip",
        "generate_alternative_plans",
        "adjust_plan_item",
        "transfer_to_execute",
        "confirm_trip",
    }
    if value in supported_phases:
        return value
    return "bootstrap"


def _resolve_bubble_text(phase: str) -> str:
    """Map one bubble phase to user-facing copy."""
    mapping = {
        "search_candidates": "正在搜索",
        "plan_trip": "正在规划方案",
        "generate_alternative_plans": "正在生成更多备选方案",
        "adjust_plan_item": "正在调整方案",
        "transfer_to_execute": "正在切换到执行确认",
        "confirm_trip": "正在整理执行结果",
        "done": "已完成规划",
        "error": "处理失败，请稍后重试",
        "bootstrap": "正在思考",
    }
    return mapping.get(phase, mapping["bootstrap"])


def _build_tool_meta(tool_payload: dict[str, Any]) -> list[str]:
    """Build display metadata for one tool entry."""
    result = tool_payload.get("result")
    meta: list[str] = []

    if not isinstance(result, dict):
        return meta

    if tool_payload.get("tool") in {"plan_trip", "generate_alternative_plans"}:
        plans = result.get("plans")
        if isinstance(plans, list) and plans:
            meta.append(f"{len(plans)} 个方案")
            first_plan = plans[0] if isinstance(plans[0], dict) else {}
            total_cost = first_plan.get("total_cost")
            total_duration_minutes = first_plan.get("total_duration_minutes")
            if isinstance(total_cost, (int, float)):
                meta.append(f"预算 {total_cost:g} 元")
            if isinstance(total_duration_minutes, (int, float)):
                meta.append(f"总时长 {total_duration_minutes:g} 分钟")
        return meta

    if tool_payload.get("tool") == "search_candidates":
        items = result.get("items") or result.get("candidates")
        if isinstance(items, list):
            meta.append(f"{len(items)} 个候选地点")
    return meta


def _build_bubble_entries(update: dict[str, Any], node_name: str | None) -> list[dict[str, Any]]:
    """Build grouped bubble entries from one update chunk."""
    step = update.get("current_step") or node_name or "bootstrap"
    phase = _resolve_bubble_phase(step)
    text = _resolve_bubble_text(phase)
    entries: list[dict[str, Any]] = [
        {
            "kind": "step",
            "title": "阶段切换",
            "summary": text,
        }
    ]

    for message in update.get("messages", []) if isinstance(update, dict) else []:
        tool_payload = _extract_tool_payload(message)
        if tool_payload is None:
            continue

        entry: dict[str, Any] = {
            "kind": "tool",
            "tool": tool_payload["tool"],
            "title": _map_tool_title(tool_payload["tool"]),
            "summary": _build_process_summary(tool_payload),
            "status": tool_payload["status"],
            "raw": tool_payload,
        }
        meta = _build_tool_meta(tool_payload)
        if meta:
            entry["meta"] = meta
        entries.append(entry)
    return entries


def _build_bubble_payload(node_name: str | None, update: dict[str, Any]) -> dict[str, Any]:
    """Build one normalized bubble event payload from a LangGraph update."""
    step = update.get("current_step") or node_name or "bootstrap"
    phase = _resolve_bubble_phase(step)
    return {
        "phase": phase,
        "step": step,
        "node": node_name,
        "text": _resolve_bubble_text(phase),
        "status": "running",
        "entries": _build_bubble_entries(update, node_name),
    }


def _iter_update_entries(update_data: Any) -> list[tuple[str | None, dict[str, Any]]]:
    """Normalize LangGraph update chunks into node/update pairs."""
    if not isinstance(update_data, dict):
        return []

    normalized: list[tuple[str | None, dict[str, Any]]] = []
    for node_name, update in update_data.items():
        if isinstance(update, dict):
            normalized.append((str(node_name), update))
    return normalized


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if hasattr(value, "model_dump"):
        try:
            return _to_jsonable(value.model_dump())
        except Exception:
            return str(value)

    if hasattr(value, "dict"):
        try:
            return _to_jsonable(value.dict())
        except Exception:
            return str(value)

    if hasattr(value, "value") and not isinstance(value, dict):
        try:
            return _to_jsonable(getattr(value, "value"))
        except Exception:
            return str(value)

    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]

    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}

    return str(value)


def _normalize_interrupt_payload(interrupt_raw: Any) -> dict[str, Any]:
    raw = interrupt_raw
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]

    if hasattr(raw, "value") and not isinstance(raw, dict):
        raw = getattr(raw, "value")

    if isinstance(raw, dict) and "value" in raw:
        raw = raw["value"]

    normalized = _to_jsonable(raw)
    if isinstance(normalized, dict):
        return normalized
    return {"message": "graph_interrupted", "raw": normalized}


def _interrupt_summary_text(interrupt_payload: dict[str, Any]) -> str | None:
    action_requests = interrupt_payload.get("action_requests") or interrupt_payload.get("actionRequests")
    if isinstance(action_requests, list) and action_requests:
        first = action_requests[0]
        if isinstance(first, dict):
            desc = first.get("description") or first.get("descriptionPrefix")
            if isinstance(desc, str) and desc.strip():
                return desc.strip()
    return None


def _build_result_payload(update: dict[str, Any]) -> dict[str, Any] | None:
    """Build the frontend result payload from a state update."""
    result: dict[str, Any] = {}
    
    if "itinerary" in update and update["itinerary"] is not None:
        itinerary_value = update["itinerary"]
        if isinstance(itinerary_value, dict):
            result["itinerary"] = itinerary_value
        elif isinstance(itinerary_value, list):
            result["itinerary"] = {
                "plans": itinerary_value,
                "status": "ok",
            }
    elif "latest_plan_result" in update and update["latest_plan_result"] is not None:
        latest_plans = update["latest_plan_result"]
        if isinstance(latest_plans, list):
            result["itinerary"] = {
                "plans": latest_plans,
                "status": "ok",
            }

    if "confirmation" in update and update["confirmation"] is not None:
        result["confirmation"] = update["confirmation"]
    if "constraints" in update and update["constraints"] is not None:
        result["constraints"] = update["constraints"]
    if "execution_report" in update and update["execution_report"] is not None:
        result["execution_report"] = update["execution_report"]
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
    runtime_config = get_config()
    hitl_heartbeat_secs = float(getattr(runtime_config, "HITL_RESUME_HEARTBEAT_SECS", 1.0))
    hitl_max_wait_secs = float(getattr(runtime_config, "HITL_RESUME_MAX_WAIT_SECS", 3.0))

    try:
        last_bubble_payload: str | None = None
        last_result_payload: str | None = None
        bootstrap_bubble = {
            "phase": "bootstrap",
            "step": "bootstrap",
            "node": None,
            "text": _resolve_bubble_text("bootstrap"),
            "status": "running",
            "entries": [
                {
                    "kind": "step",
                    "title": "进入流程",
                    "summary": _resolve_bubble_text("bootstrap"),
                }
            ],
        }
        yield format_sse_event(
            "bubble",
            bootstrap_bubble,
        )

        db_path = _get_sessions_db_path()
        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)

            input_payload: Any = {"messages": [("user", request.user_input)]}
            aiter = workflow_app.astream(
                input_payload,
                config=config_run,
                stream_mode=["messages", "updates", "custom"],
                version="v2",
            ).__aiter__()
            heartbeat_ms = max(1, int(hitl_heartbeat_secs * 1000))
            waited_ms = 0
            pending_task: asyncio.Task | None = None
            while True:
                if pending_task is None:
                    pending_task = asyncio.create_task(anext(aiter))

                done, _ = await asyncio.wait({pending_task}, timeout=hitl_heartbeat_secs)
                if not done:
                    waited_ms += heartbeat_ms
                    waiting_bubble = {
                        "phase": "waiting_response",
                        "step": "waiting_response",
                        "node": None,
                        "text": "正在等待系统返回…",
                        "status": "running",
                        "entries": [
                            {
                                "kind": "step",
                                "title": "等待返回",
                                "summary": "正在等待系统返回…",
                            },
                            {
                                "kind": "meta",
                                "title": "已等待",
                                "summary": f"{waited_ms}ms",
                            },
                        ],
                    }
                    yield format_sse_event("bubble", waiting_bubble)
                    logger.info(
                        f"phase=api_invoke_stream | thread_id={request.thread_id} | event=heartbeat | waited_ms={waited_ms}"
                    )
                    if waited_ms >= int(hitl_max_wait_secs * 1000):
                        logger.warning(
                            f"phase=api_invoke_stream | thread_id={request.thread_id} | event=waiting_long | waited_ms={waited_ms}"
                        )
                    continue

                try:
                    part = pending_task.result()
                except StopAsyncIteration:
                    break
                finally:
                    pending_task = None
                waited_ms = 0

                part_type = part.get("type")
                part_data = part.get("data")

                if part_type == "messages" and isinstance(part_data, tuple) and len(part_data) == 2:
                    message_chunk, metadata = part_data
                    if not isinstance(message_chunk, AIMessageChunk):
                        continue
                    content = _extract_message_text_from_chunk(message_chunk)
                    if content:
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
                        bubble_payload = _build_bubble_payload(node_name, update)
                        bubble_signature = json.dumps(
                            bubble_payload, ensure_ascii=False, sort_keys=True
                        )
                        if bubble_signature != last_bubble_payload:
                            last_bubble_payload = bubble_signature
                            logger.info(
                                f"phase=api_invoke_stream | thread_id={request.thread_id} | event=bubble | step={bubble_payload['step']}"
                            )
                            yield format_sse_event("bubble", bubble_payload)

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
    started_at = time.perf_counter()
    logger.info(
        f"phase=api_invoke | event=request_received | thread_id={request.thread_id}"
    )
    logger.info(f"phase=api_invoke | event=graph_start | thread_id={request.thread_id} | input={request.user_input}")
    
    try:
        config_run = {"configurable": {"thread_id": request.thread_id}}
        db_path = _get_sessions_db_path()

        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)

            input_payload: Any = {"messages": [("user", request.user_input)]}

            result = await workflow_app.ainvoke(
                input_payload,
                config=config_run,
                version="v2",
            )

        final_state = getattr(result, "value", None) if hasattr(result, "value") else result
        serializable_state = serialize_graph_state(final_state)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            f"phase=api_invoke | event=graph_end | status=success | thread_id={request.thread_id} | elapsed_ms={elapsed_ms}"
        )
        return ChatResponse(status="success", state=serializable_state)
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.error(
            f"phase=api_invoke | event=graph_end | status=failed | thread_id={request.thread_id} | elapsed_ms={elapsed_ms} | error={e}"
        )
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

@app.post("/execute/start", response_model=ExecutionStartResponse)
async def execute_start(request: ExecuteRequest):
    execution_id = await start_execution(request)
    return ExecutionStartResponse(execution_id=execution_id)

@app.get("/execute/events/{execution_id}")
async def execute_events(execution_id: str):
    async def _iter_sse() -> AsyncIterator[str]:
        async for event in iter_events(execution_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _iter_sse(),
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
