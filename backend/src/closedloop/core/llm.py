import json
import threading
import time
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware, HumanInTheLoopMiddleware, ToolCallLimitMiddleware
from langchain_deepseek import ChatDeepSeek
from langchain_community.chat_models import ChatTongyi

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger

_DEFAULT_MODEL_TIMEOUT = 15.0
_MODEL_CLIENT_CACHE: dict[tuple[str, str, float, float], Any] = {}
_MODEL_CLIENT_CACHE_LOCK = threading.RLock()
_AGENT_CACHE: dict[tuple[Any, ...], Any] = {}
_AGENT_CACHE_DEPENDENCIES: dict[tuple[Any, ...], tuple[tuple[str, str, float, float], ...]] = {}
_AGENT_CACHE_LOCK = threading.RLock()


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


def _build_model_cache_key(
    *,
    provider: str,
    model: str,
    temperature: float,
    timeout: float,
) -> tuple[str, str, float, float]:
    """Build a stable in-process cache key for a chat model client."""
    return (provider, model, float(temperature), float(timeout))


def clear_model_client_cache() -> None:
    """Clear all cached chat model clients in the current process."""
    with _MODEL_CLIENT_CACHE_LOCK:
        _MODEL_CLIENT_CACHE.clear()


def get_model_client_cache_size() -> int:
    """Return the number of cached chat model clients in the current process."""
    with _MODEL_CLIENT_CACHE_LOCK:
        return len(_MODEL_CLIENT_CACHE)


def clear_agent_cache() -> None:
    """Clear all cached agent instances in the current process."""
    with _AGENT_CACHE_LOCK:
        _AGENT_CACHE.clear()
        _AGENT_CACHE_DEPENDENCIES.clear()


def get_agent_cache_size() -> int:
    """Return the number of cached agent instances in the current process."""
    with _AGENT_CACHE_LOCK:
        return len(_AGENT_CACHE)


def _freeze_cache_value(value: Any) -> Any:
    """Convert cache inputs into stable, hashable values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, type):
        return ("type", value.__module__, value.__qualname__)

    if isinstance(value, (list, tuple)):
        return tuple(_freeze_cache_value(item) for item in value)

    if isinstance(value, dict):
        return tuple(
            sorted((str(key), _freeze_cache_value(item_value)) for key, item_value in value.items())
        )

    if hasattr(value, "__module__") and hasattr(value, "__qualname__"):
        return ("symbol", value.__module__, value.__qualname__)

    return ("instance", value.__class__.__module__, value.__class__.__qualname__, id(value))


def _build_agent_cache_key(
    *,
    agent_kind: str,
    primary_cache_key: tuple[str, str, float, float],
    fallback_cache_key: tuple[str, str, float, float],
    tools: list | None,
    response_format: Any,
    state_schema: Any,
    middleware: list | None,
    checkpointer: Any,
) -> tuple[Any, ...]:
    """Build a stable cache key for a configured agent instance."""
    return (
        agent_kind,
        primary_cache_key,
        fallback_cache_key,
        _freeze_cache_value(tools or []),
        _freeze_cache_value(response_format),
        _freeze_cache_value(state_schema),
        _freeze_cache_value(middleware or []),
        _freeze_cache_value(checkpointer),
    )


def _get_cached_agent(cache_key: tuple[Any, ...]) -> Any | None:
    """Load a cached agent instance by cache key."""
    with _AGENT_CACHE_LOCK:
        return _AGENT_CACHE.get(cache_key)


def _store_cached_agent(
    cache_key: tuple[Any, ...],
    agent: Any,
    *,
    dependencies: tuple[tuple[str, str, float, float], ...],
) -> Any:
    """Store a newly created agent instance and its model dependencies."""
    with _AGENT_CACHE_LOCK:
        _AGENT_CACHE[cache_key] = agent
        _AGENT_CACHE_DEPENDENCIES[cache_key] = dependencies
    logger.info(f"phase=agent_cache | action=store | key={cache_key}")
    return agent


def _evict_agent_cache(cache_key: tuple[Any, ...], *, reason: str) -> None:
    """Remove a cached agent instance when it becomes unsafe to reuse."""
    with _AGENT_CACHE_LOCK:
        removed = _AGENT_CACHE.pop(cache_key, None)
        _AGENT_CACHE_DEPENDENCIES.pop(cache_key, None)

    if removed is not None:
        logger.warning(f"phase=agent_cache | action=evict | key={cache_key} | reason={reason}")


def _evict_agents_by_model_cache_key(
    model_cache_key: tuple[str, str, float, float],
    *,
    reason: str,
) -> None:
    """Evict agent instances that depend on a removed model client."""
    with _AGENT_CACHE_LOCK:
        affected_keys = [
            cache_key
            for cache_key, dependencies in _AGENT_CACHE_DEPENDENCIES.items()
            if model_cache_key in dependencies
        ]

    for cache_key in affected_keys:
        _evict_agent_cache(cache_key, reason=reason)


def _evict_model_client(cache_key: tuple[str, str, float, float], *, reason: str) -> None:
    """Remove a cached model client when it becomes unsafe to reuse."""
    with _MODEL_CLIENT_CACHE_LOCK:
        removed = _MODEL_CLIENT_CACHE.pop(cache_key, None)

    if removed is not None:
        logger.warning(f"phase=llm_cache | action=evict | key={cache_key} | reason={reason}")
        _evict_agents_by_model_cache_key(cache_key, reason=f"model_dependency:{reason}")


def _get_or_create_model_client(
    *,
    provider: str,
    model: str,
    temperature: float,
    timeout: float,
    factory: Any,
    **factory_kwargs,
) -> tuple[Any, tuple[str, str, float, float]]:
    """Get a cached model client or create and cache a new one on miss."""
    cache_key = _build_model_cache_key(
        provider=provider,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )

    with _MODEL_CLIENT_CACHE_LOCK:
        cached = _MODEL_CLIENT_CACHE.get(cache_key)

    if cached is not None:
        logger.info(f"phase=llm_cache | action=hit | key={cache_key}")
        return cached, cache_key

    logger.info(f"phase=llm_cache | action=miss | key={cache_key}")
    try:
        client = factory(
            model=model,
            temperature=temperature,
            timeout=timeout,
            **factory_kwargs,
        )
    except Exception as exc:
        logger.error(f"phase=llm_cache | action=create_error | key={cache_key} | error={exc}")
        _evict_model_client(cache_key, reason="constructor_error")
        raise

    with _MODEL_CLIENT_CACHE_LOCK:
        _MODEL_CLIENT_CACHE[cache_key] = client

    logger.info(f"phase=llm_cache | action=store | key={cache_key}")
    return client, cache_key


class _StructuredOutputAgent:
    def __init__(
        self,
        *,
        primary_model: Any,
        fallback_model: Any,
        primary_cache_key: tuple[str, str, float, float],
        fallback_cache_key: tuple[str, str, float, float],
        response_format: Any,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
    ):
        """Provide structured output without relying on tool-calling support."""
        self._primary_model = primary_model
        self._fallback_model = fallback_model
        self._primary_cache_key = primary_cache_key
        self._fallback_cache_key = fallback_cache_key
        self._response_format = response_format
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._initial_delay = initial_delay

    def _invoke_with_retries(
        self,
        model: Any,
        messages: Any,
        *,
        provider: str,
        cache_key: tuple[str, str, float, float],
    ) -> Any:
        last_error: Exception | None = None
        delay = self._initial_delay
        for attempt in range(1, self._max_retries + 1):
            try:
                return model.invoke(messages)
            except Exception as exc:
                last_error = exc
                _evict_model_client(cache_key, reason=f"invoke_error:{provider}")
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
            raw = self._invoke_with_retries(
                self._primary_model,
                messages,
                provider="deepseek",
                cache_key=self._primary_cache_key,
            )
        except Exception as exc:
            logger.error(f"phase=llm_invoke | provider=deepseek | fallback=qwen | error={exc}")
            raw = self._invoke_with_retries(
                self._fallback_model,
                messages,
                provider="qwen",
                cache_key=self._fallback_cache_key,
            )

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

    timeout = _DEFAULT_MODEL_TIMEOUT

    deepseek, deepseek_cache_key = _get_or_create_model_client(
        provider="deepseek",
        model=config.deepseek.MODEL,
        temperature=temperature,
        timeout=timeout,
        factory=ChatDeepSeek,
        api_key=config.deepseek.API_KEY,
    )

    qwen, qwen_cache_key = _get_or_create_model_client(
        provider="qwen",
        model=config.qwen.MODEL,
        temperature=temperature,
        timeout=timeout,
        factory=ChatTongyi,
        api_key=config.qwen.API_KEY,
    )

    logger.info("LLM initialized | primary=DeepSeek | fallback=Qwen")

    agent_kind = "structured" if response_format is not None else "standard"
    agent_cache_key = _build_agent_cache_key(
        agent_kind=agent_kind,
        primary_cache_key=deepseek_cache_key,
        fallback_cache_key=qwen_cache_key,
        tools=tools,
        response_format=response_format,
        state_schema=state_schema,
        middleware=middleware,
        checkpointer=checkpointer,
    )
    cached_agent = _get_cached_agent(agent_cache_key)
    if cached_agent is not None:
        logger.info(f"phase=agent_cache | action=hit | key={agent_cache_key}")
        return cached_agent

    logger.info(f"phase=agent_cache | action=miss | key={agent_cache_key}")

    if response_format is not None:
        return _store_cached_agent(
            agent_cache_key,
            _StructuredOutputAgent(
            primary_model=deepseek,
            fallback_model=qwen,
            primary_cache_key=deepseek_cache_key,
            fallback_cache_key=qwen_cache_key,
            response_format=response_format,
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=1.0,
            ),
            dependencies=(deepseek_cache_key, qwen_cache_key),
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
        ToolCallLimitMiddleware(thread_limit=20, run_limit=3),
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

    return _store_cached_agent(
        agent_cache_key,
        agent,
        dependencies=(deepseek_cache_key, qwen_cache_key),
    )
