import unittest
from datetime import date, datetime, timezone

from recon.engine import control_total, reconcile
from recon.models import BankRow, GatewayRow, LedgerRow


def records(net: int = 9_764, order: str = "O1", txn: str = "T1"):
    created = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    ledger = LedgerRow(order, "C1", 10_000, "paid", created)
    gateway = GatewayRow(txn, order, 10_000, 200, 36, net, created, "captured")
    return ledger, gateway


class ReconciliationTests(unittest.TestCase):
    def test_rounding_tolerance(self):
        ledger, gateway = records()
        result = reconcile((ledger,), (gateway,), (BankRow("U1", 9_766, date(2026, 1, 3)),))
        self.assertEqual((result[0].state, result[0].rule_name), ("auto_matched", "rounding_tolerance"))

    def test_partial_sum(self):
        ledger, gateway = records()
        banks = (BankRow("U1", 4_000, date(2026, 1, 3)), BankRow("U2", 5_764, date(2026, 1, 4)))
        self.assertEqual(reconcile((ledger,), (gateway,), banks)[0].rule_name, "partial")

    def test_batched_sum(self):
        l1, g1 = records(9_764, "O1", "T1")
        l2, g2 = records(9_764, "O2", "T2")
        bank = BankRow("U1", 19_528, date(2026, 1, 3))
        self.assertEqual(reconcile((l1, l2), (g1, g2), (bank,))[0].rule_name, "batched")

    def test_duplicate_is_exception(self):
        ledger, first = records()
        _, second = records(txn="T2")
        result = reconcile((ledger,), (first, second), (BankRow("U1", 9_764, date(2026, 1, 3)),))
        self.assertEqual(result[0].reason_code, "duplicate_capture_human_void_required")

    def test_orphan_is_exception(self):
        result = reconcile((), (), (BankRow("U1", 500, date(2026, 1, 3)),))
        self.assertEqual(result[0].reason_code, "bank_credit_with_no_matching_order")

    def test_control_total_separates_explained_variance(self):
        ledger, gateway = records()
        bank = BankRow("U1", 9_766, date(2026, 1, 3))
        decisions = reconcile((ledger,), (gateway,), (bank,))

        totals = control_total(decisions, (gateway,), (bank,))

        self.assertEqual(totals["raw_residual_paise"], 2)
        self.assertEqual(totals["explained_variance_paise"], 2)
        self.assertEqual(totals["unexplained_residual_paise"], 0)


if __name__ == "__main__":
    unittest.main()
