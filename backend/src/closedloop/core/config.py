import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv

# 确定 backend/src 目录的绝对路径
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# 仓库根目录 (ClosedLoop)
REPO_ROOT_DIR = os.path.abspath(os.path.join(SRC_DIR, "..", ".."))
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
    LOG_ELK_ENABLED: bool = False
    LOG_ELK_JSON_PATH: str = os.path.join(LOG_DIR_PATH, "elk", "elk_{time:YYYY-MM-DD}.jsonl")
    LOG_ELK_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"
    FILTER_LOG_DETAILED_DEBUG: bool = True
    LOG_PLANNER_STATS: bool = False
    PLANNER_LOG_DETAILED_DEBUG: bool = False

class DeepSeekSettings(BaseSettings):
    API_KEY: Optional[str] = Field(default=None)
    MODEL: str = "deepseek-chat"
    
    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_")

class QwenSettings(BaseSettings):
    API_KEY: Optional[str] = Field(default=None)
    MODEL: str = "qwen-plus"
    
    model_config = SettingsConfigDict(env_prefix="DASHSCOPE_")

class DataSettings(BaseSettings):
    MOCK_DB_REPO_DIR: str = os.path.join(REPO_ROOT_DIR, "mock_data", "base")
    MOCK_DB_RW_DIR: str = os.path.join(REPO_ROOT_DIR, "mock_data", "runtime")

class AppConfig(BaseSettings):
    PROJECT_NAME: str = "ClosedLoop"
    MILVUS_URI: str = "http://localhost:19530"
    PLAN_SUB_API_URL: str = "http://localhost:8001/plan"
    SEARCH_SUB_API_URL: str = "http://127.0.0.1:8002/search"
    PLAN_SUB_NETWORK_MODE: Literal["local", "docker"] = "local"
    FORCE_REBUILD_VECTORS: bool = False

    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    deepseek: DeepSeekSettings = Field(default_factory=DeepSeekSettings)
    qwen: QwenSettings = Field(default_factory=QwenSettings)
    data: DataSettings = Field(default_factory=DataSettings)

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
        qwen=QwenSettings(),
        data=DataSettings(),
    )
