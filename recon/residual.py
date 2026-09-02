"""Tier-2 extension seam; no proposer is implemented in this phase."""

from dataclasses import dataclass

from .models import BankRow, Decision, GatewayRow, LedgerRow


@dataclass(frozen=True)
class Residual:
    ledger: tuple[LedgerRow, ...]
    gateway: tuple[GatewayRow, ...]
    bank: tuple[BankRow, ...]


def tier_two_decisions(residual: Residual) -> tuple[Decision, ...]:
    """Receive post-Tier-1 records; a future verified proposer plugs in here."""
    return ()


def isolate_residual(ledger: tuple[LedgerRow, ...], gateway: tuple[GatewayRow, ...],
                     bank: tuple[BankRow, ...], decisions: tuple[Decision, ...]) -> Residual:
    """Return records not conclusively closed by deterministic tiers."""
    final = tuple(decision for decision in decisions
                  if decision.state == "auto_matched"
                  or decision.reason_code in {
                      "duplicate_capture_human_void_required",
                      "bank_credit_with_no_matching_order",
                  })
    used_orders = {value for decision in final for value in decision.order_ids}
    used_txns = {value for decision in final for value in decision.txn_ids}
    used_utrs = {value for decision in final for value in decision.utrs}
    return Residual(
        tuple(row for row in ledger if row.order_id not in used_orders),
        tuple(row for row in gateway if row.txn_id not in used_txns),
        tuple(row for row in bank if row.utr not in used_utrs),
    )
