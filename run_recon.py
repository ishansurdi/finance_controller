"""Run deterministic reconciliation and print an honest scorecard."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from recon.audit import write_audit, write_exceptions
from recon.agents import reconcile_residual
from recon.engine import control_total, reconcile
from recon.evaluate import ablation, evaluate, score_tier_two
from recon.load import load_bank, load_gateway, load_ground_truth, load_ledger, structural_anomalies
from recon.residual import conclusive_decisions, isolate_residual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-backend", choices=("offline", "openai"), default="offline")
    args = parser.parse_args()
    if args.agent_backend == "openai":
        from recon.openai_backend import OpenAIBackend
        try:
            backend = OpenAIBackend()
        except ValueError as error:
            parser.error(str(error))
    else:
        from recon.agents import EvidenceBackend
        backend = EvidenceBackend()
    root = Path(__file__).resolve().parent
    data, out = root / "data", root / "out"
    ledger = load_ledger(data / "ledger.csv")
    gateway = load_gateway(data / "gateway.csv")
    bank = load_bank(data / "bank.csv")
    truth = load_ground_truth(data / "ground_truth.csv")
    anomalies = structural_anomalies(ledger, gateway)
    started = perf_counter()
    deterministic = reconcile(ledger, gateway, bank)
    residual = isolate_residual(ledger, gateway, bank, deterministic)
    agent_decisions = reconcile_residual(residual, backend)
    retained = conclusive_decisions(bank, deterministic)
    decisions = retained + agent_decisions
    elapsed = perf_counter() - started
    record_count = len(ledger) + len(gateway) + len(bank)
    deterministic_report = evaluate(deterministic, truth, elapsed, record_count,
                                    control_total(deterministic, gateway, bank))
    agent_report = evaluate(decisions, truth, elapsed, record_count,
                            control_total(decisions, gateway, bank))
    report = {"deterministic_only": deterministic_report, "with_agents": agent_report,
              "ablation": ablation(deterministic_report, agent_report),
              "tier_two_score": score_tier_two(deterministic, decisions, truth),
              "agent_backend": backend.name,
              "structural_anomalies": list(anomalies)}
    out.mkdir(exist_ok=True)
    run_at = datetime.now(timezone.utc).isoformat()
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_exceptions(out / "exceptions.csv", decisions)
    write_audit(out / "audit_trail.csv", decisions, run_at)

    print("AI FINANCE CONTROLLER - ABLATION SCORECARD")
    print("                         DETERMINISTIC   + AGENTS")
    print(f"Match rate              {deterministic_report['match_rate']:>12.1%}   {agent_report['match_rate']:>8.1%}")
    print(f"Exception precision     {deterministic_report['exception_precision']:>12.1%}   {agent_report['exception_precision']:>8.1%}")
    print(f"Exception recall        {deterministic_report['exception_recall']:>12.1%}   {agent_report['exception_recall']:>8.1%}")
    tier_two = report["tier_two_score"]
    print(f"Tier 2 recovery         {tier_two['correct_recoveries']:>7}/{tier_two['resolvable_residual_groups']:<4} "
          f"({tier_two['recovery_accuracy']:.1%} accurate)")
    print(f"Correct safety escalations{tier_two['correct_safety_escalations']:>9}")
    print(f"Resolvable misses       {tier_two['resolvable_escalations']:>12}")
    print(f"Total honest exceptions{report['ablation']['exceptions_escalated_after_agents']:>12}")
    print(f"Throughput              {agent_report['throughput_records_per_second']:>12,.0f} records/sec")
    print(f"Control residual        {agent_report['control_totals']['residual_paise']:>+12,} paise")
    print("\nPER-BREAK ACCURACY")
    for name, values in agent_report["per_break_type"].items():
        print(f"  {name:<20} {values['correct']:>3}/{values['total']:<3} {values['accuracy']:>7.1%}")
    exceptions = [d for d in decisions if d.state == "exception"]
    print(f"\nEXCEPTIONS ({len(exceptions)})")
    for item in exceptions[:10]:
        ids = "|".join(item.order_ids + item.txn_ids + item.utrs)
        print(f"  {item.reason_code:<42} {ids}")
    if len(exceptions) > 10:
        print(f"  ... and {len(exceptions) - 10} more; see out/exceptions.csv")


if __name__ == "__main__":
    main()
