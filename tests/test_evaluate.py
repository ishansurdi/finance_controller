import unittest

from recon.evaluate import evaluate
from recon.models import MatchGroup


class EvaluationTests(unittest.TestCase):
    def test_missing_decision_does_not_count_as_caught_exception(self):
        truth = (MatchGroup("G1", "orphan", (), (), ("U1",), "exception", "orphan", ""),)

        report = evaluate((), truth, 1.0, 1, {"residual_paise": 0})

        self.assertEqual(report["exception_recall"], 0.0)
        self.assertEqual(report["confusion_matrix"]["exception_as_missing"], 1)


if __name__ == "__main__":
    unittest.main()
