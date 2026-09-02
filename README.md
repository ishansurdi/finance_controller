# AI Finance Controller

A conservative multi-source reconciliation system for ledger, gateway, and bank data.
It resolves safe cases deterministically, sends evidence-rich residuals through a
maker-checker layer, and measures the incremental contribution with an ablation.

## Run

```bash
python generate_data.py
python run_recon.py
python -m unittest discover -s tests -v
```

The default offline evidence backend keeps CI reproducible and is identified in the
report. To run the actual model-backed narration interpreter:

```bash
set OPENAI_API_KEY=your-key
python run_recon.py --agent-backend openai
```

The hosted adapter uses Structured Outputs, does not store responses, and never has
authority to close the books: the local verifier remains the maker-checker gate.

## Demo

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

Generated artifacts are written to `out/report.json`, `out/exceptions.csv`, and
`out/audit_trail.csv`.
