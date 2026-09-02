import unittest
from datetime import date, datetime, timezone

from recon.agents import reconcile_residual
from recon.models import BankRow, GatewayRow, LedgerRow
from recon.residual import Residual


def residual(narration: str) -> Residual:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Residual(
        (LedgerRow("ORD00001", "C1", 10_000, "paid", now),),
        (GatewayRow("TXN00001", "ORD00001", 10_000, 200, 36, 9_764, now, "captured"),),
        (BankRow("UTR00001", 9_864, date(2026, 1, 3), narration),),
    )


class AgentTests(unittest.TestCase):
    def test_proposer_and_verifier_recover_narrated_adjustment(self):
        result = reconcile_residual(residual("PG NET TXN00001; ORDER ORD00001; ADJ 100P"))

        self.assertEqual(result[0].state, "auto_matched")
        self.assertEqual(result[0].tier, 2)

    def test_conflicting_reference_is_logged_and_escalated(self):
        result = reconcile_residual(residual("PG NET TXN99999; ORDER ORD00001; CONFLICT"))

        self.assertEqual(result[0].state, "exception")
        self.assertEqual(result[0].reason_code, "proposer_verifier_disagreement")
        self.assertIn("Verifier rejected", result[0].rationale)


if __name__ == "__main__":
    unittest.main()
