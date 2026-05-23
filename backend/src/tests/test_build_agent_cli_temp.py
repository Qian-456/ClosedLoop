import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.graph.build import build_graph


DEFAULT_USER_INPUT = "周六下午一家三口出去玩，预算600，别太累，最好有吃饭和适合小孩的活动。"


def _plan_display_name(plan: dict, index: int) -> str:
    """从 itinerary plan 中提取可读名称。"""
    return str(plan.get("name") or plan.get("title") or plan.get("plan_name") or f"plan_{index}")


def run_cli_smoke(user_input: str = DEFAULT_USER_INPUT) -> dict:
    """临时 CLI 冒烟测试：调用当前 build_graph 并输出前三个方案名称。"""
    config = get_config()
    LoggerManager.setup(config)

    graph = build_graph()
    final_state = graph.invoke({"user_input": user_input})
    itinerary = final_state.get("itinerary") or final_state.get("latest_plan_result") or {}
    plans = itinerary.get("plans", []) if isinstance(itinerary, dict) else []

    sys.stdout.write("ClosedLoop plan names:\n")
    for index, plan in enumerate(plans[:3], start=1):
        sys.stdout.write(f"{index}. {_plan_display_name(plan, index)}\n")

    if len(plans) < 3:
        logger.warning(f"phase=temp_cli_build_agent | result=plans_less_than_3 | count={len(plans)}")
    else:
        logger.info(f"phase=temp_cli_build_agent | result=ok | count={len(plans[:3])}")

    return final_state


@unittest.skip("临时 CLI 测试不参与自动 discover；请直接运行本文件。")
class TestBuildAgentCliTemp(unittest.TestCase):
    def test_run_cli_smoke(self):
        state = run_cli_smoke()
        plans = state.get("itinerary", {}).get("plans", [])
        self.assertGreaterEqual(len(plans), 3)


if __name__ == "__main__":
    user_text = " ".join(sys.argv[1:]).strip() or DEFAULT_USER_INPUT
    run_cli_smoke(user_text)
