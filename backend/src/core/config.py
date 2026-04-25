from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_DIR: str = "logs"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "30 days"


class DeepSeekSettings(BaseSettings):
    API_KEY: Optional[str] = None
    MODEL: str = "deepseek-chat"


class QwenSettings(BaseSettings):
    API_KEY: Optional[str] = None
    MODEL: str = "qwen-plus"


class AppConfig(BaseSettings):
    PROJECT_NAME: str = "ClosedLoop"

    logging: LoggingSettings = LoggingSettings()
    deepseek: DeepSeekSettings = DeepSeekSettings()
    qwen: QwenSettings = QwenSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_config() -> AppConfig:
    """Return cached config"""
    return AppConfig()