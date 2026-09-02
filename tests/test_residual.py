import unittest
from datetime import date, datetime, timezone

from recon.models import BankRow, Decision, GatewayRow, LedgerRow
from recon.residual import isolate_residual


class ResidualTests(unittest.TestCase):
    def test_only_conclusively_closed_records_are_removed(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ledger = (LedgerRow("O1", "C1", 100, "paid", now),)
        gateway = (GatewayRow("T1", "O1", 100, 2, 0, 98, now, "captured"),)
        bank = (BankRow("U1", 105, date(2026, 1, 3), "REF T1"),)
        unresolved = Decision(("O1",), ("T1",), (), "exception", 1, "unresolved", 0.0,
                              "No match", "none", "unresolved_transaction", True)

        residual = isolate_residual(ledger, gateway, bank, (unresolved,))

        self.assertEqual(residual.ledger, ledger)
        self.assertEqual(residual.gateway, gateway)
        self.assertEqual(residual.bank, bank)


if __name__ == "__main__":
    unittest.main()
