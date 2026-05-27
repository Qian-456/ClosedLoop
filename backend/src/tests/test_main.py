import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

# Add src to path so we can import from core and main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app


class _FakeAsyncContextManager:
    """用于替代 AsyncSqliteSaver 的异步上下文管理器。"""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAgent:
    """同时提供 ainvoke 与 astream 的假 Agent。"""

    def __init__(self, final_state: dict, stream_events: list[dict], stream_error: Exception | None = None):
        self.final_state = final_state
        self.stream_events = stream_events
        self.stream_error = stream_error
        self.ainvoke_calls: list[tuple[dict, dict]] = []
        self.astream_calls: list[tuple[dict, dict, object, object]] = []

    async def ainvoke(self, payload, config=None):
        self.ainvoke_calls.append((payload, config or {}))
        return self.final_state

    async def astream(self, payload, config=None, stream_mode=None, version=None):
        self.astream_calls.append((payload, config or {}, stream_mode, version))
        if self.stream_error is not None:
            raise self.stream_error
        for event in self.stream_events:
            yield event


def _build_message(message_type: str, content: str, *, message_id: str, tool_calls=None):
    return SimpleNamespace(
        id=message_id,
        type=message_type,
        content=content,
        tool_calls=tool_calls or [],
    )


def _build_stream_part(part_type: str, data):
    """构造 LangGraph v2 风格的流式事件片段。"""
    return {
        "type": part_type,
        "ns": (),
        "data": data,
    }


class TestMainAPI(unittest.TestCase):
    """Test cases for the FastAPI application main.py"""

    def setUp(self):
        self.client = TestClient(app)
        self.request_payload = {"user_input": "一家三口出去玩", "thread_id": "thread_test_001"}
        self.final_state = {
            "user_input": "一家三口出去玩",
            "constraints": {
                "group_type": "family",
                "adult_count": 2,
                "child_count": 1,
                "budget": 500.0,
            },
            "messages": [
                _build_message("human", "一家三口出去玩", message_id="msg_h_1"),
                _build_message("ai", "这是最终方案", message_id="msg_ai_2"),
            ],
        }
        self.stream_events = [
            _build_stream_part(
                "messages",
                (
                    _build_message(
                        "ai",
                        '{"tool":"plan_trip","status":"success","result":{"plans":[]}}',
                        message_id="msg_ai_chunk_ignored",
                    ),
                    {"langgraph_node": "plan_agent"},
                ),
            ),
            _build_stream_part(
                "messages",
                (
                    _build_message("ai", "正在帮你规划中", message_id="msg_ai_chunk_1"),
                    {"langgraph_node": "plan_agent"},
                ),
            ),
            _build_stream_part(
                "updates",
                {
                    "plan_trip": {
                        "current_step": "plan_trip",
                        "latest_plan_result": [
                            {
                                "plan_id": "plan_1",
                                "title": "亲子轻松版",
                                "steps": [],
                                "selected_item_ids": [],
                                "total_duration_minutes": 240,
                                "total_cost": 320,
                                "average_score": 88,
                            }
                        ],
                        "messages": [
                            _build_message(
                                "tool",
                                json.dumps(
                                    {
                                        "tool": "plan_trip",
                                        "status": "success",
                                        "result": {
                                            "plans": [
                                                {
                                                    "plan_id": "plan_1",
                                                    "title": "亲子轻松版",
                                                }
                                            ]
                                        },
                                    },
                                    ensure_ascii=False,
                                ),
                                message_id="tool_1",
                            )
                        ],
                    }
                },
            ),
        ]

    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("project", data)

    def test_invoke_graph(self):
        """Test the JSON invoke endpoint with a fake graph response."""
        fake_agent = _FakeAgent(final_state=self.final_state, stream_events=self.stream_events)

        with (
            patch("main.AsyncSqliteSaver.from_conn_string", return_value=_FakeAsyncContextManager()),
            patch("main.build_agent_with_async_checkpointer", return_value=fake_agent),
        ):
            response = self.client.post("/invoke", json=self.request_payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("state", data)
        self.assertIn("constraints", data["state"])
        self.assertEqual(data["state"]["constraints"]["group_type"], "family")
        self.assertEqual(data["state"]["constraints"]["budget"], 500.0)
        self.assertEqual(data["state"]["messages"][1]["content"], "这是最终方案")

        self.assertEqual(len(fake_agent.ainvoke_calls), 1)
        called_payload, called_config = fake_agent.ainvoke_calls[0]
        self.assertEqual(called_payload["messages"][0][1], "一家三口出去玩")
        self.assertEqual(called_config["configurable"]["thread_id"], "thread_test_001")

    def test_invoke_stream_returns_product_events(self):
        """Test the SSE invoke endpoint emits normalized product events."""
        fake_agent = _FakeAgent(final_state=self.final_state, stream_events=self.stream_events)

        with (
            patch("main.AsyncSqliteSaver.from_conn_string", return_value=_FakeAsyncContextManager()),
            patch("main.build_agent_with_async_checkpointer", return_value=fake_agent),
        ):
            response = self.client.post("/invoke/stream", json=self.request_payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])

        event_blocks = [block.strip() for block in response.text.split("\n\n") if block.strip()]
        self.assertGreaterEqual(len(event_blocks), 5)

        parsed_events = []
        for block in event_blocks:
            event_name = None
            data = None
            for line in block.splitlines():
                if line.startswith("event:"):
                    event_name = line[len("event:") :].strip()
                if line.startswith("data:"):
                    data = json.loads(line[len("data:") :].strip())
            parsed_events.append((event_name, data))

        self.assertEqual(parsed_events[0][0], "status")
        self.assertEqual(parsed_events[1][0], "message")
        self.assertEqual(parsed_events[2][0], "status")
        self.assertEqual(parsed_events[3][0], "process")
        self.assertEqual(parsed_events[4][0], "result")
        self.assertEqual(parsed_events[-1][0], "done")
        self.assertEqual(parsed_events[1][1]["text"], "正在帮你规划中")
        self.assertEqual(parsed_events[2][1]["phase"], "planning")
        self.assertEqual(parsed_events[3][1]["tool"], "plan_trip")
        self.assertEqual(parsed_events[3][1]["status"], "success")
        self.assertEqual(parsed_events[4][1]["itinerary"]["plans"][0]["title"], "亲子轻松版")
        self.assertTrue(parsed_events[-1][1]["success"])
        self.assertFalse(any(event_name == "message" and data["text"].startswith('{"tool"') for event_name, data in parsed_events if event_name == "message"))

        self.assertEqual(len(fake_agent.astream_calls), 1)
        called_payload, called_config, called_stream_mode, called_version = fake_agent.astream_calls[0]
        self.assertEqual(called_payload["messages"][0][1], "一家三口出去玩")
        self.assertEqual(called_config["configurable"]["thread_id"], "thread_test_001")
        self.assertEqual(called_stream_mode, ["messages", "updates", "custom"])
        self.assertEqual(called_version, "v2")

    def test_invoke_stream_returns_error_event_on_exception(self):
        """Test the SSE invoke endpoint emits an error event when streaming fails."""
        fake_agent = _FakeAgent(
            final_state=self.final_state,
            stream_events=[],
            stream_error=RuntimeError("stream failed"),
        )

        with (
            patch("main.AsyncSqliteSaver.from_conn_string", return_value=_FakeAsyncContextManager()),
            patch("main.build_agent_with_async_checkpointer", return_value=fake_agent),
        ):
            response = self.client.post("/invoke/stream", json=self.request_payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)
        self.assertIn("stream failed", response.text)


if __name__ == "__main__":
    unittest.main()
