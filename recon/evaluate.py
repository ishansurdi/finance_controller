"""Honest match-group evaluation against hidden ground truth."""

from collections import Counter
from dataclasses import replace
from .config import (CONFIDENCE_AUTO_MATCH, FALSE_AUTO_MATCH_COST_PAISE,
                     HUMAN_REVIEW_COST_PAISE)
from .models import Decision, MatchGroup


def _key(order_ids: tuple[str, ...], txn_ids: tuple[str, ...], utrs: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    return frozenset(order_ids), frozenset(txn_ids), frozenset(utrs)


def evaluate(decisions: tuple[Decision, ...], truth: tuple[MatchGroup, ...],
             elapsed_seconds: float, total_records: int, control_totals: dict[str, int]) -> dict[str, object]:
    predicted = {_key(d.order_ids, d.txn_ids, d.utrs): d for d in decisions}
    confusion = {"matched_as_matched": 0, "matched_as_exception": 0, "matched_as_missing": 0,
                 "exception_as_matched": 0, "exception_as_exception": 0,
                 "exception_as_missing": 0}
    per_break: dict[str, dict[str, int | float]] = {}
    correct_matches = true_matches = flagged = true_exceptions = caught = 0
    for group in truth:
        decision = predicted.get(_key(group.order_ids, group.txn_ids, group.utrs))
        if decision is None:
            predicted_state = "missing"
        else:
            predicted_state = "matched" if decision.state == "auto_matched" else "exception"
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
        caught += expected == "exception" and predicted_state == "exception" and decision is not None
    for bucket in per_break.values():
        bucket["accuracy"] = bucket["correct"] / bucket["total"]
    tiers = Counter(str(d.tier) for d in decisions if d.state == "auto_matched")
    exception_tiers = Counter(str(d.tier) for d in decisions if d.state == "exception")
    false_reviews = confusion["matched_as_exception"] + confusion["matched_as_missing"]
    false_auto_matches = confusion["exception_as_matched"]
    return {"match_rate": correct_matches / true_matches if true_matches else 0.0,
            "exception_precision": caught / flagged if flagged else 0.0,
            "exception_recall": caught / true_exceptions if true_exceptions else 0.0,
            "confusion_matrix": confusion, "per_break_type": per_break,
            "records_processed": total_records,
            "throughput_note": "Runtime throughput is printed to console and excluded for reproducibility.",
            "resolved_per_tier": dict(tiers), "exceptions_per_tier": dict(exception_tiers),
            "control_totals": control_totals,
            "estimated_error_cost_paise": {
                "false_review_cost": false_reviews * HUMAN_REVIEW_COST_PAISE,
                "false_auto_match_cost": false_auto_matches * FALSE_AUTO_MATCH_COST_PAISE,
                "total": (false_reviews * HUMAN_REVIEW_COST_PAISE
                          + false_auto_matches * FALSE_AUTO_MATCH_COST_PAISE),
            },
            "operational_errors": {
                "unnecessary_review_groups": false_reviews,
                "false_auto_match_groups": false_auto_matches,
            },
            "error_costs": {"false_positive": "good match sent to human review",
                            "false_negative": "bad item silently auto-closed; may corrupt books",
                            "human_review_cost_paise": HUMAN_REVIEW_COST_PAISE,
                            "false_auto_match_cost_paise": FALSE_AUTO_MATCH_COST_PAISE}}


def ablation(deterministic: dict[str, object], augmented: dict[str, object]) -> dict[str, object]:
    """Quantify the incremental contribution of the verified agent layer."""
    deterministic_tiers = deterministic["resolved_per_tier"]
    augmented_tiers = augmented["resolved_per_tier"]
    deterministic_cost = deterministic["estimated_error_cost_paise"]["total"]
    augmented_cost = augmented["estimated_error_cost_paise"]["total"]
    return {
        "match_rate_delta": augmented["match_rate"] - deterministic["match_rate"],
        "agent_groups_recovered": augmented_tiers.get("2", 0),
        "deterministic_auto_matched": sum(deterministic_tiers.values()),
        "agent_augmented_auto_matched": sum(augmented_tiers.values()),
        "true_exceptions_caught": augmented["confusion_matrix"]["exception_as_exception"],
        "tier_two_escalations": augmented.get("exceptions_per_tier", {}).get("2", 0),
        "expected_cost_savings_paise": deterministic_cost - augmented_cost,
        "false_auto_matches_added": (
            augmented["operational_errors"]["false_auto_match_groups"]
            - deterministic["operational_errors"]["false_auto_match_groups"]
        ),
        "human_reviews_avoided": (
            deterministic["operational_errors"]["unnecessary_review_groups"]
            - augmented["operational_errors"]["unnecessary_review_groups"]
        ),
    }


def score_tier_two(deterministic: tuple[Decision, ...], augmented: tuple[Decision, ...],
                   truth: tuple[MatchGroup, ...]) -> dict[str, int | float]:
    """Score Tier-2 recovery and abstention against exact hidden group pairings."""
    deterministic_keys = {_key(d.order_ids, d.txn_ids, d.utrs)
                          for d in deterministic if d.state == "auto_matched"}
    tier_two = {_key(d.order_ids, d.txn_ids, d.utrs): d for d in augmented if d.tier == 2}
    residual_truth = [group for group in truth
                      if _key(group.order_ids, group.txn_ids, group.utrs) not in deterministic_keys]
    resolvable = [group for group in residual_truth if group.expected_outcome == "matched"]
    truly_exceptional = [group for group in residual_truth if group.expected_outcome == "exception"]
    attempted = [d for d in tier_two.values() if d.state == "auto_matched"]
    correct_recoveries = sum(
        tier_two.get(_key(g.order_ids, g.txn_ids, g.utrs)) is not None
        and tier_two[_key(g.order_ids, g.txn_ids, g.utrs)].state == "auto_matched"
        for g in resolvable
    )
    resolvable_escalations = sum(
        tier_two.get(_key(g.order_ids, g.txn_ids, g.utrs)) is not None
        and tier_two[_key(g.order_ids, g.txn_ids, g.utrs)].state == "exception"
        for g in resolvable
    )
    correct_escalations = sum(
        tier_two.get(_key(g.order_ids, g.txn_ids, g.utrs)) is not None
        and tier_two[_key(g.order_ids, g.txn_ids, g.utrs)].state == "exception"
        for g in truly_exceptional
    )
    return {
        "resolvable_residual_groups": len(resolvable),
        "recovery_attempts": len(attempted),
        "correct_recoveries": correct_recoveries,
        "recovery_accuracy": correct_recoveries / len(resolvable) if resolvable else 0.0,
        "recovery_precision": correct_recoveries / len(attempted) if attempted else 0.0,
        "resolvable_escalations": resolvable_escalations,
        "correct_safety_escalations": correct_escalations,
    }


def cost_curve(decisions: tuple[Decision, ...], truth: tuple[MatchGroup, ...],
               thresholds: tuple[float, ...] = (0.50, 0.70, 0.90, 0.95, 0.99)) -> dict[str, object]:
    """Estimate business loss across gates; threshold selection is cost-led, not F1-led."""
    points = []
    for threshold in thresholds:
        gated = tuple(replace(decision,
                              state=("auto_matched" if not decision.reason_code
                                     and decision.confidence >= threshold else "exception"))
                      for decision in decisions)
        result = evaluate(gated, truth, 1.0, 0, {})
        points.append({"threshold": threshold, **result["estimated_error_cost_paise"]})
    return {
        "selected_threshold": CONFIDENCE_AUTO_MATCH,
        "selection_basis": "minimum expected business cost; not maximum F1",
        "false_auto_match_to_review_cost_ratio": (
            FALSE_AUTO_MATCH_COST_PAISE // HUMAN_REVIEW_COST_PAISE
        ),
        "points": points,
    }
