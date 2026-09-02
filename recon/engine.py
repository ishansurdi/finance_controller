"""Conservative tiered deterministic reconciliation."""

from collections import Counter, defaultdict
from datetime import timedelta
from itertools import combinations

from .config import (BATCH_MAX_MEMBERS, CONFIDENCE_AUTO_MATCH, ROUNDING_TOLERANCE_PAISE,
                     SETTLEMENT_LAG_DAYS, TIMING_TOLERANCE_DAYS)
from .models import BankRow, Decision, GatewayRow, LedgerRow


def _decision(txns: list[GatewayRow], banks: list[BankRow], tier: int, rule: str,
              confidence: float, rationale: str, tolerance: str, state: str = "auto_matched",
              reason: str = "") -> Decision:
    # False matches corrupt books; uncertain candidates are deliberately exceptions.
    if confidence < CONFIDENCE_AUTO_MATCH:
        state, reason = "exception", reason or "below confidence threshold"
    return Decision(tuple(dict.fromkeys(t.order_id for t in txns)), tuple(t.txn_id for t in txns),
                    tuple(b.utr for b in banks), state, tier, rule, confidence, rationale,
                    tolerance, reason, state == "exception")


def _valid_date(txn: GatewayRow, bank: BankRow) -> bool:
    lag = (bank.value_date - txn.captured_at.date()).days
    return SETTLEMENT_LAG_DAYS <= lag <= SETTLEMENT_LAG_DAYS + TIMING_TOLERANCE_DAYS


def reconcile(ledger: tuple[LedgerRow, ...], gateway: tuple[GatewayRow, ...],
              bank: tuple[BankRow, ...]) -> tuple[Decision, ...]:
    ledger_by_order = {row.order_id: row for row in ledger}
    remaining_txns = {row.txn_id: row for row in gateway}
    remaining_banks = {row.utr: row for row in bank}
    decisions: list[Decision] = []

    by_order: dict[str, list[GatewayRow]] = defaultdict(list)
    for row in gateway:
        by_order[row.order_id].append(row)
    for order_id, duplicates in by_order.items():
        if len(duplicates) < 2:
            continue
        candidates = [b for b in remaining_banks.values()
                      if b.settlement_amount_paise == duplicates[0].net_amount_paise
                      and _valid_date(duplicates[0], b)]
        banks = candidates if len(candidates) == 1 else []
        decisions.append(_decision(duplicates, banks, 1, "duplicate_detect", 0.0,
            "Multiple gateway captures share one order; a human must identify the retry to void.",
            "duplicate count > 1", "exception", "duplicate_capture_human_void_required"))
        for txn in duplicates:
            remaining_txns.pop(txn.txn_id, None)
        for item in banks:
            remaining_banks.pop(item.utr, None)

    def consume(txns: list[GatewayRow], banks: list[BankRow], decision: Decision) -> None:
        decisions.append(decision)
        for txn in txns:
            remaining_txns.pop(txn.txn_id, None)
        for item in banks:
            remaining_banks.pop(item.utr, None)

    # Single-candidate rules run from strongest to weakest.
    for rule in ("exact", "timing_window", "rounding_tolerance"):
        for txn in list(remaining_txns.values()):
            ledger_row = ledger_by_order.get(txn.order_id)
            if ledger_row is None or ledger_row.order_amount_paise != txn.gross_amount_paise:
                continue
            economic_ok = txn.net_amount_paise == txn.gross_amount_paise - txn.fee_paise - txn.gst_on_fee_paise
            if not economic_ok:
                continue
            candidates = []
            for item in remaining_banks.values():
                lag = (item.value_date - txn.captured_at.date()).days
                drift = item.settlement_amount_paise - txn.net_amount_paise
                if rule == "exact" and lag == SETTLEMENT_LAG_DAYS and drift == 0:
                    candidates.append(item)
                elif rule == "timing_window" and drift == 0 and _valid_date(txn, item) and lag != SETTLEMENT_LAG_DAYS:
                    candidates.append(item)
                elif rule == "rounding_tolerance" and _valid_date(txn, item) and 0 < abs(drift) <= ROUNDING_TOLERANCE_PAISE:
                    candidates.append(item)
            if len(candidates) == 1:
                item = candidates[0]
                lag = (item.value_date - txn.captured_at.date()).days
                drift = item.settlement_amount_paise - txn.net_amount_paise
                tier, confidence = (0, 1.0) if rule == "exact" else (1, 0.97 if rule == "timing_window" else 0.95)
                consume([txn], [item], _decision([txn], [item], tier, rule, confidence,
                    f"Economic identity validated; settlement lag {lag} days and amount drift {drift} paise.",
                    f"lag={lag}d; drift={drift}paise"))
            elif len(candidates) > 1:
                consume([txn], [], _decision([txn], [], 1, rule, 0.0,
                    "Multiple viable bank credits cannot be separated safely.", "candidate_count>1",
                    "exception", "ambiguous"))

    # Partial settlements: one transaction to a unique combination of bank credits.
    for txn in list(remaining_txns.values()):
        eligible = [b for b in remaining_banks.values() if _valid_date(txn, b)]
        candidates = [combo for size in range(2, min(len(eligible), BATCH_MAX_MEMBERS) + 1)
                      for combo in combinations(eligible, size)
                      if sum(b.settlement_amount_paise for b in combo) == txn.net_amount_paise]
        if len(candidates) == 1:
            combo = list(candidates[0])
            consume([txn], combo, _decision([txn], combo, 1, "partial", 0.94,
                "Multiple bank credits uniquely sum to one gateway net amount.",
                f"members={len(combo)}; drift=0paise"))

    # Batched settlements: one bank credit to a unique subset of transactions.
    for item in list(remaining_banks.values()):
        eligible = [t for t in remaining_txns.values() if _valid_date(t, item)]
        candidates = [combo for size in range(2, min(len(eligible), BATCH_MAX_MEMBERS) + 1)
                      for combo in combinations(eligible, size)
                      if sum(t.net_amount_paise for t in combo) == item.settlement_amount_paise]
        if len(candidates) == 1:
            combo = list(candidates[0])
            consume(combo, [item], _decision(combo, [item], 1, "batched", 0.93,
                "A unique date-consistent transaction subset sums to the bank credit.",
                f"members={len(combo)}; drift=0paise"))
        elif len(candidates) > 1:
            involved = list(dict.fromkeys(t for combo in candidates for t in combo))
            consume(involved, [item], _decision(involved, [item], 1, "batched", 0.0,
                "Multiple transaction subsets produce the same settlement amount.",
                f"candidate_subsets={len(candidates)}", "exception", "ambiguous_batch"))

    for txn in list(remaining_txns.values()):
        consume([txn], [], _decision([txn], [], 1, "unresolved", 0.0,
            "No unique bank settlement satisfies the deterministic rules.", "none",
            "exception", "unresolved_transaction"))
    for item in list(remaining_banks.values()):
        consume([], [item], _decision([], [item], 1, "orphan_detect", 0.0,
            "Bank credit has no reconcilable ledger or gateway transaction.", "none",
            "exception", "bank_credit_with_no_matching_order"))
    return tuple(decisions)


def control_total(decisions: tuple[Decision, ...], gateway: tuple[GatewayRow, ...],
                  bank: tuple[BankRow, ...]) -> dict[str, int]:
    txn_net = {row.txn_id: row.net_amount_paise for row in gateway}
    bank_amount = {row.utr: row.settlement_amount_paise for row in bank}
    matched = [d for d in decisions if d.state == "auto_matched"]
    gateway_total = sum(txn_net[i] for d in matched for i in d.txn_ids)
    bank_total = sum(bank_amount[i] for d in matched for i in d.utrs)
    return {"matched_gateway_net_paise": gateway_total, "matched_bank_paise": bank_total,
            "residual_paise": bank_total - gateway_total}
