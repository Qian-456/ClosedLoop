import json
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.plan_subgraph.repairer import repair_plan
from closedloop.contracts.state import Constraints

class AdjustPlanItemInput(BaseModel):
    plan_id: str = Field(..., description="要修改的方案 ID")
    target_item_id: str = Field(..., description="方案中需要被替换的旧条目 ID")
    new_item_id: str = Field(..., description="从 search_candidates 结果中挑选出的新条目 ID")

@tool(args_schema=AdjustPlanItemInput)
def adjust_plan_item(
    plan_id: str,
    target_item_id: str,
    new_item_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    替换行程中的指定条目，并自动处理引发的时间和预算冲突（5级修复策略）。
    """
    config = get_config()
    LoggerManager.setup(config)

    logger.info(f"phase=adjust_plan_item | plan_id={plan_id} | target={target_item_id} | new={new_item_id}")

    latest_plans = state.get("latest_plan_result", [])
    target_plan = None
    for p in latest_plans:
        if isinstance(p, dict) and p.get("plan_id") == plan_id:
            target_plan = p
            break
            
    if not target_plan:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": "找不到指定的方案 ID"}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

    # 从 candidates 里找出 new_item_id 的完整数据
    candidates = state.get("candidates", {})
    new_item_data = None
    for k in ["ranked_breakfast_combos", "ranked_lunch_combos", "ranked_afternoon_tea_combos", "ranked_dinner_combos", "ranked_late_night_combos", "ranked_packages", "ranked_light_packages", "ranked_gifts"]:
        for item in candidates.get(k, []):
            item_id = str(item.get("combo_id") or item.get("package_id") or item.get("gift_id") or item.get("id"))
            if item_id == new_item_id:
                new_item_data = item
                break
        if new_item_data:
            break
            
    # 如果候选池中找不到，可能是由于 search_candidates 返回的是另外一个 session/category 下的数据
    # 为了最强健的兜底保障，直接穿透到原始 Mock 数据库文件中全局检索这个 ID
    if not new_item_data:
        import os
        # 修正路径：获取项目根目录的最安全方法是从 backend/src/closedloop/core/config.py 的相对位置推算
        # 或者直接相对当前文件推算：__file__ 在 backend/src/closedloop/graph/tools/adjust_tool.py
        # 目录层级: tools(1) -> graph(2) -> closedloop(3) -> src(4) -> backend(5) -> ClosedLoop根目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../mock_data/base"))
        
        # 检查如果不对，尝试另外一个层级
        if not os.path.exists(base_dir):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../mock_data/base"))
            
        # 定义需要遍历查找的原始文件与主键/子键映射关系
        db_files = {
            "restaurants.json": ["combos"],
            "activities.json": ["packages"],
            "add_ons.json": ["gifts"]
        }
        
        for file_name, sub_keys in db_files.items():
            file_path = os.path.join(base_dir, file_name)
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    mock_data = json.load(f)
                    
                # 遍历顶层对象
                for parent_item in mock_data:
                    # 检查父级自身（虽然我们要找的通常是子级的 combo/package，但以防万一）
                    if str(parent_item.get("id")) == new_item_id:
                        new_item_data = parent_item
                        break
                        
                    # 检查子级的 combo / package / gift
                    for sub_key in sub_keys:
                        for child_item in parent_item.get(sub_key, []):
                            child_id = str(child_item.get("combo_id") or child_item.get("package_id") or child_item.get("gift_id") or child_item.get("id"))
                            if child_id == new_item_id:
                                # 把父级的关键属性也带给子级，就像 rerank 里做的一样
                                child_item["parent_id"] = parent_item.get("id")
                                child_item["name"] = parent_item.get("name", "") + " - " + child_item.get("name", "")
                                child_item["latitude"] = parent_item.get("latitude")
                                child_item["longitude"] = parent_item.get("longitude")
                                child_item["address"] = parent_item.get("address")
                                child_item["district"] = parent_item.get("district")
                                child_item["suitable_groups"] = parent_item.get("suitable_groups", [])
                                child_item["child_facility_tags"] = parent_item.get("child_facility_tags", [])
                                child_item["kid_menu_status"] = parent_item.get("kid_menu_status")
                                child_item["stroller_friendly_status"] = parent_item.get("stroller_friendly_status")
                                child_item["gift_type"] = parent_item.get("gift_type")
                                child_item["delivery_to_restaurant"] = parent_item.get("delivery_to_restaurant")
                                child_item["age_range"] = parent_item.get("age_range", [])
                                new_item_data = child_item
                                break
                        if new_item_data:
                            break
                    if new_item_data:
                        break
                if new_item_data:
                    break
            except Exception as e:
                logger.warning(f"phase=adjust_plan_item | msg=mock_db_fallback_search_error | file={file_name} | error={e}")

    if not new_item_data:
        return Command(update={
            "messages": [ToolMessage(content=json.dumps({"error": f"在候选池中找不到指定的 new_item_id ({new_item_id})，请检查 ID 是否正确"}, ensure_ascii=False), tool_call_id=tool_call_id)]
        })

    constraints_dict = state.get("constraints", {})
    budget = constraints_dict.get("budget", 999999.0)
    
    # 重新解析 duration_hours_range
    duration_hours = constraints_dict.get("duration_hours")
    duration_hours_range = (4.0, 6.0) # default
    if isinstance(duration_hours, (list, tuple)) and len(duration_hours) == 2:
        duration_hours_range = (float(duration_hours[0]), float(duration_hours[1]))
    elif isinstance(duration_hours, (int, float)):
        duration_hours_range = (float(duration_hours), float(duration_hours))
        
    duration_range_mins = (duration_hours_range[0] * 60.0, duration_hours_range[1] * 60.0)
    commute_preference = constraints_dict.get("commute_preference", "auto")

    result = repair_plan(
        plan=target_plan,
        target_item_id=target_item_id,
        new_item=new_item_data,
        budget=budget,
        duration_range_mins=duration_range_mins,
        candidates=candidates,
        commute_preference=commute_preference
    )

    status = result.get("status", "failed")

    transfer_message = ToolMessage(
        content=json.dumps({
            "tool": "adjust_plan_item",
            "status": status,
            "result": result,
        }, ensure_ascii=False),
        tool_call_id=tool_call_id,
    )

    update = {
        "current_step": "adjust_plan_item",
        "messages": [transfer_message],
    }

    # 如果修复成功，我们把最新的 plan 替换到 latest_plan_result 中
    if status == "success" and "plan" in result:
        new_plan = result["plan"]
        updated_latest = []
        for p in latest_plans:
            if isinstance(p, dict) and p.get("plan_id") == plan_id:
                updated_latest.append(new_plan)
            else:
                updated_latest.append(p)
        update["latest_plan_result"] = updated_latest

        # 同时更新 itinerary (历史记录)
        itinerary = state.get("itinerary", [])
        if isinstance(itinerary, list):
            updated_itinerary = []
            for p in itinerary:
                if isinstance(p, dict) and p.get("plan_id") == plan_id:
                    updated_itinerary.append(new_plan)
                else:
                    updated_itinerary.append(p)
            update["itinerary"] = updated_itinerary

    return Command(update=update)
