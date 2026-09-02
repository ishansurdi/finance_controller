"""Honest match-group evaluation against hidden ground truth."""

from collections import Counter
from .models import Decision, MatchGroup


def _key(order_ids: tuple[str, ...], txn_ids: tuple[str, ...], utrs: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    return frozenset(order_ids), frozenset(txn_ids), frozenset(utrs)


def evaluate(decisions: tuple[Decision, ...], truth: tuple[MatchGroup, ...],
             elapsed_seconds: float, total_records: int, control_totals: dict[str, int]) -> dict[str, object]:
    predicted = {_key(d.order_ids, d.txn_ids, d.utrs): d for d in decisions}
    confusion = {"matched_as_matched": 0, "matched_as_exception": 0,
                 "exception_as_matched": 0, "exception_as_exception": 0}
    per_break: dict[str, dict[str, int | float]] = {}
    correct_matches = true_matches = flagged = true_exceptions = caught = 0
    for group in truth:
        decision = predicted.get(_key(group.order_ids, group.txn_ids, group.utrs))
        predicted_state = "matched" if decision and decision.state == "auto_matched" else "exception"
        expected = group.expected_outcome
        confusion[f"{expected}_as_{predicted_state}"] += 1
        correct = predicted_state == expected and decision is not None
        bucket = per_break.setdefault(group.primary_break_type, {"correct": 0, "total": 0, "accuracy": 0.0})
        bucket["total"] += 1
        bucket["correct"] += int(correct)
        true_matches += expected == "matched"
        correct_matches += expected == "matched" and predicted_state == "matched" and decision is not None
        true_exceptions += expected == "exception"
        flagged += predicted_state == "exception"
        caught += expected == "exception" and predicted_state == "exception"
    for bucket in per_break.values():
        bucket["accuracy"] = bucket["correct"] / bucket["total"]
    tiers = Counter(str(d.tier) for d in decisions if d.state == "auto_matched")
    return {"match_rate": correct_matches / true_matches if true_matches else 0.0,
            "exception_precision": caught / flagged if flagged else 0.0,
            "exception_recall": caught / true_exceptions if true_exceptions else 0.0,
            "confusion_matrix": confusion, "per_break_type": per_break,
            "throughput_records_per_second": total_records / elapsed_seconds if elapsed_seconds else 0.0,
            "resolved_per_tier": dict(tiers), "control_totals": control_totals,
            "error_costs": {"false_positive": "good match sent to human review",
                            "false_negative": "bad item silently auto-closed; may corrupt books"}}
