import json
import os
import sys

# 添加 backend/src 到 sys.path 以便能够导入 closedloop 的包
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# 我们把需要测试的 adjust_tool 中那段提取 new_item_data 的代码摘出来跑一遍
def test_find_item_in_mock_data(new_item_id: str):
    new_item_data = None
    
    # 模拟 adjust_tool.py 第 66 行左右的路径计算
    # 在这个测试脚本里，__file__ 是 test_adjust_fallback.py
    # 它位于 backend/src/tests/
    # 我们要指向 mock_data/base/
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../mock_data/base"))
    
    print(f"尝试读取的 mock_data 基础路径: {base_dir}")
    print(f"路径是否存在: {os.path.exists(base_dir)}")
    
    db_files = {
        "restaurants.json": ["combos"],
        "activities.json": ["packages"],
        "add_ons.json": ["gifts"]
    }
    
    for file_name, sub_keys in db_files.items():
        file_path = os.path.join(base_dir, file_name)
        if not os.path.exists(file_path):
            print(f"找不到文件: {file_path}")
            continue
            
        print(f"正在扫描: {file_name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                mock_data = json.load(f)
                
            for parent_item in mock_data:
                if str(parent_item.get("id")) == new_item_id:
                    new_item_data = parent_item
                    print(f"[SUCCESS] 在 {file_name} 找到父级 ID: {new_item_id}")
                    break
                    
                for sub_key in sub_keys:
                    for child_item in parent_item.get(sub_key, []):
                        child_id = str(child_item.get("combo_id") or child_item.get("package_id") or child_item.get("gift_id") or child_item.get("id"))
                        if child_id == new_item_id:
                            print(f"[SUCCESS] 在 {file_name} 找到子级 ID: {new_item_id} (属于父级: {parent_item.get('name')})")
                            child_item["parent_id"] = parent_item.get("id")
                            child_item["name"] = parent_item.get("name", "") + " - " + child_item.get("name", "")
                            child_item["latitude"] = parent_item.get("latitude")
                            child_item["longitude"] = parent_item.get("longitude")
                            new_item_data = child_item
                            break
                    if new_item_data:
                        break
                if new_item_data:
                    break
            if new_item_data:
                break
        except Exception as e:
            print(f"读取或解析 {file_name} 时发生错误: {e}")
            
    if new_item_data:
        print("\n最终拿到的完整数据对象：")
        print(json.dumps(new_item_data, indent=2, ensure_ascii=False)[:500] + "\n... (已截断)")
    else:
        print(f"\n[FAILED] 在所有的 JSON 库中都没有找到 ID 为 {new_item_id} 的数据！")

if __name__ == "__main__":
    # 测试刚刚失败的 combo_027_5 和 combo_025_5
    print("="*50)
    test_find_item_in_mock_data("combo_027_5")
    print("="*50)
    test_find_item_in_mock_data("combo_025_5")
