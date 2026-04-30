import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.prompts.plan import (
    PLAN_ITINERARY_SYSTEM_PROMPT,
    build_plan_itinerary_system_prompt,
)


class TestPlanPromptCompiler(unittest.TestCase):
    def test_build_plan_prompt_includes_schema_constraints(self):
        prompt = build_plan_itinerary_system_prompt(
            {
                "budget": 500,
                "duration_hours": 5,
                "time_period": "13:00-18:00",
                "preferred_distance": "<2km",
                "dietary_restrictions": ["no_spicy"],
                "group_type": "family",
                "adult_count": 2,
                "child_count": 1,
                "child_ages": [5],
                "activity_preferences": ["kid_friendly"],
            }
        )

        self.assertIn("只输出", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("status", prompt)
        self.assertIn("ok", prompt)
        self.assertIn("insufficient_candidates", prompt)
        self.assertIn("fallback_deterministic", prompt)
        self.assertIn("plan_id", prompt)
        self.assertIn("plan_1", prompt)
        self.assertIn("title", prompt)

    def test_build_plan_prompt_compiles_budget_and_duration_targets(self):
        prompt = build_plan_itinerary_system_prompt(
            {
                "budget": 500,
                "duration_hours": 5,
                "time_period": "13:00-18:00",
                "preferred_distance": "2km-5km",
            }
        )

        self.assertIn("目标总时长", prompt)
        self.assertIn("300", prompt)
        self.assertIn("270", prompt)
        self.assertIn("预算", prompt)
        self.assertIn("500", prompt)
        self.assertIn("400", prompt)
        self.assertIn("13:00-18:00", prompt)
        self.assertIn("优先级", prompt)

    def test_build_plan_prompt_empty_constraints_returns_base_prompt(self):
        prompt = build_plan_itinerary_system_prompt({})
        self.assertEqual(prompt, PLAN_ITINERARY_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()

