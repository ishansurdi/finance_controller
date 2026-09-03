"""Thin read-only demo surface for reconciliation outputs."""

import csv
import json
import subprocess
import sys
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

with st.sidebar:
    st.header("Live batch controls")
    group_count = st.slider("Match groups", 50, 250, 100, 10)
    hard_multiplier = st.slider("Hard-case intensity", 0.5, 2.0, 1.0, 0.1)
    if st.button("Regenerate and run", type="primary", use_container_width=True):
        generator = subprocess.run(
            [sys.executable, str(ROOT / "generate_data.py"), "--groups", str(group_count),
             "--hard-multiplier", str(hard_multiplier)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if generator.returncode != 0:
            st.error(generator.stderr)
            st.stop()
        reconciliation = subprocess.run(
            [sys.executable, str(ROOT / "run_recon.py"), "--agent-backend", "offline"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if reconciliation.returncode != 0:
            st.error(reconciliation.stderr)
            st.stop()
        st.success("Dataset regenerated and reconciliation completed.")

report_path = ROOT / "out" / "report.json"
exceptions_path = ROOT / "out" / "exceptions.csv"
if not report_path.exists() or not exceptions_path.exists():
    st.error("Run `python run_recon.py` first to generate the scorecard.")
    st.stop()

report = json.loads(report_path.read_text(encoding="utf-8"))
before = report["deterministic_only"]
after = report["with_agents"]
ablation = report["ablation"]
tier_two = report["tier_two_score"]

st.subheader("Measured contribution")
first, second, third, fourth = st.columns(4)
first.metric("Deterministic match rate", f"{before['match_rate']:.1%}")
second.metric("With agents", f"{after['match_rate']:.1%}",
              f"+{ablation['match_rate_delta']:.1%}")
third.metric("Recovery accuracy", f"{tier_two['recovery_accuracy']:.1%}",
             f"{tier_two['correct_recoveries']}/{tier_two['resolvable_residual_groups']} groups")
fourth.metric("Safety escalations", tier_two["correct_safety_escalations"],
              f"{tier_two['resolvable_escalations']} resolvable misses")
st.caption(f"Backend provenance: `{report['agent_backend']}`")
if ablation["false_auto_matches_added"] == 0:
    st.success(
        f"The precision decline comes from {tier_two['resolvable_escalations']} good groups sent "
        f"to review—not false auto-matches. Tier 2 avoided {ablation['human_reviews_avoided']} "
        f"reviews and saved {rupees(ablation['expected_cost_savings_paise'])} at the stated costs."
    )
else:
    st.error(
        f"Tier 2 introduced {ablation['false_auto_matches_added']} false auto-matches. "
        "Tighten the confidence gate before presenting."
    )

st.subheader("Risk and controls")
risk_one, risk_two, risk_three = st.columns(3)
risk_one.metric("Exception precision", f"{after['exception_precision']:.1%}")
risk_two.metric("Exception recall", f"{after['exception_recall']:.1%}")
controls = after["control_totals"]
risk_three.metric("Unexplained residual", rupees(controls["unexplained_residual_paise"]),
                  f"Raw variance {rupees(controls['raw_residual_paise'])}")
with st.expander("Explain the control variance"):
    st.write(
        f"Verified tolerances and documented adjustments explain "
        f"{rupees(controls['explained_variance_paise'])}."
    )
    st.dataframe(controls["variance_breakdown"], hide_index=True, use_container_width=True)
costs = after["error_costs"]
st.info(
    f"Cost basis: human review {rupees(costs['human_review_cost_paise'])} per case; "
    f"false auto-match {rupees(costs['false_auto_match_cost_paise'])} expected loss. "
    "The decision gate therefore prefers a cheap review over silently corrupting books."
)
st.caption("Confidence gate selected from expected business cost, not F1.")
st.line_chart(report["confidence_cost_curve"]["points"], x="threshold", y="total")

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
left.markdown(f"**Reason code:** `{selected['reason_code']}`")
left.markdown(f"**Confidence:** {selected['confidence']}")
left.markdown(f"**Decision path:** Tier {selected['tier']} · `{selected['rule_name']}`")
left.markdown("**Explanation**")
left.write(selected["explanation"])
left.markdown("**Proposer output**")
left.write(selected["proposer_output"] or "Not invoked — deterministic control")
left.markdown("**Verifier output**")
left.write(selected["verifier_output"] or "Not invoked — deterministic control")
right.markdown("**Orders**")
right.write(selected["order_ids"] or "None")
right.markdown("**Transactions**")
right.write(selected["txn_ids"] or "None")
right.markdown("**Bank credits**")
right.write(selected["utrs"] or "None")
