import json
import os

def load_mock_data(filename: str) -> list[dict]:
    """
    加载 mock_db 目录下的 JSON 数据文件。
    
    Args:
        filename (str): 数据文件名，例如 "restaurants.json"
        
    Returns:
        list[dict]: 解析后的 JSON 列表数据
    """
    # 当前文件位于 backend/src/closedloop/utils/mock_db.py
    # 往上推 4 层得到项目根目录 (ClosedLoop)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    mock_db_dir = os.path.join(base_dir, "mock_db")
    file_path = os.path.join(mock_db_dir, filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Mock DB file not found: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
