"""Run deterministic reconciliation and print an honest scorecard."""

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from recon.audit import write_audit, write_exceptions
from recon.engine import control_total, reconcile
from recon.evaluate import evaluate
from recon.load import load_bank, load_gateway, load_ground_truth, load_ledger, structural_anomalies


def main() -> None:
    root = Path(__file__).resolve().parent
    data, out = root / "data", root / "out"
    ledger = load_ledger(data / "ledger.csv")
    gateway = load_gateway(data / "gateway.csv")
    bank = load_bank(data / "bank.csv")
    truth = load_ground_truth(data / "ground_truth.csv")
    anomalies = structural_anomalies(ledger, gateway)
    started = perf_counter()
    decisions = reconcile(ledger, gateway, bank)
    elapsed = perf_counter() - started
    report = evaluate(decisions, truth, elapsed, len(ledger) + len(gateway) + len(bank),
                      control_total(decisions, gateway, bank))
    report["structural_anomalies"] = list(anomalies)
    out.mkdir(exist_ok=True)
    run_at = datetime.now(timezone.utc).isoformat()
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_exceptions(out / "exceptions.csv", decisions)
    write_audit(out / "audit_trail.csv", decisions, run_at)

    print("AI FINANCE CONTROLLER — DETERMINISTIC SCORECARD")
    print(f"Match rate              {report['match_rate']:.1%}")
    print(f"Exception precision     {report['exception_precision']:.1%}")
    print(f"Exception recall        {report['exception_recall']:.1%}")
    print(f"Throughput              {report['throughput_records_per_second']:,.0f} records/sec")
    print(f"Control residual        {report['control_totals']['residual_paise']:+,} paise")
    print("\nPER-BREAK ACCURACY")
    for name, values in report["per_break_type"].items():
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

