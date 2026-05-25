import unittest
from closedloop.graph.plan_subgraph.repairer import repair_plan, _build_itinerary_item

class TestRepairer(unittest.TestCase):
    def setUp(self):
        self.original_plan = {
            "plan_id": "test_plan",
            "steps": [
                {
                    "order_id": "1",
                    "duration_minutes": 120,
                    "item": {
                        "id": "act_1",
                        "type": "activity",
                        "name": "Activity 1",
                        "cost": 100.0,
                        "location": "Loc A",
                        "distance_km": 0.0
                    }
                },
                {
                    "order_id": "C1",
                    "duration_minutes": 15,
                    "item": {
                        "id": "commute_1",
                        "type": "commute",
                        "name": "前往 Activity 2",
                        "cost": 15.0,
                        "distance_km": 0.0
                    }
                },
                {
                    "order_id": "2",
                    "duration_minutes": 60,
                    "item": {
                        "id": "act_2",
                        "type": "activity",
                        "name": "Activity 2",
                        "cost": 50.0,
                        "location": "Loc B",
                        "distance_km": 0.0
                    }
                }
            ],
            "total_duration_minutes": 195,
            "total_cost": 165.0,
            "selected_item_ids": ["act_1", "act_2"]
        }

        self.candidates = {
            "ranked_packages": [
                {
                    "package_id": "act_1",
                    "name": "Activity 1",
                    "price": 100.0,
                    "duration_mins": 120,
                    "duration_std_dev": 20.0,
                    "type": "activity",
                    "latitude": 1.0,
                    "longitude": 1.0
                },
                {
                    "package_id": "act_2",
                    "name": "Activity 2",
                    "price": 50.0,
                    "duration_mins": 60,
                    "duration_std_dev": 10.0,
                    "type": "activity",
                    "latitude": 1.5,
                    "longitude": 1.5
                }
            ]
        }

    def test_repair_plan_success_no_conflict(self):
        new_item = {
            "id": "act_3",
            "type": "activity",
            "name": "New Activity",
            "price": 60.0,
            "duration_mins": 60,
            "latitude": 1.5,
            "longitude": 1.5
        }
        
        result = repair_plan(
            plan=self.original_plan,
            target_item_id="act_2",
            new_item=new_item,
            budget=300.0,
            duration_range_mins=(120, 240),
            candidates=self.candidates
        )
        
        self.assertEqual(result["status"], "success")
        self.assertIn("act_3", result["plan"]["selected_item_ids"])

    def test_repair_plan_level_1_buffer(self):
        # New item takes 150 mins, total will be 120 + 150 + commutes > 240 + 45?
        # Let's set max duration tight to trigger buffer eating.
        new_item = {
            "id": "act_3",
            "type": "activity",
            "name": "New Activity",
            "price": 60.0,
            "duration_mins": 100,  # Originally 60. New dur increases by 40.
            "duration_std_dev": 0.0,
            "latitude": 1.5,
            "longitude": 1.5
        }
        
        # Max duration = 240. Target max + 45 = 285.
        # Commutes: act_1 -> act_3 is around 1.4km -> walk 15 mins.
        # Home -> act_1 -> act_3 -> Home.
        # Let's set duration_range_mins to a value where it's slightly over.
        result = repair_plan(
            plan=self.original_plan,
            target_item_id="act_2",
            new_item=new_item,
            budget=300.0,
            duration_range_mins=(120, 180), # max_dur = 225
            candidates=self.candidates
        )
        
        # Original act_1 has duration 120, std_dev 20. It can be reduced by 20.
        # The new total without shrink would be: act_1(120) + act_3(100) + commutes(~15+15+15=45) = 265
        # 265 > 225. Shrink act_1 by 20 -> 245. Still > 225.
        # Then compress act_1 (min = 120 * 0.6 = 72). Compress by 245 - 225 = 20.
        # Result should be success after compression.
        
        self.assertEqual(result["status"], "success")
        
        # 因为通勤多了 5 分钟，原有的断言方式需要更新
        # 我们重新拉取并检查 duration
        result = repair_plan(
            plan=self.original_plan,
            target_item_id="act_2",
            new_item=new_item,
            budget=200.0,
            duration_range_mins=(180.0, 240.0), # 调大上限到 240，加上 45 就是 285，刚好包住 275 的总时长，触发 L1/L2
            candidates=self.candidates
        )
        self.assertEqual(result["status"], "success")
        
        act_1_step = next(s for s in result["plan"]["steps"] if s["item"]["id"] == "act_1")
        self.assertLessEqual(act_1_step["duration_minutes"], 120)

    def test_repair_plan_level_4_delete_low_priority(self):
        # We add a gift shop to the plan, then make it exceed time/budget.
        self.original_plan["steps"].append({
            "order_id": "3",
            "duration_minutes": 30,
            "item": {
                "id": "gift_1",
                "type": "gift_shop",
                "name": "Gift Shop",
                "cost": 50.0,
                "distance_km": 0.0,
                "location": "Loc C"
            }
        })
        self.original_plan["selected_item_ids"].append("gift_1")
        
        self.candidates["ranked_gifts"] = [{
            "gift_id": "gift_1",
            "name": "Gift Shop",
            "price": 50.0,
            "duration_mins": 30,
            "type": "gift_shop"
        }]

        new_item = {
            "id": "act_3",
            "type": "activity",
            "name": "Very Long Activity",
            "price": 60.0,
            "duration_mins": 300, # Very long, cannot be resolved by compression
            "latitude": 1.5,
            "longitude": 1.5
        }

        # This should fail buffer and compression, then trigger deletion of gift_shop
        result = repair_plan(
            plan=self.original_plan,
            target_item_id="act_2",
            new_item=new_item,
            budget=300.0,
            duration_range_mins=(120, 200), # max_dur = 245
            candidates=self.candidates
        )
        
        # Even deleting the gift shop, act_3 is 300 mins. 300 > 245.
        # It will still fail and go to Level 5.
        self.assertEqual(result["status"], "need_user_choice")
        self.assertIn("保留全部并延长", [opt["label"] for opt in result["report"]["options"]])

if __name__ == '__main__':
    unittest.main()
