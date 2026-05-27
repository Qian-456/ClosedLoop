import asyncio
import os
import sys

from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver


CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_SRC_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "backend", "src"))

if BACKEND_SRC_DIR not in sys.path:
    sys.path.insert(0, BACKEND_SRC_DIR)

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager
from closedloop.graph.agent import build_agent_with_async_checkpointer


def build_docs_demo_agent():
    """Build the docs demo agent by reusing the backend graph builder."""
    config = get_config()
    LoggerManager.setup(config)
    return build_agent_with_async_checkpointer(MemorySaver())


def _get_block_type(block):
    """Extract the raw block type from dict or object content blocks."""
    if isinstance(block, dict):
        return block.get("type") or "other"
    return getattr(block, "type", None) or "other"


def _get_block_text(block):
    """Return streamable text for a content block."""
    if isinstance(block, dict):
        if block.get("type") == "text":
            return block.get("text", "")
        if block.get("type") == "tool_call_chunk":
            return block.get("args", "")
        return block.get("text", "") or block.get("args", "") or ""

    if getattr(block, "type", None) == "text":
        return getattr(block, "text", "")
    if getattr(block, "type", None) == "tool_call_chunk":
        return getattr(block, "args", "")
    return getattr(block, "text", "") or getattr(block, "args", "") or ""


def _flush_group(group_type, parts):
    """Print one grouped block section when buffered content exists."""
    if not group_type or not parts:
        return None, []

    print(f"---{group_type}---")
    print("".join(parts))
    print()
    return None, []


def _render_message_chunk(token, current_group_type, current_parts):
    """Group consecutive content blocks by type and print on type switches."""
    for block in getattr(token, "content_blocks", []):
        block_type = _get_block_type(block)
        block_text = _get_block_text(block)
        if not block_text:
            continue

        if current_group_type is not None and block_type != current_group_type:
            current_group_type, current_parts = _flush_group(current_group_type, current_parts)

        if current_group_type is None:
            current_group_type = block_type

        current_parts.append(block_text)

    return current_group_type, current_parts


async def _run_turn(agent, user_input, thread_id):
    """Run one chat turn while keeping the same thread memory."""
    current_group_type = None
    current_parts = []

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode=["messages", "updates"],
        version="v2",
    ):
        if chunk["type"] == "messages":
            token, metadata = chunk["data"]
            if isinstance(token, AIMessageChunk):
                current_group_type, current_parts = _render_message_chunk(
                    token, current_group_type, current_parts
                )
        elif chunk["type"] == "updates":
            for source, update in chunk["data"].items():
                if source in ("model", "tools"):
                    current_group_type, current_parts = _flush_group(
                        current_group_type, current_parts
                    )

    _flush_group(current_group_type, current_parts)


async def main():
    """Run an interactive CLI chat loop for manual memory checks."""
    agent = build_docs_demo_agent()
    thread_id = "test"

    while True:
        user_input = input("user> ").strip()
        if not user_input or user_input.lower() in {"exit", "quit"}:
            break
        await _run_turn(agent, user_input, thread_id)


if __name__ == "__main__":
    asyncio.run(main())
