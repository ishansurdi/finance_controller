import csv
import tempfile
import unittest
from pathlib import Path

from recon.audit import write_exceptions
from recon.models import Decision


class ExceptionOutputTests(unittest.TestCase):
    def test_records_deterministic_agent_review_status(self):
        decision = Decision(("O1",), ("T1",), (), "exception", 1, "duplicate_detect",
                            0.0, "Duplicate", "count>1", "duplicate", True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exceptions.csv"
            write_exceptions(path, (decision,))
            row = next(csv.DictReader(path.open(encoding="utf-8")))

        self.assertEqual(row["tier"], "1")
        self.assertEqual(row["rule_name"], "duplicate_detect")
        self.assertEqual(row["agent_review_status"], "not_invoked_deterministic_control")

    def test_records_tier_two_as_agent_invoked(self):
        decision = Decision(("O1",), ("T1",), ("U1",), "exception", 2,
                            "agent_verifier_disagreement", 0.35, "Rejected", "drift",
                            "disagreement", True, "Proposed", "Rejected")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exceptions.csv"
            write_exceptions(path, (decision,))
            row = next(csv.DictReader(path.open(encoding="utf-8")))

        self.assertEqual(row["agent_review_status"], "invoked")
        self.assertEqual(row["proposer_output"], "Proposed")
        self.assertEqual(row["verifier_output"], "Rejected")


if __name__ == "__main__":
    unittest.main()
