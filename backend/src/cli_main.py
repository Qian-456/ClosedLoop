import sys
import os

# 将 src 目录添加到 sys.path 中以确保内部导入正常工作
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager
from closedloop.graph.agent import agent


def main():
    # 1. 加载配置并初始化日志
    config = get_config()
    LoggerManager.setup(config)
    
    # 2. 定义运行配置（指定 thread_id 以维持多轮对话状态）
    run_config = {"configurable": {"thread_id": "support_session_002"}}
    
    print("Agent已启动。您可以开始对话。输入 '/exit' 退出。")

    while True:
        try:
            user_input = input("\nUser: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.strip() == "/exit":
            print("退出对话。")
            break
            
        if not user_input.strip():
            continue

        input_data = {"messages": [("user", user_input)]}

        # 使用 stream 循环打印
        # stream_mode="values" 会返回每一步图状态更新后的结果
        for event in agent.stream(input_data, config=run_config, stream_mode="values"):
            # 获取最后一条消息
            if "messages" in event:
                last_msg = event["messages"][-1]
                
                # 跳过打印用户自己刚刚输入的消息
                if getattr(last_msg, "type", "") == "human":
                    continue
                    
                print(f"--- Agent 动作 ---")
                try:
                    print(last_msg.content)
                except Exception:
                    print(last_msg.content.encode("gbk", "ignore").decode("gbk"))

                # 如果有 tool_calls，也打印出来
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    print("Tool Calls:", last_msg.tool_calls)

if __name__ == "__main__":
    main()
