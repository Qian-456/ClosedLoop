import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock

from closedloop.contracts.state import AgentState
from closedloop.graph.nodes.extract import extract_constraints

class TestExtractConstraints(unittest.TestCase):
    """
    Test cases for the extract_constraints node.
    """

    @patch("closedloop.graph.nodes.extract.build_agent")
    def test_extract_constraints_family_legacy_fields_removed(self, mock_build_agent):
        """
        Test constraints extraction uses only supported fields.
        """
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "group_type": "family",
            "adult_count": 2,
            "child_count": 1,
            "child_ages": [5],
            "budget": 500.0,
            "dietary_restrictions": ["no spicy"],
            "preferred_distance": "2km-5km",
            "time_period": "13:00-18:00",
            "duration_hours": 5.0,
            "activity_preferences": ["play"]
        }
        mock_build_agent.return_value = mock_agent

        state: AgentState = {
            "user_input": "2大1小下午出去玩，预算500，孩子5岁，不吃辣",
            "constraints": {},
            "itinerary": {},
            "confirmation": {},
            "current_step_id": None
        }

        new_state = extract_constraints(state)

        # Assertions
        self.assertIn("constraints", new_state)
        constraints = new_state["constraints"]
        expected_keys = {
            "group_type",
            "adult_count",
            "child_count",
            "child_ages",
            "budget",
            "dietary_restrictions",
            "preferred_distance",
            "time_period",
            "duration_hours",
            "activity_preferences",
        }
        self.assertEqual(set(constraints.keys()), expected_keys)
        self.assertEqual(constraints["group_type"], "family")
        self.assertEqual(constraints["budget"], 500.0)
        self.assertEqual(constraints["adult_count"], 2)
        self.assertEqual(constraints["child_count"], 1)
        self.assertEqual(constraints["child_ages"], [5])
        self.assertEqual(constraints["preferred_distance"], "2km-5km")
        self.assertEqual(constraints["time_period"], "13:00-18:00")
        self.assertEqual(constraints["duration_hours"], 5.0)
        self.assertEqual(constraints["activity_preferences"], ["play"])
        self.assertEqual(constraints["dietary_restrictions"], ["no spicy"])

        # Ensure the agent was called with the user input
        mock_agent.invoke.assert_called_once()
        args, kwargs = mock_agent.invoke.call_args
        self.assertIn("2大1小下午出去玩", str(args[0] if args else kwargs.get('input', '')))

    @patch("closedloop.graph.nodes.extract.build_agent")
    def test_extract_constraints_family_multi_children(self, mock_build_agent):
        """
        Test extracting constraints for a family with multiple children ages.
        """
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "group_type": "family",
            "adult_count": 3,
            "child_count": 2,
            "child_ages": [5, 8],
            "budget": 500.0,
            "dietary_restrictions": ["no spicy"],
            "preferred_distance": "2km-5km",
            "time_period": "13:00-18:00",
            "duration_hours": 5.0,
            "activity_preferences": ["play"]
        }
        mock_build_agent.return_value = mock_agent

        state: AgentState = {
            "user_input": "3大2小（5岁、8岁）下午出去玩，预算500，不吃辣",
            "constraints": {},
            "itinerary": {},
            "confirmation": {},
            "current_step_id": None,
        }

        new_state = extract_constraints(state)
        constraints = new_state["constraints"]
        expected_keys = {
            "group_type",
            "adult_count",
            "child_count",
            "child_ages",
            "budget",
            "dietary_restrictions",
            "preferred_distance",
            "time_period",
            "duration_hours",
            "activity_preferences",
        }
        self.assertEqual(set(constraints.keys()), expected_keys)
        self.assertEqual(constraints["adult_count"], 3)
        self.assertEqual(constraints["child_count"], 2)
        self.assertEqual(constraints["child_ages"], [5, 8])


    @patch("closedloop.graph.nodes.extract.build_agent")
    def test_extract_constraints_friends_default_distance(self, mock_build_agent):
        """
        Test extracting constraints for friends, verifying default distance.
        """
        # Mock the agent's invoke response directly matching the schema format returned by structured output
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "group_type": "friends",
            "adult_count": 2,
            "child_count": 0,
            "child_ages": [],
            "budget": 800.0,
            "dietary_restrictions": [],
            "preferred_distance": "2km-5km",
            "time_period": "18:00-21:00",
            "duration_hours": 3.0,
            "activity_preferences": ["dining"]
        }
        mock_build_agent.return_value = mock_agent

        state: AgentState = {
            "user_input": "朋友聚餐，晚上，预算800",
            "constraints": {},
            "itinerary": {},
            "confirmation": {},
            "current_step_id": None
        }

        new_state = extract_constraints(state)

        # Assertions
        constraints = new_state["constraints"]
        expected_keys = {
            "group_type",
            "adult_count",
            "child_count",
            "child_ages",
            "budget",
            "dietary_restrictions",
            "preferred_distance",
            "time_period",
            "duration_hours",
            "activity_preferences",
        }
        self.assertEqual(set(constraints.keys()), expected_keys)
        self.assertEqual(constraints["group_type"], "friends")
        self.assertEqual(constraints["budget"], 800.0)
        self.assertEqual(constraints["adult_count"], 2)
        self.assertEqual(constraints["child_count"], 0)
        self.assertEqual(constraints["child_ages"], [])
        self.assertEqual(constraints["preferred_distance"], "2km-5km")
        self.assertEqual(constraints["time_period"], "18:00-21:00")
        self.assertEqual(constraints["duration_hours"], 3.0)
        self.assertEqual(constraints["activity_preferences"], ["dining"])


    @patch("closedloop.graph.nodes.extract.build_agent")
    def test_extract_constraints_no_budget_default(self, mock_build_agent):
        """
        Test extracting constraints when budget is not mentioned.
        """
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "group_type": "friends",
            "adult_count": 2,
            "child_count": 0,
            "child_ages": [],
            "budget": 200.0,
            "dietary_restrictions": [],
            "preferred_distance": "2km-5km",
            "time_period": "18:00-21:00",
            "duration_hours": 3.0,
            "activity_preferences": ["dining"]
        }
        mock_build_agent.return_value = mock_agent

        state: AgentState = {
            "user_input": "朋友两人晚上聚餐",
            "constraints": {},
            "itinerary": {},
            "confirmation": {},
            "current_step_id": None
        }

        new_state = extract_constraints(state)

        # Assertions
        constraints = new_state["constraints"]
        self.assertEqual(constraints["budget"], 200.0)

    @patch("closedloop.graph.nodes.extract.build_agent")
    def test_extract_constraints_nearby_and_walk(self, mock_build_agent):
        """
        Test extracting constraints when nearby and walking are mentioned.
        """
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "group_type": "friends",
            "adult_count": 2,
            "child_count": 0,
            "child_ages": [],
            "budget": 200.0,
            "dietary_restrictions": [],
            "preferred_distance": "<2km",
            "time_period": "18:00-21:00",
            "duration_hours": 3.0,
            "activity_preferences": ["dining"]
        }
        mock_build_agent.return_value = mock_agent

        state: AgentState = {
            "user_input": "朋友两人晚上聚餐，就近走走",
            "constraints": {},
            "itinerary": {},
            "confirmation": {},
            "current_step_id": None
        }

        new_state = extract_constraints(state)

        # Assertions
        constraints = new_state["constraints"]
        self.assertEqual(constraints["preferred_distance"], "<2km")


if __name__ == "__main__":
    unittest.main()
