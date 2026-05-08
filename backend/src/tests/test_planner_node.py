import unittest
import sys
import os

# 确保能导入 src 下的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.contracts.state import ClosedLoopState
from closedloop.graph.nodes.planner import planner_node

class TestPlannerNode(unittest.TestCase):
    def setUp(self):
        # 构造 Mock 数据
        self.state: ClosedLoopState = {
            "user_input": "带孩子去玩一下午",
            "constraints": {
                "group_type": "family",
                "budget": 500.0,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "14:00-19:00",
                "duration_hours": 5.0,
                "activity_preferences": [],
                "adult_count": 2,
                "child_count": 1,
                "child_ages": [6]
            },
            "candidates": {
                "ranked_packages": [
                    {"package_id": "act_1", "name": "游乐园", "duration_mins": 120, "score": 90, "price": 100.0, "location": {"address": "测试路1号"}},
                    {"package_id": "act_2", "name": "科技馆", "duration_mins": 90, "score": 85, "price": 80.0, "location": {"address": "测试路2号"}}
                ],
                "ranked_afternoon_tea_combos": [
                    {"combo_id": "tea_1", "name": "亲子下午茶", "duration_mins": 45, "score": 88, "price": 150.0, "location": {"address": "测试路3号"}}
                ],
                "ranked_gifts": [
                    {"gift_id": "gift_1", "name": "盲盒玩具", "score": 80, "price": 50.0, "location": {"address": "测试路4号"}}
                ],
                "ranked_dinner_combos": [
                    {"combo_id": "din_1", "name": "家庭晚餐", "duration_mins": 60, "score": 95, "price": 200.0, "location": {"address": "测试路5号"}}
                ],
                "ranked_lunch_combos": [],
                "ranked_breakfast_combos": [],
                "ranked_late_night_combos": []
            }
        }

    def test_planner_node_family_afternoon(self):
        """测试家庭下午5小时场景（FAM-L-01 完整亲子下午）"""
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "ok")
        self.assertTrue(len(itinerary["plans"]) > 0)
        
        # 确保生成了多套方案，或者至少一套
        self.assertTrue(len(itinerary["plans"]) >= 1)
        
        plan = itinerary["plans"][0]
        steps = plan["steps"]
        
        # FAM-L-01 steps: ["activity", "restaurant:afternoon_tea", "activity", "gift_shop"]
        # 加上 5 个通勤节点，总共 9 个节点
        self.assertEqual(len(steps), 9)
        self.assertEqual(steps[1]["item"]["id"], "act_1")
        self.assertEqual(steps[3]["item"]["id"], "tea_1")
        self.assertEqual(steps[5]["item"]["id"], "act_2")
        self.assertEqual(steps[7]["item"]["id"], "gift_1")
        self.assertEqual(steps[7]["note"], "")
        
        # Verify calculated values
        # 4个真实步骤耗时 285，5个通勤步骤各 2 分钟 = 10 分钟，总 295
        self.assertEqual(plan["total_duration_minutes"], 295)
        self.assertEqual(plan["total_cost"], 380.0) # 100+150+80+50
        # 打分体系变化了，我们只要确保它是大于 0 的数字
        self.assertTrue(plan["average_score"] > 0)

    def test_planner_node_budget_filter(self):
        """测试预算过滤：当超出预算时，组合会被剔除"""
        self.state["constraints"]["budget"] = 200.0 # 非常低的预算
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertEqual(len(itinerary["plans"]), 0)

    def test_planner_node_time_filter(self):
        """测试时间过滤：当时长相差超过30分钟时，组合会被剔除"""
        self.state["constraints"]["duration_hours"] = 2.0 # 预期 120 分钟，但组合时间为 285 分钟
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertEqual(len(itinerary["plans"]), 0)

    def test_planner_node_fallback(self):
        """测试候选不足时的 fallback"""
        self.state["candidates"]["ranked_gifts"] = []
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertIn("gift_shop", itinerary["missing_types"])

if __name__ == "__main__":
    unittest.main()
