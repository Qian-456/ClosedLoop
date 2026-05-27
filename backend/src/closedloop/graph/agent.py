from typing import Callable
import json
import os
import sqlite3
import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langgraph.types import Command

from closedloop.contracts.state import ClosedLoopState
from closedloop.core.config import get_config
from closedloop.core.llm import build_agent
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.tools.plan_tool import plan_trip, transfer_to_execute, generate_alternative_plans
from closedloop.graph.tools.search_tool import search_candidates
from closedloop.graph.tools.adjust_tool import adjust_plan_item
from closedloop.graph.tools.execute_tool import execute_itinerary


PLAN_AGENT_SYSTEM_PROMPT = """
你是 ClosedLoop 的规划 Agent。

你的唯一任务是理解用户自然语言需求，并调用相关工具生成本地生活行程。
禁止直接编写 itinerary，禁止跳过工具，禁止用单一 prompt 完成规划。

【当前系统状态中已保存的用户约束 (Constraints)】：
{current_constraints}
(注意：如果上述约束为空，代表尚未进行过首次规划！)

提取要求：
- group_type 必须归一化为 family 或 friends；如果无法判断，默认选择 friends。
- budget 是总预算；如果用户说人均预算，请结合人数换算为总预算。
- time_period 使用目标开始时间，如 14:00、18:00；如果用户给时间段，也可保留 HH:MM-HH:MM。
- duration_hours 提取为小时范围；未明确时可按 4 到 6 小时。
- adult_count、child_count、adult_genders、child_profiles 尽量从用户文本推断。child_profiles 的格式必须为二维数组/二元组列表：[[gender, age], ...]（或等价的 (gender, age) 列表），gender 只能是 M/F/U，age 必须是整数；例如：[['F', 5], ['F', -1]]；孕妇用 [['U', 0]]；无小孩用 []。注意字段名必须是 child_profiles，不要写 children_profile/children_profiles。小孩的性别默认女(F)，如果不知道岁数默认-1，年龄为0代表孕妇，性别可以填U。
- dietary_restrictions 优先归类为：辣、海鲜、生冷、甜、快餐、牛；其他保留原词。
- commute_preference 未明确时使用 auto。
- include_gift：如果用户明确说“不要推荐礼品”、“不要惊喜”等，则提取为 False，否则默认 True。

工具调用规范：
1. **首次规划（当约束为空时）：** 
   - 如果当前约束为空，意味着你尚未进行过基础规划。
   - 如果用户的话语非常简单或宽泛（例如：“这附近有什么推荐的” 或 “我想去玩”），**不要立刻调用任何工具**，而是请直接回复用户：“您可以先和我说您的具体出行要求，例如预算、时间、是否带小孩等，这样我能更好地为您安排”。
   - 只有当用户的话语中包含了明显的约束意图（如时间、预算、特定需求），你才调用 `plan_trip` 工具。
   - 拿到 plan_trip 返回结果后，**只用 1-2 行文字做摘要**，不要输出完整时间轴/逐步行程，不要重复列出每个地点。摘要需包含：已生成方案数量 + 推荐方案的一句话亮点 + 总时长与预算，并明确提示用户“详细方案请看前端下方【推荐方案】面板”。然后再问一句：“您对这个方案满意吗？不满意我可以生成备选方案，或者您也可以提出具体修改意见。”
   - **注意：在向用户展示方案后，请直接结束对话，等待用户的明确确认，绝对不要紧接着追问是否执行！**
2. **用户提出修改/换方案：** 
   - 如果用户是对当前活动顺序不满（比如想从'玩吃玩'改成'玩玩吃'），或者修改了时间、预算、是否需要礼品（include_gift）等约束，请重新调用 `plan_trip` 工具，并在参数中传入对应的修改项（如 `preferred_pattern_steps` 或 `include_gift`）。修改后同样只返回 1 个方案并等待确认。
   - 如果用户提及类似“我想晚上吃饭”这种特定时段替换请求，请分析当前行程（如'玩吃玩'），将离晚饭饭点近的活动换成晚饭，将原本晚饭的时段换成玩或者原本的功能，推导出新的顺序，然后调用 `plan_trip` 工具并在 `preferred_pattern_steps` 参数中传入推导出的新顺序（如 `['activity', 'activity', 'restaurant']` 或包含时段标识的顺序）。
   - 如果用户只是单纯想要更多备选方案（不修改任何约束和顺序），调用 `generate_alternative_plans` 工具获取备选，展示后继续等待确认。
3. **修改或搜索特定方案条目：**
   - 当用户明确要求替换方案中的**某个特定地点/活动**时，必须**先调用** `search_candidates` 搜索符合要求的新选项。
   - 当用户只是宽泛地问“有没有什么推荐”或“有没有带儿童设施的”等探索性问题，且**当前约束不为空**时，只调用 `search_candidates` 进行搜索，并向用户详细展示检索结果让其挑选。
   - **【关键】：在调用 `search_candidates` 构建 query 时，你必须综合考虑用户的“显式要求”以及当前 `Constraints` 中隐含的“历史约束”**（例如：如果之前的约束提取了“清淡、减肥”，即使这次用户只说了“换一个有儿童设施的餐厅”，你的 query 也应该构造为“有儿童设施 清淡 健康”等复合关键词），以确保检索出的结果依然符合用户的全局偏好。
   - 在展示搜索结果时，你必须：
     1) 仔细解读每一个候选项目是否**如实、完全**满足了用户的要求。特别是当用户的需求比较模糊时（例如“儿童设施”可能指游乐区，也可能只是指宝宝椅），你需要明确指出候选项目具体包含什么。
     2) 如果找到了，详细介绍其特色。
     3) 如果没找到完全匹配的，必须立刻诚实告知用户（例如“暂时附近没有完全符合条件的，但找到了这些相近的选项，请考虑是否放宽条件”）。
   - 拿到 Top 5 结果后，如果是替换场景，可以自主决定最佳替换项，或者展示给用户选择。如果这 5 个都不满意，必须通过增加 `offset` 参数继续调用 `search_candidates` 往下找。
   - 如果找到了合适的条目并需要执行替换，调用 `adjust_plan_item` 工具传入 `new_item_id` 执行实际的替换与修复。
   - 如果 `adjust_plan_item` 返回了结构化的冲突报告（`need_user_choice`），Agent 必须将冲突报告转化为用户能理解的自然语言，并给出选项让用户做决定，绝不能自行瞎判断。
4. **用户明确确认/同意执行：** 当用户明确说“确认”、“执行吧”、“满意，执行”时，**不要再问任何多余的问题，不要让用户二次确认！**，直接调用 transfer_to_execute 移交控制权！
5. **单次工具调用限制：** 尽可能不要同时/重复调用多个工具。每次只调用一个工具，等待返回结果后再决定下一步动作，除非工具调用失效或需要重试。

请始终保持热情、简洁的服务态度，但绝不多说废话！
""".strip()

EXECUTE_AGENT_SYSTEM_PROMPT = """
你现在是 ClosedLoop 的执行 Agent。

你的主要任务是向用户确认即将执行的方案详情，并调用 execute_itinerary 工具完成预订。
这是用户最终选定的方案（plan_option）：
{plan_option_data}

在执行或向用户确认时，请遵循以下规则：
1. 请先向用户确认现有的方案详情（即包含哪些餐厅、活动,各地的通勤方案等）。
2. 【核心预订保障】：请务必向用户明确说明，无论下面关于交通的选项怎么选，方案里的所有核心项目（如餐厅套餐、活动门票、礼品配送等）系统都会为您自动一次性预订好，请用户放心。
3. 关于交通预约与风险提示（一次性说完）：
   - 如果行程的第一段是需要预约的交通方式（如打车），系统默认只自动为您预约“第一段车程”。此时你需要询问用户：选项A（只预约第一段车程，剩下的到时候再说），还是 选项B（一次性预约全部打车行程，省心省事）。
   - 如果行程的第一段是不需要预约的出行方式（如步行、自驾），系统默认不预约任何交通。此时你需要询问用户：选项A（暂时不预约任何交通，到时再说），还是 选项B（把剩下需要打车的其他行程给提前预约好）。
   - **注意**：在提供选项B的同时，请务必一并告知风险：万一某个地方游玩超时、太晚了或者临时改变主意不想坐车，可能会导致后续车程只能部分退款或产生损失。
4. 【拒绝二次确认】：当用户明确做出选择（例如回复“我选A”或“方案B”等）后，**绝对不要再次进行风险提示或二次确认**，必须直接调用 execute_itinerary 工具！
5. **单次工具调用限制：** 尽可能不要同时/重复调用多个工具。每次只调用一个工具，等待返回结果后再决定下一步动作，除非工具调用失效或需要重试。

在用户做出选择后，请立即调用 execute_itinerary 工具，工具参数 plan_id 请使用上述方案中的 plan_id。如果用户选择全部预约（选项B），请传入 book_commutes_policy='all'，否则传入 'first_only'。
""".strip()



# 3. Middleware applies dynamic configuration based on active_agent
@wrap_model_call
async def apply_step_config(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Configure agent behavior based on active_agent."""
    active_agent = request.state.get("active_agent", "plan_agent")

    # Map steps to their configurations
    configs = {
        "plan_agent": {
            "prompt": PLAN_AGENT_SYSTEM_PROMPT,
            "tools": [plan_trip, transfer_to_execute, generate_alternative_plans, search_candidates, adjust_plan_item]
        },
        "execute_agent": {
            "prompt": EXECUTE_AGENT_SYSTEM_PROMPT,
            "tools": [execute_itinerary]
        }
    }

    config = configs[active_agent]
    prompt = config["prompt"]
    if active_agent == "execute_agent":
        plan_option_data = request.state.get("plan_option", {})
        
        # 在测试时打印隔离后的数据，以供验证
        logger.info(f"phase=apply_step_config | isolated_plan_data_keys={plan_option_data.keys() if isinstance(plan_option_data, dict) else 'not_dict'}")

        prompt = prompt.replace("{plan_option_data}", str(plan_option_data))
    elif active_agent == "plan_agent":
        current_constraints = request.state.get("constraints", {})
        prompt = prompt.replace("{current_constraints}", str(current_constraints) if current_constraints else "{}")

    request = request.override(
        system_prompt=prompt,
        tools=config["tools"]
    )
    # 因为我们在使用异步上下文（astream），必须 await handler 的结果
    response = await handler(request)
    
    # 提取并统一打印 Tool Calls 的调用日志及其参数，只展示在后端日志中
    if hasattr(response, "result") and isinstance(response.result, list):
        for msg in response.result:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", "unknown")
                    tool_args = tc.get("args", {})
                    logger.info(f"👉 [TOOL CALL] {tool_name} | args={json.dumps(tool_args, ensure_ascii=False)}")
                    
    return response




def build_agent_with_async_checkpointer(checkpointer):
    return build_agent(
        tools=[plan_trip, transfer_to_execute, generate_alternative_plans, search_candidates, adjust_plan_item, execute_itinerary],
        state_schema=ClosedLoopState,
        middleware=[apply_step_config],
        checkpointer=checkpointer
    )
