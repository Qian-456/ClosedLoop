import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json

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
import aiosqlite
import os

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

@app.post("/invoke", response_model=ChatResponse)
async def invoke_graph(request: ChatRequest):
    """
    Invoke the ClosedLoop graph with user input.
    """
    logger.info(f"phase=api_invoke | input={request.user_input} | thread_id={request.thread_id}")
    
    try:
        config_run = {"configurable": {"thread_id": request.thread_id}}
        
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../mock_data/runtime/sessions.sqlite"))
        
        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            workflow_app = build_agent_with_async_checkpointer(checkpointer)
            
            final_state = await workflow_app.ainvoke(
                {"messages": [("user", request.user_input)]}, 
                config=config_run
            )
        
        # 将 LangGraph 原生的 Message 对象转换为前端可识别的字典格式
        serializable_state = dict(final_state)
        if "messages" in serializable_state:
            serializable_messages = []
            for msg in serializable_state["messages"]:
                msg_type = getattr(msg, "type", "unknown")
                
                # 如果是 AI 消息且没有 content 但有 tool_calls，我们可以将 tool_calls 的名称作为占位提示，或者忽略
                content = getattr(msg, "content", "")
                if not content and hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_names = ", ".join([tc.get("name", "tool") for tc in msg.tool_calls])
                    content = f"*[正在调用工具: {tool_names}...]*"
                
                serializable_messages.append({
                    "id": getattr(msg, "id", None),
                    "type": msg_type,
                    "content": content
                })
            serializable_state["messages"] = serializable_messages
            
        return ChatResponse(status="success", state=serializable_state)
    except Exception as e:
        logger.error(f"phase=api_invoke | error={e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": config.PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    # 通过 uvicorn 运行（也可以使用 uv run uvicorn）
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
