import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.core.llm import build_agent
from closedloop.contracts.state import Constraints


class _DummyConfig:
    class _DeepSeek:
        API_KEY = "test"
        MODEL = "deepseek-chat"

    class _Qwen:
        API_KEY = "test"
        MODEL = "qwen-plus"

    deepseek = _DeepSeek()
    qwen = _Qwen()


class _DummyChatModel:
    def __init__(self, *, content: str | None = None, error: Exception | None = None):
        self._content = content
        self._error = error

    def invoke(self, _messages):
        if self._error:
            raise self._error
        return type("Obj", (), {"content": self._content})()


class TestBuildAgentStructuredOutput(unittest.TestCase):
    def test_build_agent_structured_output_parses_json(self):
        deepseek = _DummyChatModel(
            content="""```json
{
  "group_type": "friends",
  "adult_count": 2,
  "child_count": 0,
  "child_profiles": [],
  "budget": 500,
  "dietary_restrictions": [],
  "preferred_distance": "2km-5km",
  "time_period": "14:00",
  "duration_hours": [5, 5],
  "activity_preferences": []
}
```"""
        )
        qwen = _DummyChatModel(content="{}")

        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", return_value=deepseek), patch(
            "closedloop.core.llm.ChatTongyi", return_value=qwen
        ), patch(
            "closedloop.core.llm.create_agent", side_effect=AssertionError("create_agent should not be called")
        ):
            agent = build_agent(response_format=Constraints)
            out = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})

        self.assertIsInstance(out, dict)
        self.assertIn("structured_response", out)
        self.assertTrue(hasattr(out["structured_response"], "model_dump") or hasattr(out["structured_response"], "dict"))

    def test_build_agent_structured_output_fallback_to_qwen(self):
        deepseek = _DummyChatModel(error=RuntimeError("boom"))
        qwen = _DummyChatModel(
            content='{"group_type":"friends","adult_count":2,"child_count":0,"child_profiles":[],"budget":300,"dietary_restrictions":[],"preferred_distance":"2km-5km","time_period":"14:00","duration_hours":[5,5],"activity_preferences":[]}'
        )

        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", return_value=deepseek), patch(
            "closedloop.core.llm.ChatTongyi", return_value=qwen
        ), patch(
            "closedloop.core.llm.create_agent", side_effect=AssertionError("create_agent should not be called")
        ):
            agent = build_agent(response_format=Constraints)
            out = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})

        self.assertIn("structured_response", out)


if __name__ == "__main__":
    unittest.main()
