"""Audit and exception output writers."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from .models import Decision


def write_audit(path: Path, decisions: tuple[Decision, ...], run_at: str) -> None:
    fields = ("record_type", "record_id", "state", "tier", "rule_name", "confidence",
              "rationale", "tolerance_used", "reason_code", "timestamp")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        for decision in decisions:
            for kind, ids in (("order", decision.order_ids), ("transaction", decision.txn_ids),
                              ("bank_credit", decision.utrs)):
                for record_id in ids:
                    writer.writerow({"record_type": kind, "record_id": record_id,
                        "state": decision.state, "tier": decision.tier,
                        "rule_name": decision.rule_name, "confidence": decision.confidence,
                        "rationale": decision.rationale, "tolerance_used": decision.tolerance_used,
                        "reason_code": decision.reason_code, "timestamp": run_at})


def write_exceptions(path: Path, decisions: tuple[Decision, ...]) -> None:
    fields = ("reason_code", "explanation", "order_ids", "txn_ids", "utrs", "confidence")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        for item in decisions:
            if item.state == "exception":
                writer.writerow({"reason_code": item.reason_code, "explanation": item.rationale,
                    "order_ids": "|".join(item.order_ids), "txn_ids": "|".join(item.txn_ids),
                    "utrs": "|".join(item.utrs), "confidence": item.confidence})

