"""Thin read-only demo surface for reconciliation outputs."""

import csv
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent


def rupees(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    whole, fraction = divmod(abs(paise), 100)
    return f"{sign}INR {whole:,}.{fraction:02d}"


st.set_page_config(page_title="AI Finance Controller", layout="wide")
st.title("AI Finance Controller")
st.caption("Deterministic reconciliation, verified residual recovery, and honest escalation")

report_path = ROOT / "out" / "report.json"
exceptions_path = ROOT / "out" / "exceptions.csv"
if not report_path.exists() or not exceptions_path.exists():
    st.error("Run `python run_recon.py` first to generate the scorecard.")
    st.stop()

report = json.loads(report_path.read_text(encoding="utf-8"))
before = report["deterministic_only"]
after = report["with_agents"]
ablation = report["ablation"]

st.subheader("Measured contribution")
first, second, third, fourth = st.columns(4)
first.metric("Deterministic match rate", f"{before['match_rate']:.1%}")
second.metric("With agents", f"{after['match_rate']:.1%}",
              f"+{ablation['match_rate_delta']:.1%}")
third.metric("Groups recovered", ablation["agent_groups_recovered"])
fourth.metric("Tier 2 escalations", ablation["tier_two_escalations"])
st.caption(f"Backend provenance: `{report['agent_backend']}`")

st.subheader("Risk and controls")
risk_one, risk_two, risk_three = st.columns(3)
risk_one.metric("Exception precision", f"{after['exception_precision']:.1%}")
risk_two.metric("Exception recall", f"{after['exception_recall']:.1%}")
risk_three.metric("Control residual", rupees(after["control_totals"]["residual_paise"]))
costs = after["error_costs"]
st.info(
    f"Cost basis: human review {rupees(costs['human_review_cost_paise'])} per case; "
    f"false auto-match {rupees(costs['false_auto_match_cost_paise'])} expected loss. "
    "The decision gate therefore prefers a cheap review over silently corrupting books."
)

st.subheader("Accuracy by break type")
rows = [{"break_type": name, **values} for name, values in after["per_break_type"].items()]
st.dataframe(rows, hide_index=True, use_container_width=True)

st.subheader("Exception workbench")
with exceptions_path.open(newline="", encoding="utf-8") as handle:
    exceptions = list(csv.DictReader(handle))
labels = [" | ".join(filter(None, (row["reason_code"], row["order_ids"], row["utrs"])))
          for row in exceptions]
selected = exceptions[labels.index(st.selectbox("Select an exception", labels))]
left, right = st.columns(2)
left.write("**Reason code**", selected["reason_code"])
left.write("**Confidence**", selected["confidence"])
left.write("**Explanation**", selected["explanation"])
right.write("**Orders**", selected["order_ids"] or "None")
right.write("**Transactions**", selected["txn_ids"] or "None")
right.write("**Bank credits**", selected["utrs"] or "None")
