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

