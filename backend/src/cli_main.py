import sys
import os
import asyncio

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.agent import agent


async def async_main():
    # 1. 加载配置并初始化日志
    config = get_config()
    LoggerManager.setup(config)
    
    # 2. 定义运行配置（指定 thread_id 以维持多轮对话状态）
    run_config = {"configurable": {"thread_id": "support_session_002"}}
    
    logger.info("Agent已启动。您可以开始对话。输入 '/exit' 退出。")

    while True:
        try:
            # 运行在独立线程以避免阻塞事件循环
            user_input = await asyncio.to_thread(input, "\nUser: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.strip() == "/exit":
            logger.info("退出对话。")
            break
            
        if not user_input.strip():
            continue
            
        logger.info(f"User: {user_input}")

        input_data = {"messages": [("user", user_input)]}

        # 使用 astream 异步循环打印
        # stream_mode="values" 会返回每一步图状态更新后的结果
        try:
            async for event in agent.astream(input_data, config=run_config, stream_mode="values"):
                # 获取最后一条消息
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    
                    # 跳过打印用户自己刚刚输入的消息
                    if getattr(last_msg, "type", "") == "human":
                        continue
                        
                    logger.info("--- Agent 动作 ---")
                    try:
                        logger.info(last_msg.content)
                    except Exception:
                        logger.info(last_msg.content.encode("gbk", "ignore").decode("gbk"))

                    # 如果有 tool_calls，也打印出来
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        logger.info(f"Tool Calls: {last_msg.tool_calls}")
        except Exception as e:
            logger.exception("Agent execution failed")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
