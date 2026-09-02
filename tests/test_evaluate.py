import unittest

from recon.evaluate import cost_curve, evaluate
from recon.models import Decision, MatchGroup


class EvaluationTests(unittest.TestCase):
    def test_missing_decision_does_not_count_as_caught_exception(self):
        truth = (MatchGroup("G1", "orphan", (), (), ("U1",), "exception", "orphan", ""),)

        report = evaluate((), truth, 1.0, 1, {"residual_paise": 0})

        self.assertEqual(report["exception_recall"], 0.0)
        self.assertEqual(report["confusion_matrix"]["exception_as_missing"], 1)

    def test_cost_curve_penalizes_false_auto_match_more_than_review(self):
        truth = (MatchGroup("G1", "hard", ("O1",), ("T1",), ("U1",),
                            "exception", "bad", ""),)
        unsafe = Decision(("O1",), ("T1",), ("U1",), "auto_matched", 2,
                          "agent", 0.8, "", "")

        curve = cost_curve((unsafe,), truth, (0.7, 0.9))

        self.assertGreater(curve["points"][0]["total"], curve["points"][1]["total"])
        self.assertEqual(curve["false_auto_match_to_review_cost_ratio"], 400)


if __name__ == "__main__":
    unittest.main()
