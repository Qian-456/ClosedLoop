import json

def check_base_combos():
    try:
        with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        target_ids = ['combo_004_3', 'combo_009_3', 'combo_025_5']
        found = []
        for restaurant in data:
            for combo in restaurant.get('combos', []):
                if combo['combo_id'] in target_ids:
                    found.append((combo['combo_id'], combo['description'], combo['price']))
        
        for c in found:
            print(f"Found: {c[0]} | Price: {c[2]} | Desc: {c[1]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_base_combos()
