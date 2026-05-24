import os
import sys
from loguru import logger

from closedloop.core.config import REPO_ROOT_DIR, SRC_DIR


def _resolve_logging_path(path_value: str) -> str:
    """Resolve a logging path deterministically, independent of current working directory."""
    if not path_value:
        return path_value

    normalized = os.path.normpath(str(path_value))
    if os.path.isabs(normalized):
        return normalized

    prefix = os.path.normpath(os.path.join("backend", "src"))
    if normalized.split(os.sep)[:2] == prefix.split(os.sep)[:2]:
        return os.path.abspath(os.path.join(REPO_ROOT_DIR, normalized))

    return os.path.abspath(os.path.join(SRC_DIR, normalized))


class LoggerManager:
    _initialized = False

    @classmethod
    def setup(cls, config):
        if cls._initialized:
            return

        logger.remove()

        log_dir = _resolve_logging_path(getattr(config.logging, "LOG_DIR", ""))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        logger.add(
            sys.stdout,
            format="{time} | {level} | {message}",
            level=config.logging.LOG_LEVEL,
        )

        logger.add(
            os.path.join(log_dir, "app.log"),
            rotation=config.logging.LOG_ROTATION,
            retention=config.logging.LOG_RETENTION,
            level=config.logging.LOG_LEVEL,
        )

        if getattr(config.logging, "LOG_ELK_ENABLED", False):
            elk_path = getattr(config.logging, "LOG_ELK_JSON_PATH", None)
            if elk_path:
                elk_path = _resolve_logging_path(elk_path)
                elk_dir = os.path.dirname(elk_path)
                if elk_dir:
                    os.makedirs(elk_dir, exist_ok=True)

                logger.add(
                    elk_path,
                    rotation=config.logging.LOG_ROTATION,
                    retention=config.logging.LOG_RETENTION,
                    level=getattr(config.logging, "LOG_ELK_LEVEL", "DEBUG"),
                    serialize=True,
                )

        logger.add(
            os.path.join(log_dir, "error.log"),
            rotation=config.logging.LOG_ROTATION,
            retention=config.logging.LOG_RETENTION,
            level="ERROR",
        )

        # 专门针对 planner_subgraph 相关的模块设置单独的日志输出 (普通日志)
        logger.add(
            os.path.join(log_dir, "planner_subgraph.log"),
            rotation=config.logging.LOG_ROTATION,
            retention=config.logging.LOG_RETENTION,
            level=config.logging.LOG_LEVEL,
            filter=lambda record: "planner_subgraph" in record["name"] or "phase=planner_" in record["message"] or "phase=rerank_" in record["message"] or "phase=filter_" in record["message"] or "phase=retrieve_" in record["message"],
        )

        # 专门针对 planner_subgraph 相关的模块设置单独的错误日志输出
        logger.add(
            os.path.join(log_dir, "planner_subgraph_error.log"),
            rotation=config.logging.LOG_ROTATION,
            retention=config.logging.LOG_RETENTION,
            level="ERROR",
            filter=lambda record: "planner_subgraph" in record["name"] or "phase=planner_" in record["message"] or "phase=rerank_" in record["message"] or "phase=filter_" in record["message"] or "phase=retrieve_" in record["message"],
        )

        cls._initialized = True

        logger.info("Logger initialized")


# 暴露全局 logger
__all__ = ["LoggerManager", "logger"]
