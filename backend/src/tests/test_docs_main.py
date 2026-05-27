import importlib.util
import asyncio
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessageChunk


def _load_docs_main_module():
    """Load the docs/main.py module for isolated testing."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    file_path = os.path.join(repo_root, "docs", "main.py")
    spec = importlib.util.spec_from_file_location("docs_main", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestDocsMain(unittest.TestCase):
    """Test cases for the docs streaming example script."""

    def test_build_docs_demo_agent_reuses_graph_builder(self):
        """The docs demo agent should reuse the backend graph builder."""
        docs_main = _load_docs_main_module()
        fake_checkpointer = object()
        fake_agent = object()

        with (
            patch.object(docs_main, "get_config", return_value=object()),
            patch.object(docs_main.LoggerManager, "setup"),
            patch.object(docs_main, "MemorySaver", return_value=fake_checkpointer),
            patch.object(
                docs_main,
                "build_agent_with_async_checkpointer",
                return_value=fake_agent,
            ) as mock_build_agent,
        ):
            result = docs_main.build_docs_demo_agent()

        self.assertIs(result, fake_agent)
        mock_build_agent.assert_called_once_with(fake_checkpointer)

    def test_main_astream_uses_test_thread_id(self):
        """The docs main chat loop should use async streaming with a stable thread id."""
        docs_main = _load_docs_main_module()
        stream_calls = []
        fake_stdout = io.StringIO()

        class _FakeAgent:
            async def astream(self, payload, config=None, stream_mode=None, version=None):
                stream_calls.append((payload, config, stream_mode, version))
                yield {
                    "type": "messages",
                    "data": (
                        AIMessageChunk(content_blocks=[{"type": "text", "text": "ok"}]),
                        {"langgraph_node": "plan_agent"},
                    ),
                }
                yield {"type": "updates", "data": {}}

        with (
            patch.object(docs_main, "build_docs_demo_agent", return_value=_FakeAgent()),
            patch("builtins.input", side_effect=["第一轮消息", "exit"]),
            patch("sys.stdout", new=fake_stdout),
        ):
            asyncio.run(docs_main.main())

        self.assertEqual(len(stream_calls), 1)
        _, config, stream_mode, version = stream_calls[0]
        self.assertEqual(config, {"configurable": {"thread_id": "test"}})
        self.assertEqual(stream_mode, ["messages", "updates"])
        self.assertEqual(version, "v2")

    def test_main_reuses_same_thread_id_across_turns(self):
        """The docs main chat loop should reuse the same thread id across multiple turns."""
        docs_main = _load_docs_main_module()
        stream_calls = []
        fake_stdout = io.StringIO()

        class _FakeAgent:
            async def astream(self, payload, config=None, stream_mode=None, version=None):
                stream_calls.append((payload, config, stream_mode, version))
                yield {
                    "type": "messages",
                    "data": (
                        AIMessageChunk(content_blocks=[{"type": "text", "text": "ok"}]),
                        {"langgraph_node": "plan_agent"},
                    ),
                }
                yield {"type": "updates", "data": {"model": {"messages": [SimpleNamespace()]}}}

        with (
            patch.object(docs_main, "build_docs_demo_agent", return_value=_FakeAgent()),
            patch("builtins.input", side_effect=["第一轮", "第二轮", "quit"]),
            patch("sys.stdout", new=fake_stdout),
        ):
            asyncio.run(docs_main.main())

        self.assertEqual(len(stream_calls), 2)
        first_payload, first_config, _, _ = stream_calls[0]
        second_payload, second_config, _, _ = stream_calls[1]
        self.assertEqual(first_payload["messages"][0]["content"], "第一轮")
        self.assertEqual(second_payload["messages"][0]["content"], "第二轮")
        self.assertEqual(first_config, {"configurable": {"thread_id": "test"}})
        self.assertEqual(second_config, {"configurable": {"thread_id": "test"}})

    def test_main_groups_message_chunks_by_block_type(self):
        """The docs main renderer should merge consecutive blocks by type and split on type changes."""
        docs_main = _load_docs_main_module()
        fake_stdout = io.StringIO()

        class _FakeAgent:
            async def astream(self, payload, config=None, stream_mode=None, version=None):
                yield {
                    "type": "messages",
                    "data": (
                        AIMessageChunk(content_blocks=[{"type": "text", "text": "调"}]),
                        {"langgraph_node": "model"},
                    ),
                }
                yield {
                    "type": "messages",
                    "data": (
                        AIMessageChunk(
                            content_blocks=[
                                {"type": "text", "text": "整"},
                                {"type": "tool_call_chunk", "args": "plan"},
                                {"type": "tool_call_chunk", "args": "_trip"},
                            ]
                        ),
                        {"langgraph_node": "model"},
                    ),
                }
                yield {"type": "updates", "data": {"model": {"messages": [SimpleNamespace()]}}}
                yield {
                    "type": "messages",
                    "data": (
                        AIMessageChunk(content_blocks=[{"type": "text", "text": "完成"}]),
                        {"langgraph_node": "model"},
                    ),
                }
                yield {"type": "updates", "data": {"tools": {"messages": [SimpleNamespace()]}}}

        with (
            patch.object(docs_main, "build_docs_demo_agent", return_value=_FakeAgent()),
            patch("builtins.input", side_effect=["第一轮消息", "exit"]),
            patch("sys.stdout", new=fake_stdout),
        ):
            asyncio.run(docs_main.main())

        self.assertEqual(
            fake_stdout.getvalue(),
            "---text---\n"
            "调整\n\n"
            "---tool_call_chunk---\n"
            "plan_trip\n\n"
            "---text---\n"
            "完成\n\n",
        )


if __name__ == "__main__":
    unittest.main()
