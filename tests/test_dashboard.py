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

    def test_batch_controls_explain_their_business_meaning(self):
        source = Path("streamlit_app.py").read_text(encoding="utf-8")

        self.assertIn("One match group is one reconciliation case", source)
        self.assertIn("1.0 is the baseline mix", source)
        self.assertIn("larger residual for", source)

    def test_risk_indicators_and_cost_curve_have_guidance(self):
        source = Path("streamlit_app.py").read_text(encoding="utf-8")

        self.assertIn('"Recovery impact"', source)
        self.assertIn('"Decision cost basis"', source)
        self.assertIn('"**Confidence-cost curve**"', source)
        self.assertIn("Lower is better", source)
        self.assertIn('x_label="Confidence threshold"', source)
        self.assertIn('y_label="Expected cost (paise)"', source)


if __name__ == "__main__":
    unittest.main()
