"""Public Streamlit deployment for the ERPsim Decision Command Center.

This entry point keeps all uploaded workbooks in memory for the current browser
session. It does not save student uploads to the server filesystem.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import streamlit as st

from src.engine import PRODUCTS, REGIONS, build_plan, load_data


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="ERPsim Decision Command Center",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
          .stApp { background: #f5f7fb; color: #172b4d; }
          [data-testid="stSidebar"] { background: #11253f; }
          [data-testid="stSidebar"] * { color: #f6f9ff; }
          h1, h2, h3 { color: #0b5cab; }
          .eyebrow { color: #5c718e; font-size: .77rem; font-weight: 700; letter-spacing: .11em; }
          .caption-box { background: #e8f1fb; border-left: 4px solid #0b74de; border-radius: 6px; padding: .8rem 1rem; margin: .5rem 0 1.1rem; }
          .warning-box { background: #fff5db; border-left: 4px solid #e9a400; border-radius: 6px; padding: .8rem 1rem; margin: .5rem 0 1.1rem; }
          .footer-note { color: #53647b; font-size: .86rem; margin: 1.5rem 0 .5rem; }
          div[data-testid="stMetric"] { background: white; border: 1px solid #dbe4f0; border-radius: 8px; padding: .6rem .8rem; }
          .stDownloadButton button, .stButton button { border-radius: 6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def eur(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"€{value:,.{decimals}f}"


def num(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def uploaded_data(files):
    """Parse baseline plus current-session uploads without retaining uploaded files."""
    if not files:
        return load_data()
    with TemporaryDirectory(prefix="erpsim_upload_") as temp_dir:
        folder = Path(temp_dir)
        for file in files:
            safe_name = Path(file.name).name
            (folder / safe_name).write_bytes(file.getvalue())
        return load_data(folder)


def planner_table(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Product": row["product"],
                "Forecast": row["forecast"],
                "Safety buffer": row["buffer"],
                "MD61 target": row["md61"],
                "On hand": row["inventory"],
                "Inbound PO": row["inbound"],
                "Expected MRP need": row["mrp"],
                "Suggested price": row["recommended_price"],
                "Risk": row["risk"],
            }
            for row in rows
        ]
    )


def make_csv(plan: dict) -> bytes:
    records = []
    for row in plan["rows"]:
        records.append(
            {
                "Product": row["product"],
                "Forecast": row["forecast"],
                "Safety buffer": row["buffer"],
                "MD61 target": row["md61"],
                "On hand": row["inventory"],
                "Inbound PO": row["inbound"],
                "Expected MRP need": row["mrp"],
                "Reference unit cost EUR": row["cost"],
                "Estimated PO value EUR": row["po_value"],
                "Current price EUR": row["price"],
                "Suggested price EUR": row["recommended_price"],
                "Transfer mode": plan["mode"],
                "North": (row["transfers"] or {}).get("North"),
                "South": (row["transfers"] or {}).get("South"),
                "West": (row["transfers"] or {}).get("West"),
                "Confidence": row["confidence"],
            }
        )
    return pd.DataFrame(records).to_csv(index=False).encode("utf-8")


def title(kicker: str, heading: str, text: str) -> None:
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.title(heading)
    st.caption(text)


def warning(text: str) -> None:
    st.markdown(f'<div class="warning-box"><b>Data check</b><br>{text}</div>', unsafe_allow_html=True)


def command_page(plan: dict) -> None:
    title(
        "ROUND DECISION WORKSPACE",
        f"Round {plan['target_round']} planner",
        f"Based on {len(plan['historical_rounds'])} completed rounds through round {plan['through_round']}.",
    )
    if plan["data_warning"]:
        warning(plan["data_warning"])
    financial = plan["financial"]
    risk_count = sum(row["risk"] in {"High", "Watch"} for row in plan["rows"])
    cols = st.columns(5)
    cols[0].metric("Company valuation", eur(plan["company_value"]), "actual imported value")
    cols[1].metric("Cumulative profit", eur(financial.get("profit")), f"through R{financial.get('through_round') or '—'}")
    cols[2].metric("Expected PO need", f"{num(plan['purchase_qty'])} units", eur(plan["purchase_value"]))
    cols[3].metric("Expected gross profit", eur(plan["expected_gross_profit"]), percent(plan["expected_margin"]))
    cols[4].metric("Products to watch", f"{risk_count} / 6", "stock lead-time screen")
    st.subheader("Recommended round plan")
    st.dataframe(planner_table(plan["rows"]), hide_index=True, width="stretch")
    left, right = st.columns((2, 1))
    with left:
        st.subheader("Priority actions")
        for row in sorted(plan["rows"], key=lambda item: (item["mrp"] is None, -(item["mrp"] or 0)))[:3]:
            action = "Upload current inventory and PO status" if row["mrp"] is None else f"Review expected MRP requirement: {num(row['mrp'])} units"
            st.write(f"**{row['product']}** — {action}")
        st.write("**Pricing** — retain one price per product until price-response evidence supports a change.")
    with right:
        st.subheader("SAP entry order")
        st.write("1. MD61 demand")
        st.write("2. MD01 and review PR")
        st.write("3. ME59N purchase order")
        st.write("4. ZMB1B transfer")
        st.write("5. VK32 price")


def forecast_page(plan: dict) -> None:
    title("SAP WORKFLOW · 01 / 02", "Forecast + MRP", "MD61 is the demand target. It is not the purchase quantity.")
    st.markdown(
        '<div class="caption-box"><b>Forecast rule</b><br>Latest three complete rounds are weighted 20% / 30% / 50%, newest highest. The MD61 target adds a transparent variability buffer.</div>',
        unsafe_allow_html=True,
    )
    forecast = pd.DataFrame(
        [
            {
                "Product": r["product"], "Previous round": r["previous_sales"], "Daily rate": r["daily"],
                "Forecast": r["forecast"], "Buffer": r["buffer"], "MD61 target": r["md61"],
                "Last-round error": percent(r["backtest_error"]), "Confidence": r["confidence"],
            }
            for r in plan["rows"]
        ]
    )
    st.subheader("Step 1: MD61 planned independent requirements")
    st.dataframe(forecast, hide_index=True, width="stretch")
    mrp = pd.DataFrame(
        [
            {"Product": r["product"], "MD61 target": r["md61"], "On hand": r["inventory"],
             "Inbound PO": r["inbound"], "Expected purchase requisition": r["mrp"]}
            for r in plan["rows"]
        ]
    )
    st.subheader("Step 2: MD01 expected net requirement")
    st.dataframe(mrp, hide_index=True, width="stretch")
    warning(plan["data_warning"])


def procurement_page(plan: dict) -> None:
    title("SAP WORKFLOW · 03", "Procurement", "Review expected net need before creating purchase orders in SAP.")
    table = pd.DataFrame(
        [
            {"Product": r["product"], "Expected quantity": r["mrp"], "Reference unit cost": r["cost"],
             "Estimated merchandise value": r["po_value"], "Action": "Review PO" if r["mrp"] else "No PO"}
            for r in plan["rows"]
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "Reference unit cost": st.column_config.NumberColumn(format="€%.2f"),
        "Estimated merchandise value": st.column_config.NumberColumn(format="€%.2f"),
    })
    cols = st.columns(3)
    cols[0].metric("Merchandise estimate", eur(plan["purchase_value"]))
    cols[1].metric("PO / transport cost", eur(plan["fixed_po_cost"]), "source rule row")
    cols[2].metric("Estimated cash need", eur(plan["purchase_value"] + plan["fixed_po_cost"]))
    st.caption("The source identifies a €1,000 PO cost. Verify current SAP cash, credit, and delivery timing before ME59N.")


def transfer_page(plan: dict) -> None:
    title("SAP WORKFLOW · 04", "Stock transfer", "Use this table as an allocation plan and verify actual stock in SAP before ZMB1B.")
    allocations = []
    for row in plan["rows"]:
        transfers = row["transfers"] or {}
        allocations.append({"Product": row["product"], **{region: transfers.get(region) for region in REGIONS}})
    st.subheader(f"Recommended mode: {plan['mode']} · {plan['frequency']}-day cycle")
    st.dataframe(pd.DataFrame(allocations), hide_index=True, width="stretch")
    st.caption("Transfers assume the planned replenishment reaches the central warehouse. The application caps quantities by projected central availability.")
    regional = pd.DataFrame(
        [{"Product": r["product"], **{f"{region} share": r["regional_shares"][region] for region in REGIONS}} for r in plan["rows"]]
    )
    st.subheader("Recent regional demand mix")
    st.dataframe(regional, hide_index=True, width="stretch", column_config={
        f"{region} share": st.column_config.NumberColumn(format="%.1f%%") for region in REGIONS
    })
    warning(plan["data_warning"])


def pricing_page(plan: dict) -> None:
    title("SAP WORKFLOW · 05", "Pricing", "One price per product applies across North, South, and West.")
    table = pd.DataFrame(
        [
            {"Product": r["product"], "Cost basis": r["cost_basis"], "Current price": r["price"],
             "Gross margin": r["margin"], "Suggested price": r["recommended_price"],
             "Confidence": r["price_confidence"], "Reason": r["price_reason"]}
            for r in plan["rows"]
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "Cost basis": st.column_config.NumberColumn(format="€%.2f"),
        "Current price": st.column_config.NumberColumn(format="€%.2f"),
        "Suggested price": st.column_config.NumberColumn(format="€%.2f"),
        "Gross margin": st.column_config.NumberColumn(format="%.1f%%"),
    })
    st.info("The supplied sales history does not isolate price changes from stock availability, so the app holds the observed price list instead of inventing price elasticity.")


def finance_page(plan: dict, valuations: list[dict]) -> None:
    title("FINANCIAL MONITOR", "Finance + valuation", "Actual imported results are separated from forward planning estimates.")
    finance = plan["financial"]
    cols = st.columns(5)
    cols[0].metric("Company valuation", eur(plan["company_value"]))
    cols[1].metric("Cumulative profit", eur(finance.get("profit")))
    cols[2].metric("Cumulative revenue", eur(finance.get("revenue")))
    cols[3].metric("Gross profit", eur(finance.get("gross_profit")))
    cols[4].metric("Bank cash", eur(finance.get("cash")))
    if valuations:
        history = pd.DataFrame(valuations)
        history["Period"] = history.apply(lambda r: f"R{int(r['round'])} D{int(r['day'])}", axis=1)
        st.subheader("Company valuation history")
        st.line_chart(history.set_index("Period")["value"], color="#0b74de")
    warning("The supplied files do not include the official valuation credit-rating and risk-rate lookup. The app reports imported actual valuation; it does not calculate a forward valuation.")


def final_page(plan: dict) -> None:
    title("SAP ENTRY SEQUENCE", "Final round plan", "Use this sheet beside SAP. This app never executes SAP transactions.")
    warning(plan["data_warning"])
    output = []
    for row in plan["rows"]:
        output.append({
            "Product": row["product"], "Forecast": row["forecast"], "Safety buffer": row["buffer"],
            "MD61 target": row["md61"], "MRP need": row["mrp"], "Unit cost": row["cost"],
            "PO value": row["po_value"], "VK32 price": row["recommended_price"],
            "North": (row["transfers"] or {}).get("North"), "South": (row["transfers"] or {}).get("South"),
            "West": (row["transfers"] or {}).get("West"),
        })
    st.dataframe(pd.DataFrame(output), hide_index=True, width="stretch", column_config={
        "Unit cost": st.column_config.NumberColumn(format="€%.2f"),
        "PO value": st.column_config.NumberColumn(format="€%.2f"),
        "VK32 price": st.column_config.NumberColumn(format="€%.2f"),
    })
    st.download_button(
        "Download decision sheet (.csv)", make_csv(plan),
        file_name=f"ERPsim_Round_{plan['target_round']}_Decision_Sheet.csv", mime="text/csv",
        width="stretch",
    )
    cols = st.columns(4)
    cols[0].metric("Expected revenue", eur(plan["expected_revenue"]))
    cols[1].metric("Expected gross profit", eur(plan["expected_gross_profit"]))
    cols[2].metric("Expected ending stock", f"{num(plan['expected_end_inventory'])} units")
    cols[3].metric("Estimated cash need", eur(plan["purchase_value"] + plan["fixed_po_cost"]))


def review_page(plan: dict, data: dict) -> None:
    title("LEARN AFTER EACH ROUND", "Round review", "Compare the prepared forecast with actual sales after a round finishes.")
    actuals = data["round_totals"].get(plan["target_round"], {})
    rows = []
    for row in plan["rows"]:
        actual = actuals.get(row["code"])
        error = None if actual is None else (row["forecast"] - actual) / max(1, actual)
        rows.append({"Product": row["product"], "Forecast prepared": row["forecast"], "Actual sales": actual,
                     "Forecast error": error, "Status": "Awaiting actual" if actual is None else "Compare and adjust"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Forecast error": st.column_config.NumberColumn(format="%.1f%%")
    })
    st.caption("Partial target-round sales are not used in the forecast. Review actuals only after the round completes.")


def data_page(data: dict) -> None:
    title("SOURCE MANAGEMENT", "Data center", "Starter reports are included with the app. Uploaded workbooks are used only for this browser session.")
    files = pd.DataFrame(data["files"])
    st.dataframe(files, hide_index=True, width="stretch")
    st.subheader("Data coverage")
    first, second, third = st.columns(3)
    first.metric("Latest sales round", data["max_round"] or "—")
    second.metric("Completed through", max(data["complete_rounds"], default=0) or "—")
    third.metric("Incomplete round", ", ".join(map(str, data["incomplete_rounds"])) or "None")
    warning("The supplied inventory export has no simulation date. Before entering quantities in SAP, confirm that inventory, purchase orders, and sales reports use the same simulation cutoff.")


def rules_page(data: dict) -> None:
    title("REFERENCE & ASSUMPTIONS", "Game rules", "Workbook rules and planning assumptions are shown separately.")
    rules = data.get("rules", {})
    items = []
    for key, fallback in [("Lead_Time", "1–2 days"), ("PO_Cost", "1,000"), ("Transfer_Cost", "100"),
                          ("Storage_Capacity", "4,000"), ("Storage_Extra_Capacity_Cost", "300")]:
        source = rules.get(key, {})
        items.append({"Rule": key.replace("_", " "), "Value": source.get("value") or source.get("detail") or fallback})
    st.dataframe(pd.DataFrame(items), hide_index=True, width="stretch")
    st.subheader("Planning assumptions")
    st.write("Forecast: three latest complete rounds weighted 20% / 30% / 50%.")
    st.write("Safety buffer: daily demand variation over the selected protection horizon.")
    st.write("Price: current list price held because price response cannot be estimated reliably from the supplied data.")
    st.write("Valuation: future valuation is not calculated because the official lookup is absent.")


def main() -> None:
    inject_styles()
    st.sidebar.title("ERPsim Command Center")
    st.sidebar.caption("Logistics Extended · Phase 1")
    uploads = st.sidebar.file_uploader(
        "Upload newer ERP reports (.xlsx)", type=["xlsx"], accept_multiple_files=True,
        help="Files are read for this browser session and are not saved by the deployed app.",
    )
    with st.spinner("Reading reports and calculating the plan..."):
        data = uploaded_data(uploads)

    default_round = max(data["complete_rounds"], default=0) + 1
    round_options = list(range(1, data["max_round"] + 2)) or [1]
    target = st.sidebar.selectbox("Planning round", round_options, index=round_options.index(default_round) if default_round in round_options else len(round_options) - 1)
    mode = st.sidebar.selectbox("Transfer mode", ["Auto", "PULL", "PUSH"])
    frequency = st.sidebar.selectbox("Transfer cycle (days)", [1, 2, 3, 5], index=1)
    plan = build_plan(data, target, mode.lower(), frequency)

    page = st.sidebar.radio("Navigate", [
        "Command center", "Final round plan", "Forecast + MRP", "Procurement", "Stock transfer",
        "Pricing", "Finance + valuation", "Round review", "Data center", "Game rules",
    ])
    st.sidebar.divider()
    st.sidebar.caption("Public app: no SAP connection. Verify current SAP data before entering decisions.")

    pages = {
        "Command center": lambda: command_page(plan),
        "Final round plan": lambda: final_page(plan),
        "Forecast + MRP": lambda: forecast_page(plan),
        "Procurement": lambda: procurement_page(plan),
        "Stock transfer": lambda: transfer_page(plan),
        "Pricing": lambda: pricing_page(plan),
        "Finance + valuation": lambda: finance_page(plan, data["valuations"]),
        "Round review": lambda: review_page(plan, data),
        "Data center": lambda: data_page(data),
        "Game rules": lambda: rules_page(data),
    }
    pages[page]()
    st.markdown('<div class="footer-note">ERPsim planning support · calculations are source-derived estimates; enter decisions in SAP yourself.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
