import json
import os
import random

def optimize_reservations():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mock_db_dir = os.path.join(os.path.dirname(script_dir), "backend", "src", "mock_db")
    reservations_path = os.path.join(mock_db_dir, "reservations.json")

    with open(reservations_path, "r", encoding="utf-8") as f:
        reservations = json.load(f)

    # 随机数种子以保证稳定
    random.seed(42)

    for item in reservations:
        slots = item.get("time_slots", [])
        for slot in slots:
            wait = slot.get("wait_minutes", 0)
            if wait > 15:
                # 只有 15% 的概率保留较长排队时间，且最高控制在 45 分钟左右
                if random.random() < 0.15:
                    new_wait = random.randint(15, 45)
                else:
                    new_wait = random.randint(0, 15)
                
                slot["wait_minutes"] = new_wait
                if new_wait == 0:
                    slot["queue_required"] = False
                else:
                    slot["queue_required"] = True

    with open(reservations_path, "w", encoding="utf-8") as f:
        json.dump(reservations, f, ensure_ascii=False, indent=2)

    print(f"Successfully optimized reservations.json at {reservations_path}")

if __name__ == "__main__":
    optimize_reservations()
