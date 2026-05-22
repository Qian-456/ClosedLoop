import unittest
import sys
import os
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from closedloop.contracts.state import ClosedLoopState


class _DummyAgent:
    def __init__(self, *, value=None, error: Exception | None = None):
        self._value = value
        self._error = error

    def invoke(self, _payload):
        if self._error:
            raise self._error
        return self._value


class TestCopywritingNode(unittest.TestCase):
    def _build_ok_state(self) -> ClosedLoopState:
        return {
            "user_input": "我和朋友下午想出去玩，别太累，预算600左右",
            "constraints": {
                "group_type": "friends",
                "budget": 600.0,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "14:00",
                "duration_hours": (4.0, 6.0),
                "activity_preferences": [],
                "adult_count": 2,
                "child_count": 0,
                "child_profiles": [],
                "commute_preference": "auto",
            },
            "itinerary": {
                "status": "ok",
                "missing_types": [],
                "plans": [
                    {
                        "plan_id": "plan_1",
                        "title": "方案1",
                        "total_cost": 220.0,
                        "total_duration_minutes": 240,
                        "average_score": 60.0,
                        "experience_score": 60.0,
                        "selected_item_ids": ["a1", "r1"],
                        "steps": [
                            {
                                "order_id": "1",
                                "duration_minutes": 120,
                                "item": {
                                    "id": "a1",
                                    "name": "展览馆",
                                    "type": "activity",
                                    "location": "路1号",
                                    "distance_km": 2.0,
                                    "cost": 120.0,
                                },
                            },
                            {
                                "order_id": "2",
                                "duration_minutes": 60,
                                "item": {
                                    "id": "r1",
                                    "name": "简餐小馆",
                                    "type": "restaurant",
                                    "location": "路2号",
                                    "distance_km": 1.0,
                                    "cost": 100.0,
                                },
                            },
                        ],
                    },
                    {
                        "plan_id": "plan_2",
                        "title": "方案2",
                        "total_cost": 360.0,
                        "total_duration_minutes": 300,
                        "average_score": 75.0,
                        "experience_score": 75.0,
                        "selected_item_ids": ["a2", "r2", "g2"],
                        "steps": [
                            {
                                "order_id": "1",
                                "duration_minutes": 150,
                                "item": {
                                    "id": "a2",
                                    "name": "密室逃脱",
                                    "type": "activity",
                                    "location": "路3号",
                                    "distance_km": 2.5,
                                    "cost": 200.0,
                                },
                            },
                            {
                                "order_id": "2",
                                "duration_minutes": 60,
                                "item": {
                                    "id": "r2",
                                    "name": "轻食下午茶",
                                    "type": "restaurant",
                                    "location": "路4号",
                                    "distance_km": 0.8,
                                    "cost": 120.0,
                                },
                            },
                            {
                                "order_id": "3",
                                "duration_minutes": 30,
                                "item": {
                                    "id": "g2",
                                    "name": "伴手礼店",
                                    "type": "gift_shop",
                                    "location": "路5号",
                                    "distance_km": 0.5,
                                    "cost": 40.0,
                                },
                            },
                        ],
                    },
                    {
                        "plan_id": "plan_3",
                        "title": "方案3",
                        "total_cost": 520.0,
                        "total_duration_minutes": 360,
                        "average_score": 82.0,
                        "experience_score": 82.0,
                        "selected_item_ids": ["a3", "r3", "a4", "g3"],
                        "steps": [
                            {
                                "order_id": "C1",
                                "duration_minutes": 20,
                                "item": {
                                    "id": "commute_3_1",
                                    "name": "前往 演出",
                                    "type": "commute",
                                    "location": "途中",
                                    "distance_km": 4.0,
                                    "cost": 0.0,
                                    "commute_from": "家",
                                    "commute_to": "演出",
                                    "commute_mode": "taxi",
                                    "commute_options": [],
                                },
                            },
                            {
                                "order_id": "1",
                                "duration_minutes": 120,
                                "item": {
                                    "id": "a3",
                                    "name": "演出",
                                    "type": "activity",
                                    "location": "路6号",
                                    "distance_km": 4.0,
                                    "cost": 260.0,
                                },
                            },
                            {
                                "order_id": "2",
                                "duration_minutes": 60,
                                "item": {
                                    "id": "r3",
                                    "name": "特色晚餐",
                                    "type": "restaurant",
                                    "location": "路7号",
                                    "distance_km": 1.2,
                                    "cost": 200.0,
                                },
                            },
                            {
                                "order_id": "3",
                                "duration_minutes": 60,
                                "item": {
                                    "id": "a4",
                                    "name": "夜游",
                                    "type": "activity",
                                    "location": "路8号",
                                    "distance_km": 3.0,
                                    "cost": 40.0,
                                },
                            },
                            {
                                "order_id": "4",
                                "duration_minutes": 30,
                                "item": {
                                    "id": "g3",
                                    "name": "文创店",
                                    "type": "gift_shop",
                                    "location": "路9号",
                                    "distance_km": 0.6,
                                    "cost": 20.0,
                                },
                            },
                        ],
                    },
                ],
            },
        }

    def test_copywriting_node_happy_path(self):
        from closedloop.contracts.copywriting import ThreePlansCopywriting, PlanCopywriting
        from closedloop.graph.nodes.copywriting import copywriting_node

        structured = ThreePlansCopywriting(
            plan_1=PlanCopywriting(plan_name="省钱轻松逛", pros_cons=["✔ 更省预算", "✘ 丰富度一般"], ai_reminder=""),
            plan_2=PlanCopywriting(plan_name="刚好玩得爽", pros_cons=["✔ 互动感更强", "✘ 花费略高"], ai_reminder=""),
            plan_3=PlanCopywriting(plan_name="高配全都要", pros_cons=["✔ 内容最丰富", "✘ 预算压力大"], ai_reminder=""),
        )

        agent = _DummyAgent(value={"structured_response": structured})

        with patch("closedloop.graph.nodes.copywriting.get_config"), patch(
            "closedloop.graph.nodes.copywriting.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.copywriting.build_agent", return_value=agent):
            out = copywriting_node(self._build_ok_state())

        self.assertEqual(out["confirmation"]["status"], "ok")
        self.assertIn("plan_1", out["confirmation"]["plans"])
        self.assertIn("plan_name", out["confirmation"]["plans"]["plan_1"])

    def test_copywriting_node_skipped_when_not_ok(self):
        from closedloop.graph.nodes.copywriting import copywriting_node

        state = self._build_ok_state()
        state["itinerary"]["status"] = "insufficient_candidates"

        mock_build = Mock()
        with patch("closedloop.graph.nodes.copywriting.get_config"), patch(
            "closedloop.graph.nodes.copywriting.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.copywriting.build_agent", mock_build):
            out = copywriting_node(state)

        self.assertEqual(out["confirmation"]["status"], "skipped")
        mock_build.assert_not_called()

    def test_copywriting_node_fallback_rules_on_llm_error(self):
        from closedloop.graph.nodes.copywriting import copywriting_node

        agent = _DummyAgent(error=RuntimeError("boom"))

        with patch("closedloop.graph.nodes.copywriting.get_config"), patch(
            "closedloop.graph.nodes.copywriting.LoggerManager.setup"
        ), patch("closedloop.graph.nodes.copywriting.build_agent", return_value=agent):
            out = copywriting_node(self._build_ok_state())

        self.assertEqual(out["confirmation"]["status"], "fallback_rules")
        plans = out["confirmation"]["plans"]
        self.assertIn("plan_2", plans)
        self.assertTrue(any("通勤" in s or "路上" in s for s in plans["plan_3"]["pros_cons"]))


if __name__ == "__main__":
    unittest.main()
