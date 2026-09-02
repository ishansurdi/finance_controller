import unittest

from recon.evaluate import ablation


class AblationTests(unittest.TestCase):
    def test_reports_agent_increment(self):
        before = {"match_rate": 0.8, "resolved_per_tier": {"0": 40, "1": 40},
                  "confusion_matrix": {"exception_as_exception": 5}}
        after = {"match_rate": 0.9, "resolved_per_tier": {"0": 40, "1": 40, "2": 10},
                 "confusion_matrix": {"exception_as_exception": 5}}

        result = ablation(before, after)

        self.assertAlmostEqual(result["match_rate_delta"], 0.1)
        self.assertEqual(result["agent_groups_recovered"], 10)


if __name__ == "__main__":
    unittest.main()
