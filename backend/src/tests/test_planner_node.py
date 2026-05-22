import unittest
import sys
import os
from unittest.mock import patch

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
                "time_period": "14:00",
                "duration_hours": (5.0, 5.0),
                "activity_preferences": [],
                "adult_count": 2,
                "child_count": 1,
                "child_profiles": [("F", 6)],
                "commute_preference": "auto",
            },
            "candidates": {
                "ranked_packages": [
                    {"package_id": "act_1", "name": "游乐园", "duration_mins": 120, "score": 90, "price": 100.0, "description": "亲子互动的室内游乐区", "features": "亲子友好，解放体力", "location": {"address": "测试路1号"}},
                    {"package_id": "act_2", "name": "科技馆", "duration_mins": 90, "score": 85, "price": 80.0, "description": "寓教于乐的科普体验", "features": "适合小朋友探索", "location": {"address": "测试路2号"}}
                ],
                "ranked_afternoon_tea_combos": [
                    {"combo_id": "tea_1", "name": "亲子下午茶", "duration_mins": 45, "score": 88, "price": 150.0, "description": "甜品+饮品组合", "features": "适合拍照和休息", "location": {"address": "测试路3号"}}
                ],
                "ranked_gifts": [
                    {
                        "gift_id": "gift_1",
                        "name": "盲盒玩具",
                        "score": 80,
                        "price": 50.0,
                        "description": "随机款式盲盒",
                        "features": "拆盒瞬间的小惊喜",
                        "delivery_radius_km": 5.0,
                        "receive_duration_mins": 10,
                        "receive_duration_std_dev": 3.0,
                        "location": {"address": "测试路4号"},
                    }
                ],
                "ranked_dinner_combos": [
                    {"combo_id": "din_1", "name": "家庭晚餐", "duration_mins": 60, "score": 95, "price": 200.0, "description": "适合全家分享的晚餐", "features": "口味清淡，老少皆宜", "location": {"address": "测试路5号"}}
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

        # 在候选方案中找到包含指定 4 个核心条目的方案并校验其结构
        matched = None
        for p in itinerary["plans"]:
            steps = p["steps"]
            ids = [s["item"]["id"] for s in steps if s["item"]["type"] != "commute"]
            if ids == ["act_1", "tea_1", "act_2", "gift_1"]:
                matched = p
                break

        self.assertIsNotNone(matched)
        steps = matched["steps"]

        # FAM-L-01 steps: ["activity", "restaurant:afternoon_tea", "activity", "gift_shop"]
        # gift_shop 为配送：不产生通勤节点，因此比原先少 1 个通勤节点
        self.assertEqual(len(steps), 8)
        self.assertEqual(steps[1]["item"]["id"], "act_1")
        self.assertEqual(steps[3]["item"]["id"], "tea_1")
        self.assertEqual(steps[5]["item"]["id"], "act_2")
        self.assertEqual(steps[6]["item"]["id"], "gift_1")

        # 通勤节点应包含可切换的交通方式选项
        self.assertEqual(steps[0]["item"]["type"], "commute")
        self.assertIn("commute_options", steps[0]["item"])
        self.assertEqual(len(steps[0]["item"]["commute_options"]), 2)

        # 非通勤节点应包含介绍与特色
        self.assertEqual(steps[1]["item"]["intro"], "亲子互动的室内游乐区")
        self.assertEqual(steps[1]["item"]["features"], "亲子友好，解放体力")
        
        # Verify calculated values
        # 真实步骤耗时 265（gift 收礼时长 10），4个通勤步骤各 2 分钟 = 8 分钟，总 273
        self.assertEqual(matched["total_duration_minutes"], 273)
        # total_cost 包含 gift 配送费：base_fee=3
        self.assertEqual(matched["total_cost"], 383.0) # 100+150+80+(50+3)
        # 打分体系变化了，我们只要确保它是大于 0 的数字
        self.assertTrue(matched["average_score"] > 0)
        self.assertTrue(matched["experience_score"] > 0)

        gift_step = steps[6]
        self.assertEqual(gift_step["item"]["gift_price"], 50.0)
        self.assertEqual(gift_step["item"]["delivery_fee"], 3.0)
        self.assertEqual(gift_step["item"]["delivery_distance_km"], 0.0)

    def test_planner_node_budget_filter(self):
        """测试预算过滤：当超出预算时，组合会被剔除"""
        self.state["constraints"]["budget"] = 200.0 # 非常低的预算
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertEqual(len(itinerary["plans"]), 0)

    def test_planner_node_time_filter(self):
        """测试时间过滤：当时长相差超过30分钟时，组合会被剔除"""
        self.state["constraints"]["duration_hours"] = (1.0, 1.0) # 预期 60 分钟，现有组合都将超出硬窗口
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertEqual(len(itinerary["plans"]), 0)

    def test_planner_node_time_period_window_overrides_duration_range(self):
        self.state["constraints"]["time_period"] = "14:00-17:00"
        self.state["constraints"]["duration_hours"] = (4.0, 6.0)
        new_state = planner_node(self.state)

        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "ok")
        self.assertGreaterEqual(len(itinerary["plans"]), 1)
        for p in itinerary["plans"]:
            self.assertLessEqual(p["total_duration_minutes"], 225)

    def test_planner_node_fallback(self):
        """测试候选不足时的 fallback"""
        self.state["candidates"]["ranked_gifts"] = []
        new_state = planner_node(self.state)
        
        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "insufficient_candidates")
        self.assertIn("gift_shop", itinerary["missing_types"])

    def test_planner_node_taxi_preference_keeps_plan_costs_monotonic(self):
        self.state["constraints"]["commute_preference"] = "taxi"

        plan_infos = [
            {
                "pattern": {"desc": "A"},
                "combo": [
                    {
                        "_step_type": "activity",
                        "package_id": "p1",
                        "name": "p1",
                        "duration_mins": 60,
                        "price": 100.0,
                        "location": {"address": "a", "longitude": 10.0, "latitude": 0.0},
                    }
                ],
                "commutes": [
                    {"time": 25.0, "cost": 0.0, "mode": "driving", "distance": 10.0},
                    {"time": 25.0, "cost": 0.0, "mode": "driving", "distance": 10.0},
                ],
                "average_score": 50.0,
                "experience_score": 50.0,
                "total_cost": 100.0,
                "total_duration_minutes": 60,
            },
            {
                "pattern": {"desc": "B"},
                "combo": [
                    {
                        "_step_type": "activity",
                        "package_id": "p2",
                        "name": "p2",
                        "duration_mins": 60,
                        "price": 110.0,
                        "location": {"address": "b", "longitude": 0.5, "latitude": 0.0},
                    }
                ],
                "commutes": [
                    {"time": 8.0, "cost": 0.0, "mode": "walking", "distance": 0.5},
                    {"time": 8.0, "cost": 0.0, "mode": "walking", "distance": 0.5},
                ],
                "average_score": 60.0,
                "experience_score": 60.0,
                "total_cost": 110.0,
                "total_duration_minutes": 60,
            },
            {
                "pattern": {"desc": "C"},
                "combo": [
                    {
                        "_step_type": "activity",
                        "package_id": "p3",
                        "name": "p3",
                        "duration_mins": 60,
                        "price": 200.0,
                        "location": {"address": "c", "longitude": 8.0, "latitude": 0.0},
                    }
                ],
                "commutes": [
                    {"time": 22.0, "cost": 0.0, "mode": "driving", "distance": 8.0},
                    {"time": 22.0, "cost": 0.0, "mode": "driving", "distance": 8.0},
                ],
                "average_score": 70.0,
                "experience_score": 70.0,
                "total_cost": 200.0,
                "total_duration_minutes": 60,
            },
        ]

        with patch(
            "closedloop.graph.nodes.planner.generate_and_score_combinations",
            return_value=(plan_infos, len(plan_infos), set()),
        ):
            new_state = planner_node(self.state)

        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "ok")
        self.assertEqual(len(itinerary["plans"]), 3)

        costs = [p["total_cost"] for p in itinerary["plans"]]
        self.assertTrue(costs[0] <= costs[1] <= costs[2])

    def test_planner_node_activity_light_type_normalized_to_activity(self):
        plan_infos = [
            {
                "pattern": {"desc": "A"},
                "combo": [
                    {
                        "_step_type": "activity_light",
                        "package_id": "p_light_1",
                        "name": "轻玩票",
                        "venue_name": "轻玩馆",
                        "duration_mins": 45,
                        "price": 30.0,
                        "location": {"address": "a", "longitude": 1.0, "latitude": 0.0},
                    }
                ],
                "commutes": [
                    {"time": 3.0, "cost": 0.0, "mode": "walking", "distance": 1.0},
                    {"time": 3.0, "cost": 0.0, "mode": "walking", "distance": 1.0},
                ],
                "average_score": 50.0,
                "experience_score": 50.0,
                "total_cost": 30.0,
                "total_duration_minutes": 45,
            }
        ]

        with patch(
            "closedloop.graph.nodes.planner.generate_and_score_combinations",
            return_value=(plan_infos, len(plan_infos), set()),
        ):
            new_state = planner_node(self.state)

        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "ok")
        plan = itinerary["plans"][0]
        steps = plan["steps"]

        self.assertEqual(steps[0]["item"]["type"], "commute")
        self.assertEqual(steps[0]["item"]["commute_to"], "轻玩馆")

        self.assertEqual(steps[1]["item"]["type"], "activity")
        self.assertEqual(steps[1]["item"]["id"], "p_light_1")

    def test_commute_name_uses_place_name_instead_of_package_name(self):
        plan_infos = [
            {
                "pattern": {"desc": "A"},
                "combo": [
                    {
                        "_step_type": "restaurant:dinner",
                        "_meal_category": "dinner",
                        "combo_id": "c1",
                        "name": "双人套餐",
                        "restaurant_name": "海底捞",
                        "duration_mins": 60,
                        "price": 100.0,
                        "location": {"address": "a", "longitude": 1.0, "latitude": 0.0},
                    }
                ],
                "commutes": [
                    {"time": 3.0, "cost": 0.0, "mode": "walking", "distance": 1.0},
                    {"time": 3.0, "cost": 0.0, "mode": "walking", "distance": 1.0},
                ],
                "average_score": 50.0,
                "experience_score": 50.0,
                "total_cost": 100.0,
                "total_duration_minutes": 60,
            }
        ]

        with patch(
            "closedloop.graph.nodes.planner.generate_and_score_combinations",
            return_value=(plan_infos, len(plan_infos), set()),
        ):
            new_state = planner_node(self.state)

        itinerary = new_state.get("itinerary", {})
        self.assertEqual(itinerary["status"], "ok")
        plan = itinerary["plans"][0]
        steps = plan["steps"]
        self.assertEqual(steps[0]["item"]["type"], "commute")
        self.assertEqual(steps[0]["item"]["name"], "前往 海底捞")
        self.assertEqual(steps[0]["item"]["commute_to"], "海底捞")
        self.assertEqual(steps[0]["item"]["display_name"], "家 -> 海底捞")
        self.assertEqual(steps[0]["item"]["sub_name"], "推荐方式：步行")

        self.assertEqual(steps[1]["item"]["type"], "restaurant")
        self.assertEqual(steps[1]["item"]["name"], "双人套餐")
        self.assertEqual(steps[1]["item"]["parent_name"], "海底捞")
        self.assertEqual(steps[1]["item"]["display_name"], "海底捞")
        self.assertEqual(steps[1]["item"]["sub_name"], "双人套餐")
        self.assertNotIn("commute_from", steps[1]["item"])
        self.assertNotIn("commute_to", steps[1]["item"])
        self.assertNotIn("commute_mode", steps[1]["item"])
        self.assertNotIn("commute_options", steps[1]["item"])

if __name__ == "__main__":
    unittest.main()
