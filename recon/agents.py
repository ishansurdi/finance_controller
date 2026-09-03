"""Evidence proposer and independent maker-checker verifier for Tier 2."""

import re
import json
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Protocol

from .models import BankRow, Decision, GatewayRow
from .residual import Residual

ID_PATTERN = re.compile(r"\b(?:TXN|ORD)\d{5}\b")
ADJUSTMENT_PATTERN = re.compile(r"\bADJ\s+(\d+)P\b", re.IGNORECASE)


class NarrationBackend(Protocol):
    name: str

    def extract_ids(self, narration: str) -> tuple[str, ...]: ...


class EvidenceBackend:
    """Reproducible offline backend used by tests and deterministic demos."""

    name = "offline_evidence_backend"

    def extract_ids(self, narration: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(ID_PATTERN.findall(narration.upper())))


class AbstainBackend:
    """Network-failure fallback: create no proposals and escalate the residual."""

    name = "abstain_all_fallback"

    def extract_ids(self, narration: str) -> tuple[str, ...]:
        return ()


class ReplayBackend:
    """Replay checked-in, previously reviewed extraction responses offline."""

    name = "recorded_replay"

    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.model = payload["model"]
        self.temperature = payload["temperature"]
        self.responses = payload["responses"]

    def extract_ids(self, narration: str) -> tuple[str, ...]:
        return tuple(self.responses.get(narration, ()))


@dataclass(frozen=True)
class Proposal:
    transaction: GatewayRow
    bank: BankRow
    extracted_ids: tuple[str, ...]
    rationale: str


def propose(residual: Residual, backend: NarrationBackend | None = None) -> tuple[Proposal, ...]:
    """Interpret narration and propose links without authority to close books."""
    backend = backend or EvidenceBackend()
    txns = {row.txn_id: row for row in residual.gateway}
    orders = {row.order_id: row for row in residual.gateway}
    proposals: list[Proposal] = []
    for bank in residual.bank:
        ids = backend.extract_ids(bank.bank_narration)
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
    adjustments = ADJUSTMENT_PATTERN.findall(bank.bank_narration)
    documented_adjustment = int(adjustments[0]) if len(adjustments) == 1 else 0
    adjustment_agrees = drift == documented_adjustment
    if not references_agree or not adjustment_agrees:
        failed_checks = []
        if not references_agree:
            failed_checks.append(f"references must be {txn.txn_id} and {txn.order_id}")
        if not adjustment_agrees:
            failed_checks.append(
                f"documented adjustment {documented_adjustment:+d} does not equal drift {drift:+d} paise"
            )
        return Decision((txn.order_id,), (txn.txn_id,), (bank.utr,), "exception", 2,
            "agent_verifier_disagreement", 0.35,
            f"{proposal.rationale} Verifier rejected: {'; '.join(failed_checks)}.",
            f"drift={drift}paise; documented_adjustment={documented_adjustment}paise",
            "proposer_verifier_disagreement", True,
            proposal.rationale,
            f"Rejected: {'; '.join(failed_checks)}.")
    return Decision((txn.order_id,), (txn.txn_id,), (bank.utr,), "auto_matched", 2,
        "narration_evidence", 0.96,
        f"{proposal.rationale} Verifier confirmed both transaction and order references; "
        f"documented adjustment is {drift:+d} paise.", f"drift={drift}paise", "", False,
        proposal.rationale,
        f"Confirmed both references and documented adjustment {documented_adjustment:+d} paise.")


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
            f"members={len(group)}; drift=0paise", "", False,
            " | ".join(item.proposer_output for item in group),
            "Confirmed each narrated pair is unique within the equal-amount collision.",
        ))
    return merged


def reconcile_residual(residual: Residual,
                       backend: NarrationBackend | None = None) -> tuple[Decision, ...]:
    """Run proposer then verifier and preserve unresolved records as exceptions."""
    verified = _merge_collisions([verify(item) for item in propose(residual, backend)], residual)
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
