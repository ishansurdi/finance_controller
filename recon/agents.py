"""Evidence proposer and independent maker-checker verifier for Tier 2."""

import re
from dataclasses import dataclass
from itertools import groupby

from .models import BankRow, Decision, GatewayRow
from .residual import Residual

ID_PATTERN = re.compile(r"\b(?:TXN|ORD)\d{5}\b")


@dataclass(frozen=True)
class Proposal:
    transaction: GatewayRow
    bank: BankRow
    extracted_ids: tuple[str, ...]
    rationale: str


def propose(residual: Residual) -> tuple[Proposal, ...]:
    """Interpret narration and propose links without authority to close books."""
    txns = {row.txn_id: row for row in residual.gateway}
    orders = {row.order_id: row for row in residual.gateway}
    proposals: list[Proposal] = []
    for bank in residual.bank:
        ids = tuple(dict.fromkeys(ID_PATTERN.findall(bank.bank_narration.upper())))
        referenced_txns = [txns[value] for value in ids if value in txns]
        referenced_orders = [orders[value] for value in ids if value in orders]
        candidate = referenced_txns[0] if len(referenced_txns) == 1 else None
        if candidate is None and len(referenced_orders) == 1:
            candidate = referenced_orders[0]
        if candidate is not None:
            proposals.append(Proposal(candidate, bank, ids,
                f"Proposer linked narration identifiers {', '.join(ids)} to {candidate.txn_id}."))
    return tuple(proposals)


def verify(proposal: Proposal) -> Decision:
    """Apply independent four-eyes checks and reject conflicting references."""
    txn, bank = proposal.transaction, proposal.bank
    txn_refs = [value for value in proposal.extracted_ids if value.startswith("TXN")]
    order_refs = [value for value in proposal.extracted_ids if value.startswith("ORD")]
    references_agree = txn_refs == [txn.txn_id] and order_refs == [txn.order_id]
    drift = bank.settlement_amount_paise - txn.net_amount_paise
    if not references_agree:
        return Decision((txn.order_id,), (txn.txn_id,), (bank.utr,), "exception", 2,
            "agent_verifier_disagreement", 0.35,
            f"{proposal.rationale} Verifier rejected conflicting references: "
            f"expected {txn.txn_id}/{txn.order_id}.", f"drift={drift}paise",
            "proposer_verifier_disagreement", True)
    return Decision((txn.order_id,), (txn.txn_id,), (bank.utr,), "auto_matched", 2,
        "narration_evidence", 0.96,
        f"{proposal.rationale} Verifier confirmed both transaction and order references; "
        f"documented adjustment is {drift:+d} paise.", f"drift={drift}paise")


def _merge_collisions(decisions: list[Decision], residual: Residual) -> list[Decision]:
    banks = {row.utr: row for row in residual.bank}
    txns = {row.txn_id: row for row in residual.gateway}
    keyed = sorted(decisions, key=lambda d: (
        banks[d.utrs[0]].value_date, banks[d.utrs[0]].settlement_amount_paise,
        d.state, d.txn_ids,
    ))
    merged: list[Decision] = []
    for _, group_iterator in groupby(keyed, key=lambda d: (
        banks[d.utrs[0]].value_date, banks[d.utrs[0]].settlement_amount_paise, d.state,
    )):
        group = list(group_iterator)
        is_collision = (len(group) > 1 and group[0].state == "auto_matched"
                        and all(txns[item.txn_ids[0]].net_amount_paise
                                == banks[item.utrs[0]].settlement_amount_paise for item in group))
        if not is_collision:
            merged.extend(group)
            continue
        merged.append(Decision(
            tuple(value for item in group for value in item.order_ids),
            tuple(value for item in group for value in item.txn_ids),
            tuple(value for item in group for value in item.utrs),
            "auto_matched", 2, "narration_collision_resolution", 0.96,
            "Proposer separated equal-amount candidates using narration; verifier confirmed every pair.",
            f"members={len(group)}; drift=0paise",
        ))
    return merged


def reconcile_residual(residual: Residual) -> tuple[Decision, ...]:
    """Run proposer then verifier and preserve unresolved records as exceptions."""
    verified = _merge_collisions([verify(item) for item in propose(residual)], residual)
    used_txns = {value for decision in verified for value in decision.txn_ids}
    used_utrs = {value for decision in verified for value in decision.utrs}
    for txn in residual.gateway:
        if txn.txn_id not in used_txns:
            verified.append(Decision((txn.order_id,), (txn.txn_id,), (), "exception", 2,
                "agent_abstain", 0.0, "No narration evidence produced a verifiable unique link.",
                "none", "agent_abstained", True))
    for bank in residual.bank:
        if bank.utr not in used_utrs:
            verified.append(Decision((), (), (bank.utr,), "exception", 2, "agent_abstain", 0.0,
                "No transaction could be verified from bank narration.", "none",
                "agent_abstained", True))
    return tuple(verified)
