import ast
import unittest
from pathlib import Path


class DashboardTests(unittest.TestCase):
    def test_write_calls_use_one_element(self):
        tree = ast.parse(Path("streamlit_app.py").read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "write"]

        self.assertTrue(calls)
        self.assertTrue(all(len(call.args) <= 1 for call in calls))


if __name__ == "__main__":
    unittest.main()
