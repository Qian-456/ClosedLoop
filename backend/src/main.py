import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
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

if __name__ == "__main__":
    import uvicorn
    # 通过 uvicorn 运行（也可以使用 uv run uvicorn）
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
