import json
import time
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_deepseek import ChatDeepSeek
from langchain_community.chat_models import ChatTongyi

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger


def _extract_json_object(text: str) -> str:
    """
    从模型输出文本中提取 JSON 对象。

    该函数用于避免依赖 tool calling 的结构化输出流程：当 tool_call 消息未被完整回显到
    provider 时，这类流程可能失败。这里改为从纯文本中截取并解析 JSON。
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

    left = cleaned.find("{")
    right = cleaned.rfind("}")
    if left == -1 or right == -1 or right <= left:
        raise ValueError("Model output does not contain a JSON object.")
    return cleaned[left : right + 1]


def _coerce_structured_response(schema: Any, data: Any) -> Any:
    """
    当 schema 为 Pydantic 模型类时，将原始数据强制转换为结构化响应实例。
    """
    if schema is None:
        return data
    if hasattr(schema, "model_validate"):
        return schema.model_validate(data)
    if hasattr(schema, "parse_obj"):
        return schema.parse_obj(data)
    return data


class _StructuredOutputAgent:
    def __init__(
        self,
        *,
        primary_model: Any,
        fallback_model: Any,
        response_format: Any,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
    ):
        """一个最小的 Agent 适配器：在不使用 tool calling 的情况下提供结构化输出。"""
        self._primary_model = primary_model
        self._fallback_model = fallback_model
        self._response_format = response_format
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._initial_delay = initial_delay

    def _invoke_with_retries(self, model: Any, messages: Any, *, provider: str) -> Any:
        last_error: Exception | None = None
        delay = self._initial_delay
        for attempt in range(1, self._max_retries + 1):
            try:
                return model.invoke(messages)
            except Exception as exc:
                last_error = exc
                logger.error(
                    f"phase=llm_invoke | provider={provider} | attempt={attempt} | error={exc}"
                )
                if attempt < self._max_retries:
                    time.sleep(delay)
                    delay *= self._backoff_factor
        raise last_error or RuntimeError("LLM invocation failed")

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])

        try:
            raw = self._invoke_with_retries(self._primary_model, messages, provider="deepseek")
        except Exception as exc:
            logger.error(f"phase=llm_invoke | provider=deepseek | fallback=qwen | error={exc}")
            raw = self._invoke_with_retries(self._fallback_model, messages, provider="qwen")

        content = raw
        if hasattr(raw, "content"):
            content = raw.content
        if not isinstance(content, str):
            raise ValueError("Model output content must be a string for structured parsing.")

        json_text = _extract_json_object(content)
        data = json.loads(json_text)
        structured = _coerce_structured_response(self._response_format, data)
        return {"structured_response": structured}


def build_agent(
    *,
    tools: list | None = None,
    temperature: float = 0.7,
    response_format=None,
    state_schema: Any = None,
    middleware: list | None = None,
    checkpointer: Any = None,
):
    """创建带有回退机制（fallback）和重试机制（retry）的标准 agent。

    这是本项目中初始化 LLM 的唯一允许方式。
    """

    # 1. 加载 Config
    config = get_config()

    # 2. 设置日志（幂等操作）
    LoggerManager.setup(config)

    # 3. 初始化模型
    # 检查 API key 是否为空，抛出明确的错误以帮助调试
    if not config.deepseek.API_KEY:
        logger.error("DEEPSEEK_API_KEY is missing from configuration")
        raise ValueError("DEEPSEEK_API_KEY must be set in .env")
        
    if not config.qwen.API_KEY:
        logger.error("DASHSCOPE_API_KEY is missing from configuration")
        raise ValueError("DASHSCOPE_API_KEY must be set in .env")

    deepseek = ChatDeepSeek(
        model=config.deepseek.MODEL,
        api_key=config.deepseek.API_KEY,
        temperature=temperature,
        timeout=15.0
    )

    qwen = ChatTongyi(
        model=config.qwen.MODEL,
        api_key=config.qwen.API_KEY,
        temperature=temperature,
        timeout=15.0
    )

    logger.info("LLM initialized | primary=DeepSeek | fallback=Qwen")

    if response_format is not None:
        return _StructuredOutputAgent(
            primary_model=deepseek,
            fallback_model=qwen,
            response_format=response_format,
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
        )

    # 4. create agent
    merged_middleware = [
        ModelFallbackMiddleware(qwen),
        ModelRetryMiddleware(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            on_failure="error",
        ),
    ]
    if middleware:
        merged_middleware.extend(middleware)

    agent_kwargs = {
        "model": deepseek,
        "tools": tools or [],
        "middleware": merged_middleware,
    }

    if state_schema is not None:
        agent_kwargs["state_schema"] = state_schema
        
    if checkpointer is not None:
        agent_kwargs["checkpointer"] = checkpointer

    agent = create_agent(**agent_kwargs)

    return agent
