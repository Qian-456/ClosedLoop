import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.nodes.plan import plan_itinerary_node
from closedloop.contracts.itinerary import (
    ItineraryItem,
    ItineraryPlan,
    ItineraryPlanVariant,
    ItineraryStep,
)


class _DummyAgent:
    def __init__(self, response):
        self._response = response

    def invoke(self, _payload):
        return self._response


class TestPlanItineraryNode(unittest.TestCase):
    def test_plan_node_fallback_uses_gift_handoff_minutes_as_duration(self):
        state = {
            "user_input": "随便安排一下",
            "constraints": {
                "group_type": "friends",
                "people_count": 2,
                "budget": 500,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "13:00-18:00",
                "duration_hours": 5,
                "activity_preferences": [],
                "child_age": None,
            },
            "candidates": {
                "nearby_restaurants": [
                    {
                        "id": "r001",
                        "name": "轻食花园餐厅",
                        "type": "restaurant",
                        "location": "科技园区A栋",
                        "distance_km": 1.2,
                        "score": 90,
                        "duration_minutes": 60,
                    }
                ],
                "nearby_activities": [
                    {
                        "id": "a001",
                        "name": "亲子科学探索馆",
                        "type": "activity",
                        "location": "科技路8号",
                        "distance_km": 5.2,
                        "score": 80,
                        "duration_minutes": 120,
                    }
                ],
                "nearby_gifts": [
                    {
                        "id": "o002",
                        "name": "花礼与卡片礼物店",
                        "type": "gift_shop",
                        "location": "市中心步行街",
                        "distance_km": 4.6,
                        "score": 70,
                        "lead_time_minutes": 60,
                        "handoff_minutes": 15,
                    }
                ],
                "processed_steps": ["retrieve_candidates_node", "filter_rank_node"],
            },
        }

        response = {
            "structured_response": ItineraryPlan(plans=[], status="ok", missing_types=[])
        }
        with patch(
            "closedloop.graph.nodes.plan.build_agent", return_value=_DummyAgent(response)
        ):
            out = plan_itinerary_node(state)

        self.assertEqual(out["itinerary"].get("status"), "fallback_deterministic")
        steps = out["itinerary"]["plans"][0]["steps"]
        gift_steps = [s for s in steps if s.get("item", {}).get("type") == "gift_shop"]
        self.assertEqual(len(gift_steps), 1)
        self.assertEqual(gift_steps[0].get("duration_minutes"), 15)

    def test_plan_node_happy_path_writes_itinerary(self):
        state = {
            "user_input": "随便安排一下",
            "constraints": {
                "group_type": "friends",
                "people_count": 2,
                "budget": 500,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "13:00-18:00",
                "duration_hours": 5,
                "activity_preferences": [],
                "child_age": None,
            },
            "candidates": {
                "nearby_restaurants": [
                    {
                        "id": "r001",
                        "name": "轻食花园餐厅",
                        "type": "restaurant",
                        "location": "科技园区A栋",
                        "distance_km": 1.2,
                        "score": 90,
                    }
                ],
                "nearby_activities": [
                    {
                        "id": "a001",
                        "name": "亲子科学探索馆",
                        "type": "activity",
                        "location": "科技路8号",
                        "distance_km": 5.2,
                        "score": 80,
                    }
                ],
                "nearby_gifts": [
                    {
                        "id": "o001",
                        "name": "童趣甜品礼物店",
                        "type": "gift_shop",
                        "location": "万达广场B1",
                        "distance_km": 2.8,
                        "score": 70,
                    }
                ],
                "processed_steps": ["retrieve_candidates_node", "filter_rank_node"],
            },
        }

        response = {
            "structured_response": ItineraryPlan(
                plans=[
                    ItineraryPlanVariant(
                        plan_id="plan_1",
                        title="推荐方案",
                        steps=[
                            ItineraryStep(
                                order_id=1,
                                item=ItineraryItem(
                                    id="a001",
                                    name="亲子科学探索馆",
                                    type="activity",
                                    location="科技路8号",
                                    distance_km=5.2,
                                ),
                                duration_minutes=120,
                                note="先活动热身",
                            ),
                            ItineraryStep(
                                order_id=2,
                                item=ItineraryItem(
                                    id="r001",
                                    name="轻食花园餐厅",
                                    type="restaurant",
                                    location="科技园区A栋",
                                    distance_km=1.2,
                                ),
                                duration_minutes=60,
                                note="用餐补给",
                            ),
                            ItineraryStep(
                                order_id=3,
                                item=ItineraryItem(
                                    id="o001",
                                    name="童趣甜品礼物店",
                                    type="gift_shop",
                                    location="万达广场B1",
                                    distance_km=2.8,
                                ),
                                duration_minutes=30,
                                note="顺路买礼物",
                            ),
                        ],
                        selected_item_ids=["a001", "r001", "o001"],
                        total_duration_minutes=210,
                    )
                ],
                status="ok",
                missing_types=[],
            )
        }

        with patch("closedloop.graph.nodes.plan.build_agent", return_value=_DummyAgent(response)):
            out = plan_itinerary_node(state)

        self.assertIn("itinerary", out)
        self.assertIsInstance(out["itinerary"], dict)
        self.assertEqual(out["itinerary"].get("status"), "ok")
        self.assertIn("plans", out["itinerary"])
        self.assertGreaterEqual(len(out["itinerary"]["plans"]), 1)
        self.assertIn("total_duration_minutes", out["itinerary"]["plans"][0])

    def test_plan_node_fallback_when_llm_output_missing_required_types(self):
        state = {
            "user_input": "随便安排一下",
            "constraints": {
                "group_type": "friends",
                "people_count": 2,
                "budget": 500,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "13:00-18:00",
                "duration_hours": 5,
                "activity_preferences": [],
                "child_age": None,
            },
            "candidates": {
                "nearby_restaurants": [
                    {
                        "id": "r001",
                        "name": "轻食花园餐厅",
                        "type": "restaurant",
                        "location": "科技园区A栋",
                        "distance_km": 1.2,
                        "score": 90,
                    }
                ],
                "nearby_activities": [
                    {
                        "id": "a001",
                        "name": "亲子科学探索馆",
                        "type": "activity",
                        "location": "科技路8号",
                        "distance_km": 5.2,
                        "score": 80,
                    }
                ],
                "nearby_gifts": [
                    {
                        "id": "o001",
                        "name": "童趣甜品礼物店",
                        "type": "gift_shop",
                        "location": "万达广场B1",
                        "distance_km": 2.8,
                        "score": 70,
                    }
                ],
                "processed_steps": ["retrieve_candidates_node", "filter_rank_node"],
            },
        }

        response = {
            "structured_response": ItineraryPlan(
                plans=[
                    ItineraryPlanVariant(
                        plan_id="plan_1",
                        title="缺少礼品店的方案",
                        steps=[
                            ItineraryStep(
                                order_id=1,
                                item=ItineraryItem(
                                    id="a001",
                                    name="亲子科学探索馆",
                                    type="activity",
                                    location="科技路8号",
                                    distance_km=5.2,
                                ),
                                duration_minutes=120,
                                note="先活动",
                            ),
                            ItineraryStep(
                                order_id=2,
                                item=ItineraryItem(
                                    id="r001",
                                    name="轻食花园餐厅",
                                    type="restaurant",
                                    location="科技园区A栋",
                                    distance_km=1.2,
                                ),
                                duration_minutes=60,
                                note="再吃饭",
                            ),
                        ],
                        selected_item_ids=["a001", "r001"],
                        total_duration_minutes=180,
                    )
                ],
                status="ok",
                missing_types=[],
            )
        }

        with patch("closedloop.graph.nodes.plan.build_agent", return_value=_DummyAgent(response)):
            out = plan_itinerary_node(state)

        self.assertEqual(out["itinerary"].get("status"), "fallback_deterministic")

        types = []
        for step in out["itinerary"]["plans"][0]["steps"]:
            types.append(step["item"]["type"])
        self.assertIn("activity", types)
        self.assertIn("restaurant", types)
        self.assertIn("gift_shop", types)

    def test_plan_node_insufficient_candidates(self):
        state = {
            "user_input": "随便安排一下",
            "constraints": {
                "group_type": "friends",
                "people_count": 2,
                "budget": 500,
                "dietary_restrictions": [],
                "preferred_distance": "2km-5km",
                "time_period": "13:00-18:00",
                "duration_hours": 5,
                "activity_preferences": [],
                "child_age": None,
            },
            "candidates": {
                "nearby_restaurants": [
                    {
                        "id": "r001",
                        "name": "轻食花园餐厅",
                        "type": "restaurant",
                        "location": "科技园区A栋",
                        "distance_km": 1.2,
                        "score": 90,
                    }
                ],
                "nearby_activities": [
                    {
                        "id": "a001",
                        "name": "亲子科学探索馆",
                        "type": "activity",
                        "location": "科技路8号",
                        "distance_km": 5.2,
                        "score": 80,
                    }
                ],
                "nearby_gifts": [],
                "processed_steps": ["retrieve_candidates_node", "filter_rank_node"],
            },
        }

        with patch("closedloop.graph.nodes.plan.build_agent") as mocked:
            out = plan_itinerary_node(state)

        mocked.assert_not_called()
        self.assertEqual(out["itinerary"].get("status"), "insufficient_candidates")
        self.assertIn("gift_shop", out["itinerary"].get("missing_types", []))


if __name__ == "__main__":
    unittest.main()
