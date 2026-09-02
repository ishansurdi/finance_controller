"""Immutable source and result models."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class LedgerRow:
    order_id: str
    customer_id: str
    order_amount_paise: int
    order_status: str
    created_at: datetime


@dataclass(frozen=True)
class GatewayRow:
    txn_id: str
    order_id: str
    gross_amount_paise: int
    fee_paise: int
    gst_on_fee_paise: int
    net_amount_paise: int
    captured_at: datetime
    payment_status: str


@dataclass(frozen=True)
class BankRow:
    utr: str
    settlement_amount_paise: int
    value_date: date
    bank_narration: str = ""


@dataclass(frozen=True)
class MatchGroup:
    match_group_id: str
    primary_break_type: str
    order_ids: tuple[str, ...]
    txn_ids: tuple[str, ...]
    utrs: tuple[str, ...]
    expected_outcome: str
    expected_exception_reason: str
    notes: str


@dataclass(frozen=True)
class Decision:
    order_ids: tuple[str, ...]
    txn_ids: tuple[str, ...]
    utrs: tuple[str, ...]
    state: str
    tier: int
    rule_name: str
    confidence: float
    rationale: str
    tolerance_used: str
    reason_code: str = ""
    review_recommended: bool = False
