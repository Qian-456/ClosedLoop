import asyncio
from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.types import Command
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, AIMessage
import os

os.environ["DASHSCOPE_API_KEY"] = "sk-123456" # Dummy key just to init

@tool
def my_tool() -> Command:
    """My tool"""
    return Command(update={"my_state": "executed", "messages": [("tool", "success")]})

async def main():
    from langgraph.prebuilt.tool_node import ToolNode
    node = ToolNode([my_tool])
    msg = AIMessage(content="", tool_calls=[{"name": "my_tool", "args": {}, "id": "123"}])
    res = await node.ainvoke({"messages": [msg]})
    print("TOOL NODE RESULT:", res)

asyncio.run(main())