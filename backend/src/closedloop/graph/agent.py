from typing import Callable
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langgraph.types import Command

from closedloop.contracts.state import ClosedLoopState
from closedloop.core.config import get_config
from closedloop.core.llm import build_agent
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.tools.plan_tool import plan_trip, transfer_to_execute, generate_alternative_plans
from closedloop.graph.tools.execute_tool import execute_itinerary


PLAN_AGENT_SYSTEM_PROMPT = """
你是 ClosedLoop 的规划 Agent。

你的唯一任务是理解用户自然语言需求，并调用相关工具生成本地生活行程。
禁止直接编写 itinerary，禁止跳过工具，禁止用单一 prompt 完成规划。

提取要求：
- group_type 必须归一化为 family 或 friends；如果无法判断，默认选择 friends。
- budget 是总预算；如果用户说人均预算，请结合人数换算为总预算。
- time_period 使用目标开始时间，如 14:00、18:00；如果用户给时间段，也可保留 HH:MM-HH:MM。
- duration_hours 提取为小时范围；未明确时可按 4 到 6 小时。
- adult_count、child_count、adult_genders、child_profiles 尽量从用户文本推断。
- dietary_restrictions 优先归类为：辣、海鲜、生冷、甜、快餐、牛；其他保留原词。
- commute_preference 未明确时使用 auto。

工具调用规范：
1. **第一次对话：** 你必须提取参数并调用 plan_trip 工具。拿到工具返回结果后，直接使用 Markdown 总结推荐的行程（重点突出时间、总花费、关键节点等），并主动问用户：“请问您对这个方案满意吗？如果不满意我可以生成备选方案，或者您可以提出具体修改意见。”
   **注意：在向用户展示方案后，请直接结束对话，等待用户的明确确认，绝对不要紧接着追问是否执行！**
2. **用户提出修改/换方案：** 调用 generate_alternative_plans 工具获取备选，展示后继续等待确认。
3. **用户明确确认/同意执行：** 当用户明确说“确认”、“执行吧”、“满意，执行”时，**不要再问任何多余的问题，不要让用户二次确认！**，直接调用 transfer_to_execute 移交控制权！

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
3. 关于交通预约：
   - 如果行程的第一段是需要预约的交通方式（如打车），系统默认只自动为您预约“第一段车程”。此时你需要询问用户：选项A（只预约第一段车程，剩下的到时候再说），还是 选项B（一次性预约全部打车行程，省心省事）。
   - 如果行程的第一段是不需要预约的出行方式（如步行、自驾），系统默认不预约任何交通。此时你需要询问用户：选项A（暂时不预约任何交通，到时再说），还是 选项B（把剩下需要打车的其他行程给提前预约好）。
4. 【风险提示】：只要用户选择了选项B（一次性预约后续车程），请务必提醒用户：万一某个地方游玩超时、太晚了或者临时改变主意不想坐车，可能会导致后续车程只能部分退款或产生损失。请让用户确认是否仍要全部预约（偏J型计划性极强的人可能会选择全部预约）。

在用户确认后，请调用 execute_itinerary 工具，工具参数 plan_id 请使用上述方案中的 plan_id。如果用户选择全部预约（选项B），请传入 book_commutes_policy='all'，否则传入 'first_only'。
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
            "tools": [plan_trip, transfer_to_execute, generate_alternative_plans]
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

        prompt = prompt.format(
            plan_option_data=plan_option_data
        )

    request = request.override(
        system_prompt=prompt,
        tools=config["tools"]
    )
    # 因为我们在使用异步上下文（astream），必须 await handler 的结果
    return await handler(request)




# 4. Create agent with middleware
agent = build_agent(
    tools=[plan_trip, transfer_to_execute, generate_alternative_plans, execute_itinerary],
    state_schema=ClosedLoopState,
    middleware=[apply_step_config],
    checkpointer=InMemorySaver()  # Persist state across turns
)
