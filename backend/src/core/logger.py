import sys
from loguru import logger


class LoggerManager:
    _initialized = False

    @classmethod
    def setup(cls, config):
        if cls._initialized:
            return

        logger.remove()

        logger.add(
            sys.stdout,
            format="{time} | {level} | {message}",
            level=config.logging.LOG_LEVEL,
        )

        logger.add(
            f"{config.logging.LOG_DIR}/app.log",
            rotation=config.logging.LOG_ROTATION,
            retention=config.logging.LOG_RETENTION,
        )

        cls._initialized = True

        logger.info("Logger initialized")


# 暴露全局 logger
__all__ = ["LoggerManager", "logger"]