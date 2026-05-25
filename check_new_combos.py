import json

def check_combos():
    try:
        with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        target_ids = ['combo_009_3', 'combo_001_3', 'combo_003_3', 'combo_027_5']
        found = []
        for restaurant in data:
            for combo in restaurant.get('combos', []):
                if combo['combo_id'] in target_ids:
                    found.append({
                        'id': combo['combo_id'],
                        'name': combo.get('name', ''),
                        'price': combo['price'],
                        'duration': combo.get('duration_mins', ''),
                        'desc': combo['description']
                    })
        
        for c in found:
            print(f"Found: {c['id']} | Name: {c['name']} | Price: {c['price']} | Duration: {c['duration']}min | Desc: {c['desc']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_combos()
