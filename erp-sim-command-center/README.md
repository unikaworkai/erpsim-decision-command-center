# ERPsim Decision Command Center

Phase 1 planning application for the ERPsim Logistics Extended game. It reads the provided Excel exports, calculates an explainable demand plan, separates MD61 from expected MRP need, recommends procurement quantities when dated stock and open-order data exist, allocates regional transfers, carries forward observed prices, and exports a SAP-side decision sheet.

## Deploy publicly with Streamlit Community Cloud

The app is ready for Streamlit deployment. The public entry point is `streamlit_app.py`.

1. Create a **private** GitHub repository. This protects the included baseline workbooks and source code.
2. Upload all project files, including the `data/baseline/` folder. Do not upload the ignored `data/uploads/` or `data/snapshots/` folders.
3. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and choose **Create app**.
4. Select the GitHub repository and `main` branch, then enter `streamlit_app.py` as the main file path.
5. Choose a memorable public app URL and click **Deploy**.
6. Open the completed `https://...streamlit.app` URL in a private browser window. It should work without a login.

The public app shows planning outputs, not downloadable source workbooks. Excel files uploaded through the sidebar are parsed for the current browser session and are not saved by the application. Do not put API keys, passwords, SAP credentials, or personal information in GitHub.

When you update a file in the GitHub repository, Streamlit rebuilds the public app automatically.

## Run the Streamlit version locally

```bash
cd "/Users/unikamaharjan/Documents/Codex/2026-10-04/files-mentioned-by-the-user-o/outputs/erp-sim-command-center"
python3 -m pip install -r requirements.txt
python3 -m streamlit run streamlit_app.py
```

Streamlit opens a local browser address, usually `http://localhost:8501`. Stop it with **Ctrl+C**.

## Original local-server launch

From Terminal, run:

```bash
cd "/Users/unikamaharjan/Documents/Codex/2026-10-04/files-mentioned-by-the-user-o/outputs/erp-sim-command-center"
python3 app.py
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). Stop the server with **Ctrl+C**. The only non-standard Python library is `openpyxl`; it is available in the bundled workspace Python runtime. If your system `python3` does not have it, launch with:

```bash
"/Users/unikamaharjan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" app.py
```

The app starts with the workbooks from the provided Downloads paths. The current source set contains a partial round 9 (day 1 only), so the default is to plan round 9 using complete rounds 1–8. On **Data center**, upload newer `.xlsx` exports; column headers identify report types. Uploaded copies are kept locally in `data/uploads/`. Saved round snapshots are in `data/snapshots/`. No SAP connection or cloud API is used.

If your Python does not have `openpyxl`, install the one dependency with `python3 -m pip install -r requirements.txt`.

## Use before an ERPsim round

1. Open **Data center** and verify report status and dates. The supplied inventory export has no simulation date, so confirm it matches your sales cutoff.
2. Use the round selector to choose the round you plan to enter. For example, after round 8 select **Plan round 9 · in progress**. Partial sales from the target round are excluded; historical replay uses only earlier complete rounds, and undated stock and PO snapshots are excluded during replay.
3. Review **Forecast + MRP** in SAP order: enter the MD61 target, then run MD01 and compare its actual requisitions with the estimate.
4. Review **Procurement**, **Stock transfer**, and **Pricing**. Transfer quantities copy to clipboard; prices remain one per product across regions.
5. Download the decision sheet or save a snapshot. Enter decisions in SAP yourself; this app does not execute transactions.
6. After the round, upload the latest reports and use **Round review** to compare the forecast with actual sales.

## Phase 1 calculation notes

- Forecast = the latest three complete rounds weighted 20%, 30%, and 50% from oldest to newest. Incomplete rounds are excluded.
- MD61 target = weighted forecast + a variability buffer based on daily sales variation over the selected protection horizon (transfer days + three days; five days at the default two-day cycle).
- Forecast confidence is Medium only after two or more completed rounds and a last-round backtest error no greater than 30%; otherwise Low.
- Expected MRP requirement = max(0, MD61 − current total stock − confirmed inbound quantity). It is left pending if those snapshots are missing.
- Transfer target uses recent regional sales shares, cycle demand, the same proportional buffer and regional stock; dispatched quantities are capped by central warehouse stock.
- Purchase value uses expected net requirement × supplied reference cost. The source's EUR 1,000 PO cost is shown once as an estimate.
- Price recommendation holds the observed list because the available history cannot establish a controlled price response. Expected gross profit uses recent transaction COGS where present, or the supplier reference cost otherwise.
- Actual company valuation history is shown. A future valuation is not calculated because the official credit-rating and risk-rate table is absent.

See [BUILD_NOTE.md](BUILD_NOTE.md) for the internal game-rules summary, architecture, revisions and limits.
