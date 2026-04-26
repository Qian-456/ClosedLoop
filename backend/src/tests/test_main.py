import sys
import os
# Add src to path so we can import from core and main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

class TestMainAPI(unittest.TestCase):
    """
    Test cases for the FastAPI application main.py
    """
    def test_health_check(self):
        """
        Test the health check endpoint.
        """
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("project", data)

    @patch("main.workflow_app.invoke")
    def test_invoke_graph(self, mock_invoke):
        """
        Test the invoke graph endpoint with a mock graph response.
        """
        # Mock what the graph would return
        mock_invoke.return_value = {
            "user_input": "一家三口出去玩",
            "constraints": {
                "group_type": "family",
                "budget": 500.0,
                "time_period": "afternoon",
                "preferred_distance": "2km-5km",
                "dietary_restrictions": [],
                "child_age": 5
            }
        }

        # Make the request
        response = client.post("/invoke", json={"user_input": "一家三口出去玩"})
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("state", data)
        self.assertIn("constraints", data["state"])
        self.assertEqual(data["state"]["constraints"]["group_type"], "family")
        self.assertEqual(data["state"]["constraints"]["budget"], 500.0)

        # Check if invoke was called properly
        mock_invoke.assert_called_once()
        called_args = mock_invoke.call_args[0][0]
        self.assertEqual(called_args["user_input"], "一家三口出去玩")

if __name__ == "__main__":
    unittest.main()
