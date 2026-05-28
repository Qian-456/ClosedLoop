import json
import os
import copy

from closedloop.core.config import REPO_ROOT_DIR, get_config

_MOCK_DB_CACHE: dict[str, tuple[float, list[dict]]] = {}

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

    file_mtime = os.path.getmtime(file_path)
    cached = _MOCK_DB_CACHE.get(file_path)
    if cached and cached[0] == file_mtime:
        return copy.deepcopy(cached[1])

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Mock DB file must be a list: {file_path}")
    _MOCK_DB_CACHE[file_path] = (file_mtime, data)
    return copy.deepcopy(data)
