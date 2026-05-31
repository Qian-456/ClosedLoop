import json

with open("backend/src/mock_db/add_ons.json", "r", encoding="utf-8") as f:
    add_ons = json.load(f)

for s in add_ons:
    for g in s.get("gifts", []):
        if g.get("gift_id") in ["gift_011_1", "gift_011_3", "gift_011_6"]:
            print(f"Found {g.get('gift_id')}: stock={g.get('stock')}")
