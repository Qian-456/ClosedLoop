import json
import os

from closedloop.core.config import REPO_ROOT_DIR, get_config

def load_mock_data(filename: str) -> list[dict]:
    """
    加载 mock_db 目录下的 JSON 数据文件。
    
    Args:
        filename (str): 数据文件名，例如 "restaurants.json"
        
    Returns:
        list[dict]: 解析后的 JSON 列表数据
    """
    config = get_config()

    def _resolve_dir(v: str) -> str:
        if not v:
            return ""
        if os.path.isabs(v):
            return os.path.abspath(v)
        return os.path.abspath(os.path.join(REPO_ROOT_DIR, v))

    repo_dir = _resolve_dir(config.data.MOCK_DB_REPO_DIR)
    file_path = os.path.join(repo_dir, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Mock DB file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Mock DB file must be a list: {file_path}")
    return data
