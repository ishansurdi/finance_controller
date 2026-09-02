"""Generate reproducible synthetic ledger, gateway, bank, and ground-truth data."""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Configuration
SEED = 20260902
N_GROUPS = 100
BREAK_MIX = {
    "clean": 0.36,
    "timing_lag": 0.10,
    "batched": 0.07,
    "partial": 0.08,
    "duplicate": 0.08,
    "rounding": 0.06,
    "orphan": 0.06,
    "narration_recovery": 0.10,
    "same_amount_collision": 0.05,
    "agent_disagreement": 0.04,
}


BREAK_TYPES = tuple(BREAK_MIX)
LEDGER_FIELDS = (
    "order_id", "customer_id", "order_amount_paise", "order_status", "created_at"
)
GATEWAY_FIELDS = (
    "txn_id", "order_id", "gross_amount_paise", "fee_paise",
    "gst_on_fee_paise", "net_amount_paise", "captured_at", "payment_status",
)
BANK_FIELDS = ("utr", "settlement_amount_paise", "value_date", "bank_narration")
GROUND_TRUTH_FIELDS = (
    "match_group_id", "primary_break_type", "order_ids", "txn_ids", "utrs",
    "expected_outcome", "expected_exception_reason", "notes",
)


def round_ratio_half_even(numerator: int, denominator: int) -> int:
    """Round a non-negative rational number using Python's half-even rule."""
    quotient, remainder = divmod(numerator, denominator)
    twice_remainder = remainder * 2
    if twice_remainder > denominator or (
        twice_remainder == denominator and quotient % 2 == 1
    ):
        return quotient + 1
    return quotient


def economics(gross_amount_paise: int) -> tuple[int, int, int]:
    fee_paise = round_ratio_half_even(gross_amount_paise * 2, 100)
    gst_on_fee_paise = round_ratio_half_even(fee_paise * 18, 100)
    net_amount_paise = gross_amount_paise - fee_paise - gst_on_fee_paise
    return fee_paise, gst_on_fee_paise, net_amount_paise


def allocate_break_types(n_groups: int) -> list[str]:
    if n_groups < 0:
        raise ValueError("N_GROUPS must be non-negative")
    if set(BREAK_MIX) != set((
        "clean", "timing_lag", "batched", "partial", "duplicate", "rounding", "orphan",
        "narration_recovery", "same_amount_collision", "agent_disagreement"
    )):
        raise ValueError("BREAK_MIX must contain exactly the seven supported break types")
    if any(isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0
           for weight in BREAK_MIX.values()):
        raise ValueError("BREAK_MIX values must be non-negative numbers")

    total = sum(BREAK_MIX.values())
    if not 0.999999999 <= total <= 1.000000001:
        raise ValueError("BREAK_MIX proportions must sum to 1")

    raw_counts = {name: n_groups * weight for name, weight in BREAK_MIX.items()}
    counts = {name: int(value) for name, value in raw_counts.items()}
    remaining = n_groups - sum(counts.values())
    order = {name: index for index, name in enumerate(BREAK_MIX)}
    ranked = sorted(
        BREAK_MIX,
        key=lambda name: (-(raw_counts[name] - counts[name]), order[name]),
    )
    for name in ranked[:remaining]:
        counts[name] += 1

    return [name for name in BREAK_MIX for _ in range(counts[name])]


class Generator:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.ledger: list[dict[str, object]] = []
        self.gateway: list[dict[str, object]] = []
        self.bank: list[dict[str, object]] = []
        self.ground_truth: list[dict[str, object]] = []
        self.order_number = 0
        self.txn_number = 0
        self.utr_number = 0
        self.narration_recovery_number = 0
        self.base_time = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)

    def next_id(self, kind: str) -> str:
        if kind == "order":
            self.order_number += 1
            return f"ORD{self.order_number:05d}"
        if kind == "txn":
            self.txn_number += 1
            return f"TXN{self.txn_number:05d}"
        self.utr_number += 1
        return f"UTR{self.utr_number:05d}"

    def random_time(self) -> datetime:
        day_offset = self.rng.randrange(0, 180)
        minute_offset = self.rng.randrange(0, 12 * 60)
        return self.base_time + timedelta(days=day_offset, minutes=minute_offset)

    def random_amount(self) -> int:
        # A skew toward everyday purchases, with occasional larger orders.
        band = self.rng.randrange(100)
        if band < 65:
            return self.rng.randint(20_000, 250_000)
        if band < 92:
            return self.rng.randint(250_001, 1_500_000)
        return self.rng.randint(1_500_001, 7_500_000)

    def add_normal_transaction(self, created_at: datetime | None = None,
                               gross_amount_paise: int | None = None) -> tuple[str, str, int, datetime]:
        created = created_at or self.random_time()
        captured = created + timedelta(minutes=self.rng.randint(1, 240))
        gross = gross_amount_paise if gross_amount_paise is not None else self.random_amount()
        fee, gst, net = economics(gross)
        order_id = self.next_id("order")
        txn_id = self.next_id("txn")
        self.ledger.append({
            "order_id": order_id,
            "customer_id": f"CUST{self.rng.randint(1, 500):04d}",
            "order_amount_paise": gross,
            "order_status": "paid",
            "created_at": created.isoformat(),
        })
        self.gateway.append({
            "txn_id": txn_id,
            "order_id": order_id,
            "gross_amount_paise": gross,
            "fee_paise": fee,
            "gst_on_fee_paise": gst,
            "net_amount_paise": net,
            "captured_at": captured.isoformat(),
            "payment_status": "captured",
        })
        return order_id, txn_id, net, captured

    def add_bank_credit(self, amount: int, value_date: datetime, narration: str = "") -> str:
        utr = self.next_id("utr")
        self.bank.append({
            "utr": utr,
            "settlement_amount_paise": amount,
            "value_date": value_date.date().isoformat(),
            "bank_narration": narration,
        })
        return utr

    def add_truth(
        self, group_number: int, break_type: str, orders: list[str],
        txns: list[str], utrs: list[str], outcome: str, reason: str, notes: str,
    ) -> None:
        self.ground_truth.append({
            "match_group_id": f"GRP{group_number:05d}",
            "primary_break_type": break_type,
            "order_ids": "|".join(orders),
            "txn_ids": "|".join(txns),
            "utrs": "|".join(utrs),
            "expected_outcome": outcome,
            "expected_exception_reason": reason,
            "notes": notes,
        })

    def generate_group(self, group_number: int, break_type: str) -> None:
        if break_type == "orphan":
            utr = self.add_bank_credit(self.random_amount(), self.random_time())
            self.add_truth(group_number, break_type, [], [], [utr], "exception",
                           "bank credit with no matching order",
                           "Standalone bank credit with no ledger or gateway record.")
            return

        if break_type == "batched":
            orders, txns, nets, captures = [], [], [], []
            shared_day = self.random_time().replace(hour=10, minute=0)
            for _ in range(self.rng.randint(2, 5)):
                created = shared_day + timedelta(minutes=self.rng.randint(0, 480))
                order, txn, net, captured = self.add_normal_transaction(created)
                orders.append(order)
                txns.append(txn)
                nets.append(net)
                captures.append(captured)
            utr = self.add_bank_credit(sum(nets), max(captures) + timedelta(days=2))
            self.add_truth(group_number, break_type, orders, txns, [utr], "matched", "",
                           "Multiple gateway transactions combined into one bank credit.")
            return

        if break_type == "same_amount_collision":
            shared_time = self.random_time()
            shared_gross = self.random_amount()
            first = self.add_normal_transaction(shared_time, shared_gross)
            second = self.add_normal_transaction(shared_time, shared_gross)
            orders = [first[0], second[0]]
            txns = [first[1], second[1]]
            utrs = [
                self.add_bank_credit(first[2], first[3] + timedelta(days=2),
                                     f"PG SETTLEMENT REF {first[1]} / {first[0]}"),
                self.add_bank_credit(second[2], second[3] + timedelta(days=2),
                                     f"PG SETTLEMENT REF {second[1]} / {second[0]}"),
            ]
            self.add_truth(group_number, break_type, orders, txns, utrs, "matched", "",
                           "Equal amount and date collision; narration uniquely identifies both pairs.")
            return

        order, txn, net, captured = self.add_normal_transaction()
        orders, txns = [order], [txn]

        if break_type == "narration_recovery":
            self.narration_recovery_number += 1
            adjustment = self.rng.randint(25, 250)
            if self.narration_recovery_number <= 3:
                narration = f"PG NET {txn}; ADJ {adjustment}P; ORDER REFERENCE MISSING"
            else:
                narration = f"PG NET {txn}; ORDER {order}; ADJ {adjustment}P"
            utrs = [self.add_bank_credit(net + adjustment, captured + timedelta(days=2), narration)]
            notes = "Amount has a documented adjustment beyond deterministic tolerance; narration identifies it."
            outcome, reason = "matched", ""
        elif break_type == "agent_disagreement":
            narration = f"PG NET TXN99999; ORDER {order}; CONFLICTING REFERENCE"
            utrs = [self.add_bank_credit(net + 100, captured + timedelta(days=2), narration)]
            notes = "Narration conflicts with the order evidence; proposer and verifier must escalate."
            outcome, reason = "exception", "conflicting bank narration"
        elif break_type == "timing_lag":
            lag_days = self.rng.choice((4, 5))
            utrs = [self.add_bank_credit(net, captured + timedelta(days=lag_days))]
            notes = f"Settlement arrived T+{lag_days} instead of T+2."
            outcome, reason = "matched", ""
        elif break_type == "partial":
            first = self.rng.randint(1, net - 1)
            utrs = [
                self.add_bank_credit(first, captured + timedelta(days=2)),
                self.add_bank_credit(net - first, captured + timedelta(days=3)),
            ]
            notes = "One transaction settled in two bank credits whose amounts sum to net."
            outcome, reason = "matched", ""
        elif break_type == "duplicate":
            original = self.gateway[-1]
            duplicate_txn = self.next_id("txn")
            duplicate = dict(original)
            duplicate["txn_id"] = duplicate_txn
            duplicate["captured_at"] = (captured + timedelta(minutes=self.rng.randint(2, 30))).isoformat()
            self.gateway.append(duplicate)
            txns.append(duplicate_txn)
            utrs = [self.add_bank_credit(net, captured + timedelta(days=2))]
            notes = "Two captured gateway records share an order ID; only the first was settled."
            outcome, reason = "exception", "duplicate transaction reference"
        elif break_type == "rounding":
            drift = self.rng.choice((-2, -1, 1, 2))
            utrs = [self.add_bank_credit(net + drift, captured + timedelta(days=2))]
            notes = f"Bank settlement differs from gateway net by {drift:+d} paise."
            outcome, reason = "matched", ""
        else:  # clean
            utrs = [self.add_bank_credit(net, captured + timedelta(days=2))]
            notes = "Standard one-to-one settlement with fee, GST, and T+2 timing."
            outcome, reason = "matched", ""

        self.add_truth(group_number, break_type, orders, txns, utrs, outcome, reason, notes)


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    generator = Generator(SEED)
    break_types = allocate_break_types(N_GROUPS)
    generator.rng.shuffle(break_types)
    for group_number, break_type in enumerate(break_types, start=1):
        generator.generate_group(group_number, break_type)

    output_dir = Path(__file__).resolve().parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "ledger.csv", LEDGER_FIELDS, generator.ledger)
    write_csv(output_dir / "gateway.csv", GATEWAY_FIELDS, generator.gateway)
    write_csv(output_dir / "bank.csv", BANK_FIELDS, generator.bank)
    write_csv(output_dir / "ground_truth.csv", GROUND_TRUTH_FIELDS, generator.ground_truth)

    counts = Counter(row["primary_break_type"] for row in generator.ground_truth)
    print("Generated records:")
    print(f"  ledger.csv: {len(generator.ledger)}")
    print(f"  gateway.csv: {len(generator.gateway)}")
    print(f"  bank.csv: {len(generator.bank)}")
    print(f"  ground_truth.csv: {len(generator.ground_truth)}")
    print("Break types:")
    for break_type in BREAK_TYPES:
        print(f"  {break_type}: {counts[break_type]}")


if __name__ == "__main__":
    main()
