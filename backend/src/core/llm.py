from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_deepseek import ChatDeepSeek
from langchain_community.chat_models import ChatTongyi

from core.config import get_config
from core.logger import LoggerManager, logger


def build_agent(*, tools: list | None = None):
    """Create a standard agent with fallback + retry.

    This is the ONLY allowed way to initialize LLM in this project.
    """

    # 1. load config
    config = get_config()

    # 2. setup logging (idempotent)
    LoggerManager.setup(
        log_dir=config.logging.LOG_DIR,
        level=config.logging.LOG_LEVEL,
        rotation=config.logging.LOG_ROTATION,
        retention=config.logging.LOG_RETENTION,
    )

    # 3. init models
    deepseek = ChatDeepSeek(
        model=config.deepseek.MODEL,
        api_key=config.deepseek.API_KEY,
    )

    qwen = ChatTongyi(
        model=config.dashscope.MODEL,
        api_key=config.dashscope.API_KEY,
    )

    logger.info("LLM initialized | primary=DeepSeek | fallback=Qwen")

    # 4. create agent
    agent = create_agent(
        model=deepseek,
        tools=tools or [],
        middleware=[
            ModelFallbackMiddleware(qwen),
            ModelRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                on_failure="error",
            ),
        ],
    )

    return agent