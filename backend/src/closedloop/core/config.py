import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv

# 确定 backend/src 目录的绝对路径
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# 指向 backend/.env
ENV_FILE_PATH = os.path.abspath(os.path.join(SRC_DIR, "..", ".env"))
LOG_DIR_PATH = os.path.join(SRC_DIR, "logs")

# 强制将环境变量从 .env 文件加载到 os.environ 中
load_dotenv(ENV_FILE_PATH)

class LoggingSettings(BaseSettings):
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_DIR: str = LOG_DIR_PATH
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "30 days"

class DeepSeekSettings(BaseSettings):
    API_KEY: Optional[str] = Field(default=None)
    MODEL: str = "deepseek-chat"
    
    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_")

class QwenSettings(BaseSettings):
    API_KEY: Optional[str] = Field(default=None)
    MODEL: str = "qwen-plus"
    
    model_config = SettingsConfigDict(env_prefix="DASHSCOPE_")

class AppConfig(BaseSettings):
    PROJECT_NAME: str = "ClosedLoop"

    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    deepseek: DeepSeekSettings = Field(default_factory=DeepSeekSettings)
    qwen: QwenSettings = Field(default_factory=QwenSettings)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_config() -> AppConfig:
    """Return cached config"""
    # Load AppConfig, which in turn initializes its fields.
    # However, since nested settings might not automatically pick up root .env vars,
    # we initialize them explicitly reading from the environment which is populated by dotenv.
    return AppConfig(
        logging=LoggingSettings(),
        deepseek=DeepSeekSettings(),
        qwen=QwenSettings()
    )