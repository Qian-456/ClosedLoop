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
from closedloop.graph.build import build_graph
from closedloop.contracts.state import ClosedLoopState

# 初始化配置与日志
config = get_config()
LoggerManager.setup(config)

app = FastAPI(title=config.PROJECT_NAME)

# 在应用启动时构建单例的 Graph (避免每次请求重建)
workflow_app = build_graph()

class ChatRequest(BaseModel):
    user_input: str

class ChatResponse(BaseModel):
    status: str
    state: dict

@app.post("/invoke", response_model=ChatResponse)
async def invoke_graph(request: ChatRequest):
    """
    Invoke the ClosedLoop graph with user input.
    """
    logger.info(f"phase=api_invoke | input={request.user_input}")
    
    try:
        # 初始化状态
        initial_state: ClosedLoopState = {
            "user_input": request.user_input
        }
        
        # 执行 graph
        final_state = workflow_app.invoke(initial_state)
        
        return ChatResponse(
            status="success",
            state=final_state
        )
    except Exception as e:
        logger.error(f"phase=api_invoke | error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": config.PROJECT_NAME}


@app.post("/execute/start", response_model=ExecutionStartResponse)
async def execute_start(request: ExecuteRequest):
    logger.info(f"phase=api_execute_start | input=plan_id={request.plan_id} steps={len(request.steps)}")
    try:
        execution_id = await start_execution(request)
        logger.info(f"phase=api_execute_start | output=execution_id={execution_id}")
        return ExecutionStartResponse(execution_id=execution_id)
    except Exception as e:
        logger.error(f"phase=api_execute_start | error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/execute/events/{execution_id}")
async def execute_events(execution_id: str):
    logger.info(f"phase=api_execute_events | input=execution_id={execution_id}")

    async def _event_stream():
        async for event in iter_events(execution_id):
            payload = json.dumps(event, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

if __name__ == "__main__":
    import uvicorn
    # 通过 uvicorn 运行（也可以使用 uv run uvicorn）
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
