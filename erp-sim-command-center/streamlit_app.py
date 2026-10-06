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
          /* Page, sidebar and widget colours come from .streamlit/config.toml (repo root).
             Rules below only style our own boxes, and always set text AND background
             together so they stay readable whatever theme Streamlit picks. */
          [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 { color: #0b4f99; }
          .eyebrow { color: #4a5b73; font-size: .77rem; font-weight: 700; letter-spacing: .11em; }
          /* Streamlit draws captions at 60% opacity, which drops grey text below 4.5:1. */
          [data-testid="stMain"] [data-testid="stCaptionContainer"] { color: #4a5b73; opacity: 1; }
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #c9d6e8; opacity: 1; }
          .caption-box { background: #e8f1fb; color: #172b4d; border-left: 4px solid #0b63c4; border-radius: 6px; padding: .8rem 1rem; margin: .5rem 0 1.1rem; }
          .warning-box { background: #fff5db; color: #172b4d; border-left: 4px solid #b37e00; border-radius: 6px; padding: .8rem 1rem; margin: .5rem 0 1.1rem; }
          .decision-box { background: #ffffff; color: #172b4d; border: 1px solid #c9d6e8; border-left: 5px solid #0b63c4; border-radius: 8px; padding: .9rem 1.1rem; margin: .4rem 0 1rem; }
          .decision-box b.tag { background: #0b4f99; color: #ffffff; border-radius: 4px; padding: 1px 8px; font-size: .8rem; letter-spacing: .04em; }
          .footer-note { color: #4a5b73; font-size: .86rem; margin: 1.5rem 0 .5rem; }
          div[data-testid="stMetric"] { background: #ffffff; border: 1px solid #c9d6e8; border-radius: 8px; padding: .6rem .8rem; }
          div[data-testid="stMetric"] [data-testid="stMetricLabel"],
          div[data-testid="stMetric"] [data-testid="stMetricLabel"] p { color: #4a5b73; }
          div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #172b4d; }
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
                "ZMB1B entry type": ENTRY_LABEL[plan["mode"]],
                "ZMB1B North": (row["transfers"] or {}).get("North"),
                "ZMB1B South": (row["transfers"] or {}).get("South"),
                "ZMB1B West": (row["transfers"] or {}).get("West"),
                "Confidence": row["confidence"],
            }
        )
    return pd.DataFrame(records).to_csv(index=False).encode("utf-8")


def cash_need(plan: dict) -> float | None:
    if plan["purchase_value"] is None or plan["fixed_po_cost"] is None:
        return None
    return plan["purchase_value"] + plan["fixed_po_cost"]


def show_rejected(plan: dict) -> None:
    """Every uploaded file that was NOT used gets a visible reason."""
    for item in plan.get("rejected_uploads", []):
        extra = (" Stock-based numbers (MRP need, transfers, Push/Pull) are withheld until a readable "
                 "inventory report is uploaded, so the app does not reuse old stock by mistake."
                 if item["looks_like"] == "inventory" else
                 " The app is still using the packaged data for every report.")
        st.error(f"**Not used: {item['file']}**. Reason: {item['reason']}.{extra}")


def kpi(col, label: str, value: str, note: str | None = None) -> None:
    """KPI card with an optional plain note underneath.

    Notes used to sit in st.metric's delta slot, which drew a green up arrow
    ("went up, good") next to things like a purchase cost. A caption is neutral.
    """
    with col:
        st.metric(label, value)
        if note:
            st.caption(note)


def title(kicker: str, heading: str, text: str) -> None:
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.title(heading)
    st.caption(text)


def warning(text: str) -> None:
    st.markdown(f'<div class="warning-box"><b>Data check</b><br>{text}</div>', unsafe_allow_html=True)


ENTRY_LABEL = {"PUSH": "quantity to SEND every cycle", "PULL": "TARGET stock to keep"}


def inputs_line(plan: dict, data: dict) -> None:
    """Show exactly which inputs produced the results, so nothing on screen is stale."""
    mode_text = (f"transfer mode {plan['mode']} ({plan['mode_source']})" if plan.get("policy")
                 else "transfer mode not calculated (needs inventory)")
    st.caption(f"Calculated just now for: Round {plan['target_round']} · {mode_text} · {plan['frequency']}-day cycle. "
               "Changing any sidebar control recalculates everything on this page.")


def zmb1b_table(plan: dict, mode: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"Product": r["product"], **{reg: (r["zmb1b"] or {}).get(mode, {}).get(reg) for reg in REGIONS},
         "What you type in ZMB1B": ENTRY_LABEL[mode] if r["zmb1b"] else "Needs current inventory"}
        for r in plan["rows"]
    ])


def comparison_table(policy: dict) -> pd.DataFrame:
    rows = []
    for label, pair in policy["scenarios"].items():
        for mode in ("PUSH", "PULL"):
            res = pair[mode]
            rows.append({"Scenario": label, "Mode": mode.title(),
                         "Lost sales (units)": round(res["lost"]),
                         "Units shipped to regions": round(sum(x["shipped"] for x in res["products"])),
                         "Transfer fees (€)": round(res["fees"]),
                         "Extra storage fees (€)": round(res["storage_cost"]),
                         "Regional stock at round end": round(res["end_regional"]),
                         "Gross profit after fees (€)": None if res["profit_after_logistics"] is None else round(res["profit_after_logistics"])})
    return pd.DataFrame(rows)


def transfer_decision(plan: dict, show_trace: bool = True) -> None:
    policy = plan.get("policy")
    if policy is None:
        st.info("Push vs Pull needs a current inventory report (ZMB52). Upload it in the sidebar. "
                "No transfer quantities are shown without it, so nothing here can mislead you.")
        return
    tag = "RECOMMENDED" if policy["recommended"] else "NO CLEAR WINNER"
    body = (f'<div class="decision-box"><b class="tag">{tag}</b> <b>{policy["headline"]}</b>'
            f'<br>1. {policy["reasons"][0]}<br>2. {policy["reasons"][1]}'
            f'<br><b>Main risk:</b> {policy["risk"]}'
            f'<br><b>What would change this:</b> {policy["change"]}')
    if policy["why_equal"]:
        body += f'<br><b>Why the modes match:</b> {policy["why_equal"]}'
    st.markdown(body + "</div>", unsafe_allow_html=True)
    shown = plan["mode"]
    st.markdown(f"**ZMB1B entries for {shown.title()}** ({ENTRY_LABEL[shown]}, every {plan['frequency']} days). "
                f"Showing {shown.title()} because: {plan['mode_source'][0].lower() + plan['mode_source'][1:]}.")
    st.dataframe(zmb1b_table(plan, shown), hide_index=True, width="stretch")
    st.caption("Timing: transfers run on day 1 and then every cycle. A transfer reaches the region the next morning. "
               "These are recommendations for you to enter in SAP; the app does not run ZMB1B.")
    with st.expander("Why this result? (formulas, comparison and day-by-day trace)"):
        st.markdown(
            "**What Push and Pull mean in the course** (guide slides 13 and 14): Push sends a fixed quantity "
            "to each region every cycle. Pull keeps a target level in each region; each cycle SAP ships target "
            "minus the stock already there. Neither mode changes MD61, MD01 or ME59N, so the purchase plan above "
            "is the same in both modes.")
        st.markdown(
            "**Formulas per product and region:** cycle demand = daily forecast × cycle days × region share. "
            "Push quantity = cycle demand, rounded up. Pull target = cycle demand + region share of the safety buffer, rounded up.")
        st.markdown("**Both modes are simulated over the 10-day round on the same demand path:**")
        st.dataframe(comparison_table(policy), hide_index=True, width="stretch")
        st.caption("Gross profit after fees = units sold × (current price minus recent unit cost) minus transfer fees "
                   "minus extra storage fees. It is not company valuation. Purchase cost and the €1,000 PO fee are the "
                   "same in both modes, so they are left out of the comparison.")
        st.markdown("**Assumptions used in the simulation**")
        st.code(policy["assumptions"], language=None)
        st.markdown(f"Stock check (start + received minus sold = end, every product, every scenario): "
                    f"**{'passed' if policy['conservation_ok'] else 'FAILED'}**")
        if show_trace:
            names = [r["product"] for r in plan["rows"]]
            pick = st.selectbox("Day-by-day trace for", names, key=f"trace_{show_trace}")
            mode_pick = st.radio("Mode", ["PUSH", "PULL"], horizontal=True, key=f"trace_mode_{show_trace}")
            res = policy["scenarios"]["Expected demand"][mode_pick]
            prod = next(x for x in res["products"] if x["product"] == pick)
            st.dataframe(pd.DataFrame(prod["trace"]), hide_index=True, width="stretch")


def command_page(plan: dict, data: dict) -> None:
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
    asof = plan.get("valuation_asof")
    kpi(cols[0], "Company valuation", eur(plan["company_value"]) if asof else "Not yet",
        f"SAP value at end of Round {asof['round']}" if asof else "No round finished before this one")
    prof_round = financial.get("through_round")
    prof_note = (f"SAP postings through Round {prof_round}" +
                 (" (latest report available)" if prof_round and prof_round < plan["as_of_round"] else "")) if prof_round else "No postings before this round"
    kpi(cols[1], "Cumulative profit", eur(financial.get("profit")) if prof_round else "Not yet", prof_note)
    if plan["purchase_qty"] is None:
        kpi(cols[2], "Expected PO need", "Pending", "Needs a readable inventory report (ZMB52)")
    else:
        kpi(cols[2], "Expected PO need", f"{num(plan['purchase_qty'])} units", f"{eur(plan['purchase_value'])} at supplier cost, before the PO fee")
    kpi(cols[3], "Expected gross profit", eur(plan["expected_gross_profit"]), f"{percent(plan['expected_margin'])} margin, only if every forecast unit is in stock")
    if plan["inventory_valid"]:
        kpi(cols[4], "Products to watch", f"{risk_count} / 6", "High or Watch on the stock lead-time screen")
    else:
        kpi(cols[4], "Products to watch", "Pending", "Stock risk needs a readable inventory report")
    inputs_line(plan, data)
    st.caption("What changes these cards: **Planning round** changes all of them. Valuation and profit are SAP "
               "results, so Push/Pull and cycle days do not change them. Push/Pull changes only the Transfer plan below.")
    st.subheader("Purchase plan (MD61, MD01, ME59N)")
    st.caption("Quantities to BUY from the supplier. Transfer mode does not change these numbers: "
               "Push and Pull only decide how bought stock moves to the regions (ZMB1B, below).")
    st.dataframe(planner_table(plan["rows"]), hide_index=True, width="stretch")
    st.subheader("Transfer plan (ZMB1B): Push or Pull?")
    transfer_decision(plan, show_trace="cc")
    left, right = st.columns((2, 1))
    with left:
        st.subheader("Priority actions")
        for row in sorted(plan["rows"], key=lambda item: (item["mrp"] is None, -(item["mrp"] or 0)))[:3]:
            action = "Upload current inventory and PO status" if row["mrp"] is None else f"Review expected MRP requirement: {num(row['mrp'])} units"
            st.write(f"**{row['product']}**: {action}")
        st.write("**Pricing**: retain one price per product until price-response evidence supports a change.")
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
    cols[0].metric("Merchandise estimate", eur(plan["purchase_value"]) if plan["purchase_value"] is not None else "Pending")
    kpi(cols[1], "PO / transport cost", eur(plan["fixed_po_cost"]) if plan["fixed_po_cost"] is not None else "Pending", "€1,000 per purchase order (game rule)")
    cols[2].metric("Estimated cash need", eur(cash_need(plan)) if cash_need(plan) is not None else "Pending")
    st.caption("The source identifies a €1,000 PO cost. Verify current SAP cash, credit, and delivery timing before ME59N.")


def transfer_page(plan: dict, data: dict) -> None:
    title("SAP WORKFLOW · 04", "Stock transfer", "Choose Push or Pull for ZMB1B. Verify actual stock in SAP before saving.")
    inputs_line(plan, data)
    transfer_decision(plan, show_trace="tp")
    if plan.get("policy"):
        st.subheader("Both modes side by side (ZMB1B entries)")
        left, right = st.columns(2)
        with left:
            st.markdown("**Push:** quantity to send every cycle")
            st.dataframe(zmb1b_table(plan, "PUSH").drop(columns=["What you type in ZMB1B"]), hide_index=True, width="stretch")
        with right:
            st.markdown("**Pull:** target stock to keep")
            st.dataframe(zmb1b_table(plan, "PULL").drop(columns=["What you type in ZMB1B"]), hide_index=True, width="stretch")
        stock = pd.DataFrame([{"Product": r["product"], "Main warehouse (03)": r["central"],
                               **{f"{reg} now": (r["regional_stock"] or {}).get(reg) for reg in REGIONS}} for r in plan["rows"]])
        st.markdown("**Stock in the inventory export (ZMB52)**")
        st.dataframe(stock, hide_index=True, width="stretch")
    regional = pd.DataFrame(
        [{"Product": r["product"], **{f"{region} share": r["regional_shares"][region] * 100 for region in REGIONS}} for r in plan["rows"]]
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
             "Gross margin": None if r["margin"] is None else r["margin"] * 100, "Suggested price": r["recommended_price"],
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
            f"ZMB1B North ({plan['mode'].title()})": (row["transfers"] or {}).get("North"),
            f"ZMB1B South ({plan['mode'].title()})": (row["transfers"] or {}).get("South"),
            f"ZMB1B West ({plan['mode'].title()})": (row["transfers"] or {}).get("West"),
        })
    st.dataframe(pd.DataFrame(output), hide_index=True, width="stretch", column_config={
        "Unit cost": st.column_config.NumberColumn(format="€%.2f"),
        "PO value": st.column_config.NumberColumn(format="€%.2f"),
        "VK32 price": st.column_config.NumberColumn(format="€%.2f"),
    })
    st.caption(f"ZMB1B columns are {plan['mode'].title()} entries: {ENTRY_LABEL[plan['mode']]}, every {plan['frequency']} days.")
    st.download_button(
        "Download decision sheet (.csv)", make_csv(plan),
        file_name=f"ERPsim_Round_{plan['target_round']}_Decision_Sheet.csv", mime="text/csv",
        width="stretch",
    )
    cols = st.columns(4)
    cols[0].metric("Expected revenue", eur(plan["expected_revenue"]))
    cols[1].metric("Expected gross profit", eur(plan["expected_gross_profit"]))
    cols[2].metric("Expected ending stock", f"{num(plan['expected_end_inventory'])} units")
    cols[3].metric("Estimated cash need", eur(cash_need(plan)) if cash_need(plan) is not None else "Pending")


def review_page(plan: dict, data: dict) -> None:
    title("LEARN AFTER EACH ROUND", "Round review", "Compare the prepared forecast with actual sales after a round finishes.")
    actuals = data["round_totals"].get(plan["target_round"], {})
    rows = []
    for row in plan["rows"]:
        actual = actuals.get(row["code"])
        error = None if actual is None else (row["forecast"] - actual) / max(1, actual)
        rows.append({"Product": row["product"], "Forecast prepared": row["forecast"], "Actual sales": actual,
                     "Forecast error": None if error is None else error * 100, "Status": "Awaiting actual" if actual is None else "Compare and adjust"})
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

    for item in data.get("upload_report", []):
        msg = f"**{item['file']}**: used as {item['used_as']}. {item['detail']}"
        (st.sidebar.success if item["changed"] else st.sidebar.info)(msg)

    default_round = max(data["complete_rounds"], default=0) + 1
    # Rounds 2 .. next round: a past round opens as a replay; you cannot plan further ahead than the next round.
    round_options = list(range(2, default_round + 1)) or [1]
    target = st.sidebar.selectbox(
        "Planning round", round_options, index=len(round_options) - 1,
        help=f"Round {default_round} is the next real round. Earlier rounds open as a replay that uses only the data "
             "that existed at that time, so you can compare the forecast with what really sold (Round review).")
    mode = st.sidebar.selectbox("Transfer mode", ["Auto", "PULL", "PUSH"],
                                help="Auto shows the mode the Push/Pull comparison recommends. Push and Pull only change ZMB1B, not purchasing.")
    frequency = st.sidebar.selectbox("Transfer cycle (days)", [1, 2, 3, 5], index=1)
    plan = build_plan(data, target, mode.lower(), frequency)

    page = st.sidebar.radio("Navigate", [
        "Command center", "Final round plan", "Forecast + MRP", "Procurement", "Stock transfer",
        "Pricing", "Finance + valuation", "Round review", "Data center", "Game rules",
    ])
    st.sidebar.divider()
    st.sidebar.caption("Public app: no SAP connection. Verify current SAP data before entering decisions.")

    pages = {
        "Command center": lambda: command_page(plan, data),
        "Final round plan": lambda: final_page(plan),
        "Forecast + MRP": lambda: forecast_page(plan),
        "Procurement": lambda: procurement_page(plan),
        "Stock transfer": lambda: transfer_page(plan, data),
        "Pricing": lambda: pricing_page(plan),
        "Finance + valuation": lambda: finance_page(plan, data["valuations"]),
        "Round review": lambda: review_page(plan, data),
        "Data center": lambda: data_page(data),
        "Game rules": lambda: rules_page(data),
    }
    if plan.get("rejected_uploads"):
        st.sidebar.error(f"{len(plan['rejected_uploads'])} uploaded file(s) not used. See the message on the page.")
        show_rejected(plan)
    pages[page]()
    st.markdown('<div class="footer-note">ERPsim planning support · calculations are source-derived estimates; enter decisions in SAP yourself.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
