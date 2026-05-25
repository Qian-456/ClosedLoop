import json

def check_base_combos_features():
    try:
        with open('mock_data/base/restaurants.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        target_ids = ['combo_004_3', 'combo_009_3', 'combo_025_5']
        for restaurant in data:
            for combo in restaurant.get('combos', []):
                if combo['combo_id'] in target_ids:
                    print(f"{combo['combo_id']} - features: {combo.get('features', [])}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_base_combos_features()
