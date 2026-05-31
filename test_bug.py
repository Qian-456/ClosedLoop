import asyncio
from unittest.mock import patch, AsyncMock
from langgraph.types import Command
import json

from closedloop.graph.tools.adjust_tool import adjust_and_execute_plan_item

async def run_bug():
    # 模拟第一次替换
    state_1 = {
        "plan_option": {
            "plan_id": "plan_A",
            "total_cost": 100,
            "steps": [
                {
                    "item": {
                        "id": "gift_011_6",
                        "type": "gift_shop",
                        "name": "Old Gift",
                        "cost": 100
                    },
                    "duration_minutes": 30
                }
            ]
        },
        "latest_plan_result": [
            {
                "plan_id": "plan_A",
                "total_cost": 100,
                "steps": [
                    {
                        "item": {
                            "id": "gift_011_6",
                            "type": "gift_shop",
                            "name": "Old Gift",
                            "cost": 100
                        },
                        "duration_minutes": 30
                    }
                ]
            }
        ],
        "candidates": {
            "ranked_gifts": [
                {
                    "gift_id": "gift_011_1",
                    "name": "New Gift 1",
                    "price": 100,
                    "duration_mins": 30,
                    "score": 90,
                    "shop_id": "s1",
                    "shop_name": "s1"
                },
                {
                    "gift_id": "gift_011_3",
                    "name": "New Gift 2",
                    "price": 100,
                    "duration_mins": 30,
                    "score": 90,
                    "shop_id": "s1",
                    "shop_name": "s1"
                }
            ]
        }
    }

    class FakeConfig:
        def __init__(self):
            self.TOOL_HTTP_TIMEOUT_SECS = 3.0
            self.TOOL_MAX_RUNTIME_SECS = 3.0
            self.PLAN_SUB_API_URL = "http://localhost"
            self.PLAN_SUB_NETWORK_MODE = "local"
    
    config_runnable = {"configurable": {"thread_id": "thread-1"}}

    # Mock _do_execute_itinerary to return needs_fixup for the first replacement
    async def mock_execute(plan_id, target_plan, state, config, book_commutes_policy, tool_budget_secs, started_at):
        print(f"--- MOCK EXECUTE CALLED ---")
        print(f"Plan ID: {plan_id}")
        print(f"Steps in target_plan: {[s['item']['id'] for s in target_plan['steps']]}")
        
        # return failed to simulate out of stock
        return "needs_fixup", {"message": "failed", "execution_summary": {"failures": [{"item_id": "gift_011_1"}]}}, {"current_step": "needs_fixup", "active_agent": "fixup_agent"}

    print("=== FIRST REPLACEMENT (gift_011_6 -> gift_011_1) ===")
    with patch("closedloop.graph.tools.adjust_tool._do_execute_itinerary", new=AsyncMock(side_effect=mock_execute)):
        with patch("closedloop.graph.tools.adjust_tool.get_config", return_value=FakeConfig()):
            with patch("closedloop.graph.tools.adjust_tool.LoggerManager.setup", return_value=None):
                cmd_1 = await adjust_and_execute_plan_item.coroutine(
                    plan_id="plan_A",
                    target_item_id="gift_011_6",
                    new_item_id="gift_011_1",
                    tool_call_id="call_1",
                    state=state_1,
                    config_runnable=config_runnable,
                    book_commutes_policy="first_only"
                )

    update_1 = cmd_1.update
    print(f"Update 1 Keys: {update_1.keys()}")
    if "plan_option" in update_1:
        print(f"Plan Option Steps in Update 1: {[s['item']['id'] for s in update_1['plan_option']['steps']]}")
    else:
        print("ERROR: plan_option NOT in update_1")
    
    # 模拟第二次替换
    print("\n=== SECOND REPLACEMENT (gift_011_1 -> gift_011_3) ===")
    # 模拟 LangGraph 状态合并
    state_2 = dict(state_1)
    state_2.update(update_1) # This is where the bug might be!

    with patch("closedloop.graph.tools.adjust_tool._do_execute_itinerary", new=AsyncMock(side_effect=mock_execute)):
        with patch("closedloop.graph.tools.adjust_tool.get_config", return_value=FakeConfig()):
            with patch("closedloop.graph.tools.adjust_tool.LoggerManager.setup", return_value=None):
                cmd_2 = await adjust_and_execute_plan_item.coroutine(
                    plan_id="plan_A",
                    target_item_id="gift_011_1",
                    new_item_id="gift_011_3",
                    tool_call_id="call_2",
                    state=state_2,
                    config_runnable=config_runnable,
                    book_commutes_policy="first_only"
                )
    
    update_2 = cmd_2.update
    if "messages" in update_2:
        for msg in update_2["messages"]:
            print(f"Message in Update 2: {msg.content}")

if __name__ == "__main__":
    asyncio.run(run_bug())
