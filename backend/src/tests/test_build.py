import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from closedloop.graph.build import build_graph

class TestGraphBuild(unittest.TestCase):
    def test_build_graph(self):
        """Test if graph can be compiled successfully."""
        app = build_graph()
        self.assertIsNotNone(app)
        
if __name__ == "__main__":
    unittest.main()
