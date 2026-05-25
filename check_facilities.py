import json

def check_child_facilities():
    try:
        with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        found = []
        for r in data:
            tags = r.get('child_facility_tags', [])
            if tags:
                found.append({'name': r['name'], 'id': r['id'], 'tags': tags})
                
        print(f"Total restaurants with child facilities: {len(found)}")
        for idx, r in enumerate(found):
            print(f"{idx+1}. {r['name']} ({r['id']}) - 设施: {', '.join(r['tags'])}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_child_facilities()
