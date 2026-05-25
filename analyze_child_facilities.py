import json

def analyze_child_facilities():
    try:
        with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print('=== 检查包含 child_facility_tags 且不为空的餐厅 ===')
        count = 0
        all_tags = set()
        
        for r in data:
            tags = r.get('child_facility_tags')
            if tags and isinstance(tags, list) and len(tags) > 0:
                count += 1
                tags_str = ", ".join(tags)
                print(f"- {r['name']} ({r['id']}): {tags_str}")
                for tag in tags:
                    all_tags.add(tag)
                    
        print(f'\n总计: {count} 家餐厅提供儿童设施。')
        all_tags_str = ", ".join(all_tags)
        print(f'出现过的所有儿童设施标签: {all_tags_str}')
        
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    analyze_child_facilities()