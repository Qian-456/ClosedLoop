import json
import os

def process_file(filepath, key_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    removed_count = 0
    for item in data:
        if key_name in item:
            for sub_item in item[key_name]:
                if 'start_time' in sub_item:
                    # Check if it's a fixed show (e.g., has "演出" or "话剧" in name/description)
                    is_fixed = False
                    text = (sub_item.get('name', '') + sub_item.get('description', '')).lower()
                    if '演出' in text or '话剧' in text or '音乐会' in text:
                        is_fixed = True
                        
                    if not is_fixed:
                        del sub_item['start_time']
                        removed_count += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Removed {removed_count} start_times from {filepath}")

base_dir = os.path.join('backend', 'src', 'mock_db')
process_file(os.path.join(base_dir, 'activities.json'), 'packages')
process_file(os.path.join(base_dir, 'restaurants.json'), 'combos')
