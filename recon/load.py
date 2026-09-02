"""Strict CSV loading and one-time normalization."""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Callable, TypeVar

from .models import BankRow, GatewayRow, LedgerRow, MatchGroup

T = TypeVar("T")


def _money(value: str, column: str, row_number: int) -> int:
    if not value.isdigit():
        raise ValueError(f"row {row_number}: {column} must be a non-negative integer")
    return int(value)


def _read(path: Path, expected: tuple[str, ...], build: Callable[[dict[str, str], int], T]) -> tuple[T, ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected:
            raise ValueError(f"{path}: expected columns {expected}, got {reader.fieldnames}")
        return tuple(build(row, number) for number, row in enumerate(reader, start=2))


def load_ledger(path: Path) -> tuple[LedgerRow, ...]:
    fields = ("order_id", "customer_id", "order_amount_paise", "order_status", "created_at")
    return _read(path, fields, lambda r, n: LedgerRow(r["order_id"], r["customer_id"],
        _money(r["order_amount_paise"], "order_amount_paise", n), r["order_status"],
        datetime.fromisoformat(r["created_at"])))


def load_gateway(path: Path) -> tuple[GatewayRow, ...]:
    fields = ("txn_id", "order_id", "gross_amount_paise", "fee_paise", "gst_on_fee_paise",
              "net_amount_paise", "captured_at", "payment_status")
    return _read(path, fields, lambda r, n: GatewayRow(r["txn_id"], r["order_id"],
        *(_money(r[key], key, n) for key in fields[2:6]), datetime.fromisoformat(r["captured_at"]),
        r["payment_status"]))


def load_bank(path: Path) -> tuple[BankRow, ...]:
    fields = ("utr", "settlement_amount_paise", "value_date", "bank_narration")
    return _read(path, fields, lambda r, n: BankRow(r["utr"],
        _money(r["settlement_amount_paise"], "settlement_amount_paise", n),
        date.fromisoformat(r["value_date"]), r["bank_narration"]))


def load_ground_truth(path: Path) -> tuple[MatchGroup, ...]:
    fields = ("match_group_id", "primary_break_type", "order_ids", "txn_ids", "utrs",
              "expected_outcome", "expected_exception_reason", "notes")
    split = lambda value: tuple(filter(None, value.split("|")))
    return _read(path, fields, lambda r, _n: MatchGroup(r["match_group_id"],
        r["primary_break_type"], split(r["order_ids"]), split(r["txn_ids"]), split(r["utrs"]),
        r["expected_outcome"], r["expected_exception_reason"], r["notes"]))


def structural_anomalies(ledger: tuple[LedgerRow, ...], gateway: tuple[GatewayRow, ...]) -> tuple[str, ...]:
    known_orders = {row.order_id for row in ledger}
    return tuple(f"gateway {row.txn_id}: unknown order_id {row.order_id}"
                 for row in gateway if row.order_id not in known_orders)
