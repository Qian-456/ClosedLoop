import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import closedloop.core.llm as llm_module
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


class _VariantConfig:
    def __init__(self, *, deepseek_model="deepseek-chat", qwen_model="qwen-plus"):
        class _DeepSeek:
            API_KEY = "test"
            MODEL = deepseek_model

        class _Qwen:
            API_KEY = "test"
            MODEL = qwen_model

        self.deepseek = _DeepSeek()
        self.qwen = _Qwen()


class _DummyChatModel:
    def __init__(self, *, content: str | None = None, error: Exception | None = None):
        self._content = content
        self._error = error

    def invoke(self, _messages):
        if self._error:
            raise self._error
        return type("Obj", (), {"content": self._content})()


class _TrackingChatModel:
    created = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).created += 1

    def invoke(self, _messages):
        return type("Obj", (), {"content": "{}"})()


class _BrokenChatModel:
    def __init__(self, **_kwargs):
        raise RuntimeError("constructor boom")


class _SequenceChatModel:
    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, _messages):
        if not self._responses:
            raise AssertionError("no more responses configured")

        current = self._responses.pop(0)
        if isinstance(current, Exception):
            raise current
        return type("Obj", (), {"content": current})()


class TestBuildAgentStructuredOutput(unittest.TestCase):
    def setUp(self):
        llm_module.clear_model_client_cache()
        if hasattr(llm_module, "clear_agent_cache"):
            llm_module.clear_agent_cache()
        _TrackingChatModel.created = 0

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

    def test_build_agent_reuses_cached_model_clients_when_config_is_same(self):
        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_TrackingChatModel), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ), patch("closedloop.core.llm.create_agent", side_effect=lambda **kwargs: kwargs):
            first = build_agent()
            second = build_agent()

        self.assertIs(first["model"], second["model"])
        self.assertEqual(_TrackingChatModel.created, 2)
        self.assertEqual(llm_module.get_model_client_cache_size(), 2)

    def test_build_agent_reuses_cached_agent_instance_when_args_are_same(self):
        created_agents = []

        def _fake_create_agent(**kwargs):
            agent = {"model": kwargs["model"], "middleware": kwargs["middleware"], "tools": kwargs["tools"]}
            created_agents.append(agent)
            return agent

        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_TrackingChatModel), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ), patch("closedloop.core.llm.create_agent", side_effect=_fake_create_agent):
            first = build_agent()
            second = build_agent()

        self.assertIs(first, second)
        self.assertEqual(len(created_agents), 1)
        self.assertEqual(_TrackingChatModel.created, 2)

    def test_build_agent_reuses_cached_structured_agent_when_response_format_matches(self):
        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_TrackingChatModel), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ), patch(
            "closedloop.core.llm.create_agent", side_effect=AssertionError("create_agent should not be called")
        ):
            first = build_agent(response_format=Constraints)
            second = build_agent(response_format=Constraints)

        self.assertIs(first, second)
        self.assertEqual(_TrackingChatModel.created, 2)

    def test_build_agent_rebuilds_cached_model_when_model_config_changes(self):
        first_config = _VariantConfig(deepseek_model="deepseek-chat", qwen_model="qwen-plus")
        second_config = _VariantConfig(deepseek_model="deepseek-reasoner", qwen_model="qwen-turbo")

        with patch("closedloop.core.llm.get_config", side_effect=[first_config, second_config]), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_TrackingChatModel), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ), patch("closedloop.core.llm.create_agent", side_effect=lambda **kwargs: kwargs):
            first = build_agent()
            second = build_agent()

        self.assertIsNot(first["model"], second["model"])
        self.assertEqual(_TrackingChatModel.created, 4)
        self.assertEqual(llm_module.get_model_client_cache_size(), 4)

    def test_build_agent_keeps_cache_empty_when_constructor_raises(self):
        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_BrokenChatModel), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ):
            with self.assertRaises(RuntimeError):
                build_agent()

        self.assertEqual(llm_module.get_model_client_cache_size(), 0)

    def test_build_agent_evicts_bad_cached_client_after_invoke_exception(self):
        """Ensure invoke errors evict the broken cached primary model."""
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
        self.assertEqual(llm_module.get_model_client_cache_size(), 1)
        self.assertEqual(llm_module.get_agent_cache_size(), 0)

    def test_build_agent_rebuilds_structured_agent_after_primary_invoke_exception(self):
        """Ensure a structured agent is rebuilt after invoke failure evicts its primary dependency."""

        deepseek_instances = [
            _SequenceChatModel([RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")]),
            _SequenceChatModel(
                [
                    '{"group_type":"friends","adult_count":2,"child_count":0,"child_profiles":[],"budget":260,"dietary_restrictions":[],"preferred_distance":"2km-5km","time_period":"14:00","duration_hours":[5,5],"activity_preferences":[]}'
                ]
            ),
        ]
        qwen = _DummyChatModel(
            content='{"group_type":"friends","adult_count":2,"child_count":0,"child_profiles":[],"budget":300,"dietary_restrictions":[],"preferred_distance":"2km-5km","time_period":"14:00","duration_hours":[5,5],"activity_preferences":[]}'
        )

        with patch("closedloop.core.llm.time.sleep"), patch(
            "closedloop.core.llm.get_config", return_value=_DummyConfig()
        ), patch("closedloop.core.llm.LoggerManager.setup"), patch(
            "closedloop.core.llm.ChatDeepSeek", side_effect=deepseek_instances
        ) as deepseek_factory, patch(
            "closedloop.core.llm.ChatTongyi", return_value=qwen
        ), patch(
            "closedloop.core.llm.create_agent", side_effect=AssertionError("create_agent should not be called")
        ):
            first_agent = build_agent(response_format=Constraints)
            first_out = first_agent.invoke({"messages": [{"role": "user", "content": "hi"}]})

            self.assertIn("structured_response", first_out)
            self.assertEqual(llm_module.get_model_client_cache_size(), 1)
            self.assertEqual(llm_module.get_agent_cache_size(), 0)

            rebuilt_agent = build_agent(response_format=Constraints)
            rebuilt_out = rebuilt_agent.invoke({"messages": [{"role": "user", "content": "hi again"}]})

        self.assertIsNot(first_agent, rebuilt_agent)
        self.assertEqual(deepseek_factory.call_count, 2)
        self.assertEqual(llm_module.get_model_client_cache_size(), 2)
        self.assertEqual(llm_module.get_agent_cache_size(), 1)
        self.assertEqual(rebuilt_out["structured_response"].budget, 260.0)

    def test_build_agent_rebuilds_model_client_after_constructor_exception(self):
        """Ensure the next build recreates model clients after a constructor failure."""

        call_state = {"deepseek": 0}

        def _deepseek_factory(**kwargs):
            call_state["deepseek"] += 1
            if call_state["deepseek"] == 1:
                raise RuntimeError("constructor boom")
            return _TrackingChatModel(**kwargs)

        with patch("closedloop.core.llm.get_config", return_value=_DummyConfig()), patch(
            "closedloop.core.llm.LoggerManager.setup"
        ), patch("closedloop.core.llm.ChatDeepSeek", side_effect=_deepseek_factory), patch(
            "closedloop.core.llm.ChatTongyi", side_effect=_TrackingChatModel
        ), patch("closedloop.core.llm.create_agent", side_effect=lambda **kwargs: kwargs):
            with self.assertRaises(RuntimeError):
                build_agent()

            rebuilt_agent = build_agent()

        self.assertIsInstance(rebuilt_agent, dict)
        self.assertEqual(call_state["deepseek"], 2)
        self.assertEqual(_TrackingChatModel.created, 2)
        self.assertEqual(llm_module.get_model_client_cache_size(), 2)
        self.assertEqual(llm_module.get_agent_cache_size(), 1)


if __name__ == "__main__":
    unittest.main()
