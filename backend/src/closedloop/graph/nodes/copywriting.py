from __future__ import annotations

import json
from typing import Any

from langchain.messages import HumanMessage, SystemMessage

from closedloop.core.config import get_config
from closedloop.core.llm import build_agent
from closedloop.core.logger import LoggerManager, logger
from closedloop.contracts.copywriting import ThreePlansCopywriting
from closedloop.contracts.state import PlanState
from closedloop.graph.prompts.copywriting import COPYWRITING_SYSTEM_PROMPT


def _parse_start_minutes(time_period: Any) -> int:
    if not isinstance(time_period, str) or not time_period.strip():
        return 14 * 60
    s = time_period.strip()
    if "-" in s:
        s = s.split("-", 1)[0].strip()
    if ":" not in s:
        return 14 * 60
    hh, mm = s.split(":", 1)
    try:
        h = int(hh)
        m = int(mm)
    except Exception:
        return 14 * 60
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return h * 60 + m


def _format_hhmm(total_minutes: int) -> str:
    m = total_minutes % (24 * 60)
    hh = m // 60
    mm = m % 60
    return f"{hh:02d}:{mm:02d}"


def _build_plan_info(plan: dict, *, start_minutes: int) -> dict[str, Any]:
    steps = plan.get("steps") or []
    if not isinstance(steps, list):
        steps = []

    t = int(start_minutes)
    items: list[str] = []
    type_sequence: list[str] = []
    non_commute_steps = 0
    commute_segments = 0
    estimated_commute_minutes = 0
    has_gift = False
    activity_count = 0

    for step in steps:
        if not isinstance(step, dict):
            continue
        dur = step.get("duration_minutes")
        try:
            dur_i = int(dur)
        except Exception:
            dur_i = 0
        item = step.get("item") or {}
        if not isinstance(item, dict):
            item = {}
        item_type = item.get("type")
        name = item.get("name", "未知项目")

        start = _format_hhmm(t)
        end = _format_hhmm(t + max(0, dur_i))

        if item_type == "commute":
            commute_segments += 1
            estimated_commute_minutes += max(0, dur_i)
        else:
            non_commute_steps += 1
            if isinstance(item_type, str):
                type_sequence.append(item_type)
            if item_type == "gift_shop":
                has_gift = True
            if item_type == "activity":
                activity_count += 1
            items.append(f"{start}-{end} {name}")

        t += max(0, dur_i)

    total_price = plan.get("total_cost", 0.0)
    total_duration = plan.get("total_duration_minutes", 0)

    return {
        "type_sequence": type_sequence,
        "items": items,
        "total_price": total_price,
        "total_duration_minutes": total_duration,
        "facts": {
            "non_commute_steps": non_commute_steps,
            "commute_segments": commute_segments,
            "estimated_commute_minutes": estimated_commute_minutes,
            "has_gift": has_gift,
            "activity_count": activity_count,
        },
    }


def _fallback_plan_copywriting(
    *,
    role: str,
    group_type: str,
    plan_info: dict[str, Any],
) -> dict[str, Any]:
    facts = plan_info.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}

    non_commute_steps = int(facts.get("non_commute_steps") or 0)
    commute_minutes = int(facts.get("estimated_commute_minutes") or 0)
    has_gift = bool(facts.get("has_gift"))
    activity_count = int(facts.get("activity_count") or 0)
    total_price = plan_info.get("total_price")
    total_duration = plan_info.get("total_duration_minutes")

    if role == "plan_1":
        plan_name = "省钱轻装版"
    elif role == "plan_2":
        if group_type in ("solo", "couple"):
            plan_name = "松弛刚刚好"
        elif group_type == "friends":
            plan_name = "好玩不折腾"
        elif group_type == "business":
            plan_name = "体面稳妥版"
        else:
            plan_name = "省心平衡版"
    else:
        plan_name = "高配丰富版"

    pros_cons: list[str] = []

    if role == "plan_1":
        if isinstance(total_price, (int, float)):
            pros_cons.append(f"✔ 总价约{int(total_price)}元更省")
        else:
            pros_cons.append("✔ 总价更低更省预算")
        if activity_count <= 1:
            pros_cons.append("✘ 活动偏少更偏轻量")
        else:
            pros_cons.append("✘ 节奏偏紧舒适度一般")
    elif role == "plan_2":
        if group_type == "friends":
            pros_cons.append("✔ 玩法更集中更好一起玩")
        elif group_type == "business":
            pros_cons.append("✔ 体验更稳妥更体面")
        elif group_type in ("solo", "couple"):
            pros_cons.append("✔ 节奏不赶更松弛舒服")
        else:
            pros_cons.append("✔ 节奏更平衡更省心")
        if commute_minutes >= 30:
            pros_cons.append(f"✘ 路上约{commute_minutes}分钟")
        else:
            pros_cons.append("✘ 花费比省钱款略高")
    else:
        if activity_count >= 2:
            pros_cons.append("✔ 内容更丰富体验更满")
        else:
            pros_cons.append("✔ 质量更高更有氛围")
        if has_gift:
            pros_cons.append("✔ 还能顺路带个伴手礼")
        else:
            pros_cons.append("✘ 预算更高更费钱包")

        if commute_minutes > 0 and not any(s.startswith("✘") for s in pros_cons):
            pros_cons.append(f"✘ 通勤约{commute_minutes}分钟")
        elif commute_minutes > 0 and any(s.startswith("✘") for s in pros_cons):
            pass
        elif not any(s.startswith("✘") for s in pros_cons):
            pros_cons.append("✘ 行程更满体力要跟上")

    if len(pros_cons) > 3:
        pros_cons = pros_cons[:3]
    if len(pros_cons) < 2:
        pros_cons = (pros_cons + ["✘ 体验取舍需要接受"])[:2]

    if role == "plan_1":
        reminder = "如果你就想省点钱、别太折腾，这套挺合适。\n到现场就按感觉走，别硬赶进度。"
    elif role == "plan_2":
        reminder = "这套属于玩得尽兴但不累的节奏。\n建议提前留点弹性，看到喜欢的就多待会。"
    else:
        reminder = "这套更像“把一天的好都装进去”，体验会很满。\n注意中间留点休息，不然容易越玩越累。"

    if isinstance(total_duration, (int, float)) and int(total_duration) > 0:
        reminder = reminder + f"\n总时长大概 {int(total_duration)} 分钟，记得留机动时间。"

    return {"plan_name": plan_name, "pros_cons": pros_cons, "ai_reminder": reminder}


def _fallback_copywriting(constraints: dict, itinerary: dict) -> dict[str, Any]:
    group_type = "family"
    if isinstance(constraints, dict):
        v = constraints.get("group_type")
        if isinstance(v, str):
            group_type = v

    plans = itinerary.get("plans") or []
    if not isinstance(plans, list):
        plans = []

    start_minutes = _parse_start_minutes(constraints.get("time_period") if isinstance(constraints, dict) else None)

    plan_infos = []
    for p in plans[:3]:
        if isinstance(p, dict):
            plan_infos.append(_build_plan_info(p, start_minutes=start_minutes))

    while len(plan_infos) < 3:
        plan_infos.append({"type_sequence": [], "items": [], "total_price": 0.0, "total_duration_minutes": 0, "facts": {}})

    return {
        "status": "fallback_rules",
        "plans": {
            "plan_1": _fallback_plan_copywriting(role="plan_1", group_type=group_type, plan_info=plan_infos[0]),
            "plan_2": _fallback_plan_copywriting(role="plan_2", group_type=group_type, plan_info=plan_infos[1]),
            "plan_3": _fallback_plan_copywriting(role="plan_3", group_type=group_type, plan_info=plan_infos[2]),
        },
    }


def copywriting_node(state: PlanState) -> PlanState:
    """Generate human-friendly copywriting for the three plans."""

    config = get_config()
    LoggerManager.setup(config)

    itinerary = state.get("itinerary") or {}
    if not isinstance(itinerary, dict):
        itinerary = {}

    status = itinerary.get("status")
    plans = itinerary.get("plans") or []

    if status != "ok" or not isinstance(plans, list) or len(plans) != 3:
        state["confirmation"] = {
            "status": "skipped",
            "reason": f"itinerary_not_ready status={status} plans={len(plans) if isinstance(plans, list) else 0}",
            "plans": {},
        }
        return state

    constraints = state.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}

    user_prompt = state.get("user_input", "")
    if not isinstance(user_prompt, str):
        user_prompt = str(user_prompt)

    group_type = constraints.get("group_type", "family")
    if not isinstance(group_type, str):
        group_type = "family"

    start_minutes = _parse_start_minutes(constraints.get("time_period"))
    plan_1_info = _build_plan_info(plans[0], start_minutes=start_minutes)
    plan_2_info = _build_plan_info(plans[1], start_minutes=start_minutes)
    plan_3_info = _build_plan_info(plans[2], start_minutes=start_minutes)

    human_payload = {
        "user_prompt": user_prompt,
        "group_type": group_type,
        "plan_1": plan_1_info,
        "plan_2": plan_2_info,
        "plan_3": plan_3_info,
    }

    logger.info(
        f"phase=copywriting_node | status=started | group_type={group_type} | p1_cost={plan_1_info.get('total_price')} | p2_cost={plan_2_info.get('total_price')} | p3_cost={plan_3_info.get('total_price')}"
    )

    agent = build_agent(response_format=ThreePlansCopywriting)

    try:
        response = agent.invoke(
            {
                "messages": [
                    SystemMessage(content=COPYWRITING_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(human_payload, ensure_ascii=False)),
                ]
            }
        )

        parsed_output: Any = response
        if isinstance(response, dict) and "structured_response" in response:
            parsed_output = response["structured_response"]

        if isinstance(parsed_output, ThreePlansCopywriting):
            obj = parsed_output
        elif hasattr(ThreePlansCopywriting, "model_validate"):
            obj = ThreePlansCopywriting.model_validate(parsed_output)
        else:
            obj = ThreePlansCopywriting.parse_obj(parsed_output)

        state["confirmation"] = {"status": "ok", "plans": obj.model_dump()}
        processed_steps = state.setdefault("processed_steps", [])
        processed_steps.append("copywriting_node")
        logger.info("phase=copywriting_node | status=ok")
        return state
    except Exception as e:
        logger.error(f"phase=copywriting_node | status=fallback_rules | error={e}")
        state["confirmation"] = _fallback_copywriting(constraints, itinerary)
        processed_steps = state.setdefault("processed_steps", [])
        processed_steps.append("copywriting_node")
        return state
