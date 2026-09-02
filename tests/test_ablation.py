import unittest

from recon.evaluate import ablation, score_tier_two
from recon.models import Decision, MatchGroup


class AblationTests(unittest.TestCase):
    def test_reports_agent_increment(self):
        before = {"match_rate": 0.8, "resolved_per_tier": {"0": 40, "1": 40},
                  "confusion_matrix": {"exception_as_exception": 5}, "exceptions_per_tier": {"1": 5}}
        after = {"match_rate": 0.9, "resolved_per_tier": {"0": 40, "1": 40, "2": 10},
                 "confusion_matrix": {"exception_as_exception": 5}, "exceptions_per_tier": {"1": 3, "2": 2}}

        result = ablation(before, after)

        self.assertAlmostEqual(result["match_rate_delta"], 0.1)
        self.assertEqual(result["agent_groups_recovered"], 10)
        self.assertEqual(result["tier_two_escalations"], 2)
        self.assertEqual(result["true_exceptions_caught"], 5)

    def test_tier_two_scores_recovery_and_escalation_separately(self):
        truth = (
            MatchGroup("G1", "hard", ("O1",), ("T1",), ("U1",), "matched", "", ""),
            MatchGroup("G2", "hard", ("O2",), ("T2",), ("U2",), "matched", "", ""),
            MatchGroup("G3", "conflict", ("O3",), ("T3",), ("U3",), "exception", "", ""),
        )
        matched = Decision(("O1",), ("T1",), ("U1",), "auto_matched", 2, "agent", .9, "", "")
        missed = Decision(("O2",), ("T2",), ("U2",), "exception", 2, "agent", .2, "", "")
        safe = Decision(("O3",), ("T3",), ("U3",), "exception", 2, "agent", .2, "", "")

        score = score_tier_two((), (matched, missed, safe), truth)

        self.assertEqual(score["correct_recoveries"], 1)
        self.assertEqual(score["resolvable_escalations"], 1)
        self.assertEqual(score["correct_safety_escalations"], 1)


if __name__ == "__main__":
    unittest.main()
