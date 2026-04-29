import json
from typing import Any

from langchain.messages import SystemMessage, HumanMessage

from closedloop.contracts.itinerary import ItineraryPlan
from closedloop.contracts.state import ClosedLoopState
from closedloop.core.config import get_config
from closedloop.core.llm import build_agent
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.prompts.plan import PLAN_ITINERARY_SYSTEM_PROMPT


def _safe_list(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def _missing_types_from_candidates(candidates: dict) -> list[str]:
    missing: list[str] = []
    if not _safe_list(candidates.get("nearby_restaurants")):
        missing.append("restaurant")
    if not _safe_list(candidates.get("nearby_activities")):
        missing.append("activity")
    if not _safe_list(candidates.get("nearby_gifts")):
        missing.append("gift_shop")
    return missing


def _candidate_id_set(candidates: dict) -> set[str]:
    ids: set[str] = set()
    for key in ("nearby_restaurants", "nearby_activities", "nearby_gifts"):
        for item in _safe_list(candidates.get(key)):
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id:
                ids.add(item_id)
    return ids


def _sort_key_for_best(item: dict) -> tuple:
    score = item.get("score")
    try:
        score_value = int(score)
    except Exception:
        score_value = 0

    distance = item.get("distance_km")
    try:
        distance_value = float(distance)
    except Exception:
        distance_value = float("inf")

    return (-score_value, distance_value)


def _pick_best(items: list[dict]) -> dict | None:
    if not items:
        return None
    return sorted(items, key=_sort_key_for_best)[0]


def _as_itinerary_item(item: dict) -> dict:
    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "type": item.get("type", ""),
        "location": item.get("location", ""),
        "distance_km": item.get("distance_km", 0),
    }


def _fallback_deterministic(candidates: dict) -> dict:
    activity = _pick_best(_safe_list(candidates.get("nearby_activities")))
    restaurant = _pick_best(_safe_list(candidates.get("nearby_restaurants")))
    gift_shop = _pick_best(_safe_list(candidates.get("nearby_gifts")))

    steps: list[dict] = []
    total = 0

    if activity is not None:
        duration = activity.get("duration_minutes") or 120
        steps.append(
            {
                "order_id": 1,
                "item": _as_itinerary_item(activity),
                "duration_minutes": int(duration),
                "note": "活动优先安排在前段，提升体验感。",
            }
        )
        total += int(duration)

    if restaurant is not None:
        duration = restaurant.get("duration_minutes") or 60
        steps.append(
            {
                "order_id": 2,
                "item": _as_itinerary_item(restaurant),
                "duration_minutes": int(duration),
                "note": "用餐安排在中段，便于补给与休息。",
            }
        )
        total += int(duration)

    if gift_shop is not None:
        duration = gift_shop.get("handoff_minutes") or gift_shop.get("duration_minutes") or 15
        lead_time = gift_shop.get("lead_time_minutes")
        if restaurant is not None:
            destination = restaurant.get("name") or "用餐地点"
        elif activity is not None:
            destination = activity.get("name") or "活动地点"
        else:
            destination = "目的地"

        lead_text = ""
        if lead_time is not None:
            try:
                lead_text = f"提前{int(lead_time)}分钟下单，"
            except Exception:
                lead_text = ""

        steps.append(
            {
                "order_id": 3,
                "item": _as_itinerary_item(gift_shop),
                "duration_minutes": int(duration),
                "note": f"{lead_text}送至{destination}交付，预留{int(duration)}分钟收礼与整理。",
            }
        )
        total += int(duration)

    selected_ids: list[str] = []
    for step in steps:
        item_id = step.get("item", {}).get("id")
        if isinstance(item_id, str) and item_id:
            selected_ids.append(item_id)

    return {
        "plans": [
            {
                "plan_id": "fallback_1",
                "title": "最小可用方案",
                "steps": steps,
                "selected_item_ids": selected_ids,
                "total_duration_minutes": total,
            }
        ],
        "status": "fallback_deterministic",
        "missing_types": [],
    }


def _normalize_and_filter_plans(itinerary: dict, *, allowed_ids: set[str]) -> list[dict]:
    plans_raw = itinerary.get("plans")
    if not isinstance(plans_raw, list):
        return []

    valid: list[dict] = []
    for plan in plans_raw:
        if not isinstance(plan, dict):
            continue

        steps_raw = plan.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            continue

        steps: list[dict] = [s for s in steps_raw if isinstance(s, dict)]
        steps.sort(key=lambda x: x.get("order_id", 0))

        selected_ids: list[str] = []
        total = 0
        present_types: set[str] = set()
        ok = True

        for step in steps:
            item = step.get("item")
            if not isinstance(item, dict):
                ok = False
                break

            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id or item_id not in allowed_ids:
                ok = False
                break

            item_type = item.get("type")
            if isinstance(item_type, str) and item_type:
                present_types.add(item_type)

            duration = step.get("duration_minutes")
            try:
                duration_value = int(duration)
            except Exception:
                duration_value = 0
            if duration_value <= 0:
                ok = False
                break

            total += duration_value
            selected_ids.append(item_id)

        if not ok:
            continue

        if not {"activity", "restaurant", "gift_shop"}.issubset(present_types):
            continue

        plan_out = dict(plan)
        plan_out["steps"] = steps
        plan_out["selected_item_ids"] = selected_ids
        plan_out["total_duration_minutes"] = total
        valid.append(plan_out)

    return valid


def plan_itinerary_node(state: ClosedLoopState) -> ClosedLoopState:
    """
    将 candidates 直接传给 LLM，并用 schema 约束生成初步行程 plans。
    """

    config = get_config()
    LoggerManager.setup(config)

    logger.info("phase=plan_itinerary_node | input=start")

    candidates = state.get("candidates")
    if not isinstance(candidates, dict):
        state["itinerary"] = {
            "plans": [],
            "status": "insufficient_candidates",
            "missing_types": ["restaurant", "activity", "gift_shop"],
        }
        logger.error("phase=plan_itinerary_node | error=candidates_not_dict")
        return state

    processed_steps = candidates.get("processed_steps")
    if processed_steps != ["retrieve_candidates_node", "filter_rank_node"]:
        missing = _missing_types_from_candidates(candidates)
        state["itinerary"] = {
            "plans": [],
            "status": "insufficient_candidates",
            "missing_types": missing or ["restaurant", "activity", "gift_shop"],
        }
        logger.error(
            f"phase=plan_itinerary_node | error=processed_steps_not_ready | processed_steps={processed_steps}"
        )
        return state

    missing = _missing_types_from_candidates(candidates)
    if missing:
        state["itinerary"] = {
            "plans": [],
            "status": "insufficient_candidates",
            "missing_types": missing,
        }
        logger.error(f"phase=plan_itinerary_node | error=missing_candidates | missing={missing}")
        return state

    allowed_ids = _candidate_id_set(candidates)

    constraints = state.get("constraints")
    if hasattr(constraints, "model_dump"):
        constraints_payload = constraints.model_dump()
    elif hasattr(constraints, "dict"):
        constraints_payload = constraints.dict()
    elif isinstance(constraints, dict):
        constraints_payload = constraints
    else:
        constraints_payload = {}

    payload = {
        "constraints": constraints_payload,
        "candidates": {
            "nearby_restaurants": candidates.get("nearby_restaurants", []),
            "nearby_activities": candidates.get("nearby_activities", []),
            "nearby_gifts": candidates.get("nearby_gifts", []),
        },
    }

    agent = build_agent(response_format=ItineraryPlan)

    try:
        response = agent.invoke(
            {
                "messages": [
                    SystemMessage(content=PLAN_ITINERARY_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            }
        )
        parsed_output = response
        if isinstance(response, dict) and "structured_response" in response:
            parsed_output = response["structured_response"]

        if hasattr(parsed_output, "model_dump"):
            itinerary_dict = parsed_output.model_dump()
        elif hasattr(parsed_output, "dict"):
            itinerary_dict = parsed_output.dict()
        elif isinstance(parsed_output, dict):
            itinerary_dict = parsed_output
        else:
            itinerary_dict = {}

        plans = _normalize_and_filter_plans(itinerary_dict, allowed_ids=allowed_ids)
        if plans:
            state["itinerary"] = {
                "plans": plans,
                "status": "ok",
                "missing_types": [],
            }
            logger.info(
                f"phase=plan_itinerary_node | output=status_ok | plans={len(plans)} | first_plan_steps={len(plans[0].get('steps', []))}"
            )
            return state

        state["itinerary"] = _fallback_deterministic(candidates)
        logger.error("phase=plan_itinerary_node | error=invalid_llm_output | fallback=deterministic")
        return state
    except Exception as e:
        logger.error(f"phase=plan_itinerary_node | error=llm_invoke_failed | detail={e}")
        state["itinerary"] = _fallback_deterministic(candidates)
        return state
