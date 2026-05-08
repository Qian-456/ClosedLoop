import time
import random
from closedloop.graph.nodes.planner_utils import (
    generate_and_score_combinations
)

def generate_mock_queues():
    queues = {
        "activity": [],
        "gift_shop": [],
        "lunch": [],
        "dinner": []
    }
    for i in range(20):
        queues["activity"].append({
            "package_id": f"act_{i}",
            "name": f"Activity {i}",
            "price": random.uniform(50, 200),
            "score": random.uniform(60, 100),
            "duration_mins": random.choice([60, 90, 120]),
            "location": {"longitude": random.uniform(-10, 10), "latitude": random.uniform(-10, 10)}
        })
        queues["gift_shop"].append({
            "gift_id": f"gift_{i}",
            "name": f"Gift {i}",
            "price": random.uniform(20, 100),
            "score": random.uniform(60, 100),
            "duration_mins": 30,
            "location": {"longitude": random.uniform(-10, 10), "latitude": random.uniform(-10, 10)}
        })
        queues["lunch"].append({
            "combo_id": f"lunch_{i}",
            "name": f"Lunch {i}",
            "price": random.uniform(30, 100),
            "score": random.uniform(60, 100),
            "duration_mins": 60,
            "location": {"longitude": random.uniform(-10, 10), "latitude": random.uniform(-10, 10)}
        })
        queues["dinner"].append({
            "combo_id": f"dinner_{i}",
            "name": f"Dinner {i}",
            "price": random.uniform(50, 150),
            "score": random.uniform(60, 100),
            "duration_mins": 60,
            "location": {"longitude": random.uniform(-10, 10), "latitude": random.uniform(-10, 10)}
        })
    return queues

def test_dfs_performance():
    queues = generate_mock_queues()
    patterns = [
        {
            "desc": "Pattern 1",
            "steps": ["activity", "restaurant:lunch", "activity", "restaurant:dinner", "gift_shop"]
        },
        {
            "desc": "Pattern 2",
            "steps": ["restaurant:lunch", "activity", "activity", "restaurant:dinner", "gift_shop"]
        }
    ]
    budget = 400
    required_duration_mins = 300

    start_time = time.time()
    
    valid_plans_info, valid_count, missing = generate_and_score_combinations(
        queues, patterns, budget, required_duration_mins, top_k=20
    )
    
    total_time = time.time() - start_time
    print(f"DFS total time: {total_time:.4f}s")
    print(f"Valid count: {valid_count}, Top K: {len(valid_plans_info)}, Missing: {missing}")

if __name__ == "__main__":
    random.seed(42)
    test_dfs_performance()
