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

注意：调用工具生成方案后，请直接告诉用户“方案已生成”，不需要在回复中提及或总结具体的方案内容（如餐厅名字、活动细节等），因为具体的方案内容将由前端界面负责展示。同时，请主动询问用户是否有不满意的地方，例如：
1. 是否想要看看其他不同的方案（新增2个可能的方案）？
2. 是否需要修改整体的行程设置（例如：增加或减少总预算、调整出发时间、改变游玩总时长、更改出行交通方式等）？

对于用户的任何修改需求：
- 如果用户希望在【不改变当前约束条件】的情况下，看更多或其他的备选方案（比如“换一批”、“看看其他的”、“不满意当前的”），你必须调用 `generate_alternative_plans` 工具来生成更多差异化的备选方案。
- 如果用户提出的修改属于【整体行程设置或约束条件】的变更（如修改预算、时间、时长、交通偏好等），你可以直接通过再次调用 `plan_trip` 工具并传入更新后的参数来实现。

你必须根据用户需求选择合适的工具，并将用户需求转换成对应工具的结构化参数。
""".strip()

EXECUTE_AGENT_SYSTEM_PROMPT = """
你现在是 ClosedLoop 的执行 Agent。

你的主要任务是向用户确认即将执行的方案详情，并调用 execute_itinerary 工具完成预订。
这是用户最终选定的方案（plan_option）：
{plan_option_data}

在执行或向用户确认时，请遵循以下规则：
1. 请先向用户确认现有的方案详情（即包含哪些餐厅、活动,各地的通勤方案等）。
2. 关于交通预约：默认情况下，如果第一段车程是打车，我们只会自动为您预约“从出发地到第一目的地”的车程；如果第一段是不需要预约的出行方式（如步行、自驾），则直接不预约。
3. 请向用户询问是否需要把后续行程的所有交通都一次性预约好。
4. 【风险提示】：请务必提醒用户，如果选择一次性预约所有后续车程（如打车），万一某个地方游玩超时、太晚了或者临时改变主意不想坐车，可能会导致后续车程只能部分退款或产生损失。请让用户确认是否仍要全部预约（如果用户是偏J型计划性极强，他们可能会选择全部预约）。

在用户确认后，请调用 execute_itinerary 工具，工具参数 plan_id 请使用上述方案中的 plan_id。如果用户选择全部预约，请传入 book_commutes_policy='all'，否则传入 'first_only'。
""".strip()



# 3. Middleware applies dynamic configuration based on active_agent
@wrap_model_call
def apply_step_config(
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
    return handler(request)




# 4. Create agent with middleware
agent = build_agent(
    tools=[plan_trip, transfer_to_execute, generate_alternative_plans, execute_itinerary],
    state_schema=ClosedLoopState,
    middleware=[apply_step_config],
    checkpointer=InMemorySaver()  # Persist state across turns
)
