# Test results

Run from this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile app.py src/engine.py
node --check static/app.js
```

## Results

- Known example: **passed**. Two-round weighted example checks MD61 target plus buffer and MRP netting against on-hand and inbound quantities.
- Realistic data: **passed**. Reads the provided source set; identifies rounds 1–8 complete and round 9 incomplete; selects round 9 and verifies actual round-8 valuation.
- Invalid inputs: **passed**. Unparseable numeric values and unknown product material codes return safe defaults rather than raising calculation errors.
- Report detection: **passed**. Detailed sales, inventory and purchase-order workbooks are identified by headers.
- Independent verification: **passed**. Recomputes the round-9 Milk forecast from raw round 6/7 sales rows and round-8 detailed sales, then compares it with the engine output.
- Python compile check: **passed**.
- JavaScript syntax check: **passed**.
- Local app/API and rendered UI: **passed**. Health and state endpoints responded on localhost; Command center, Final round plan, Pricing, Data center and Finance + valuation rendered with source-derived values.
- Upload smoke test: **passed**. A temporary summary workbook was accepted through the local upload endpoint and header-detected; the probe file was removed after the check.
- Streamlit deployment entry point: **passed**. `streamlit_app.py` compiled, started locally, rendered the Round 9 dashboard, and displayed the source-derived plan through the Streamlit interface.
- Packaged baseline data: **passed**. The calculation engine used `data/baseline/` rather than the original Downloads paths and produced the expected 2,403-unit purchase recommendation and €1,125,700.90 actual valuation.

The app does not write to SAP. Inventory is undated and financial postings are outdated, which remain visible warnings in the UI.
