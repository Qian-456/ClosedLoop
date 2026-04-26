from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_deepseek import ChatDeepSeek
from langchain_community.chat_models import ChatTongyi

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger


def build_agent(*, tools: list | None = None, temperature: float = 0.7, response_format=None):
    """Create a standard agent with fallback + retry.

    This is the ONLY allowed way to initialize LLM in this project.
    """

    # 1. load config
    config = get_config()

    # 2. setup logging (idempotent)
    LoggerManager.setup(config)

    # 3. init models
    # Check if API keys are None and throw a clear error to help debugging
    if not config.deepseek.API_KEY:
        logger.error("DEEPSEEK_API_KEY is missing from configuration")
        raise ValueError("DEEPSEEK_API_KEY must be set in .env")
        
    if not config.qwen.API_KEY:
        logger.error("DASHSCOPE_API_KEY is missing from configuration")
        raise ValueError("DASHSCOPE_API_KEY must be set in .env")

    deepseek = ChatDeepSeek(
        model=config.deepseek.MODEL,
        api_key=config.deepseek.API_KEY,
        temperature=temperature
    )

    qwen = ChatTongyi(
        model=config.qwen.MODEL,
        api_key=config.qwen.API_KEY,
        temperature=temperature,
    )

    logger.info("LLM initialized | primary=DeepSeek | fallback=Qwen")

    # 4. create agent
    agent_kwargs = {
        "model": deepseek,
        "tools": tools or [],
        "middleware": [
            ModelFallbackMiddleware(qwen),
            ModelRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                on_failure="error",
            ),
        ],
    }

    if response_format is not None:
        agent_kwargs["response_format"] = response_format

    agent = create_agent(**agent_kwargs)

    return agent