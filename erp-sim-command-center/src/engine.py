"""Deterministic ERPsim workbook reader and next-round planning rules."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
import math
import re

from openpyxl import load_workbook

PRODUCTS = [
    {"code": f"CC-T{i:02d}", "suffix": f"T{i:02d}", "name": n, "cost": c}
    for i, (n, c) in enumerate([
        ("Milk", 22.95), ("Cream", 72.07), ("Yoghurt", 25.85),
        ("Cheese", 82.68), ("Butter", 59.88), ("Ice Cream", 43.15)
    ], 1)
]
REGIONS = ["North", "South", "West"]
REGION_CODES = {"03N": "North", "NO": "North", "NORTH": "North",
                "03S": "South", "SO": "South", "SOUTH": "South",
                "03W": "West", "WE": "West", "WEST": "West"}

BASELINE_DIR = Path(__file__).resolve().parent.parent / "data" / "baseline"

_SOURCE_FILENAMES = {
    "all_rounds": "O data for all the rounds.xlsx",
    "valuation": "Company Valuation.xlsx",
    "po_round8": "purchase order round 8 ExportData.xlsx",
    "summary_sales": "Summary salesExportData.xlsx",
    "sales_round8": "SalesExportData.xlsx",
    "inventory": "ExportData (1).xlsx",
}

_LOCAL_SOURCE_DIR = Path("/Users/unikamaharjan/Downloads")


def default_files():
    """Use portable packaged data when deployed, then fall back to local source files."""
    paths = {}
    for key, filename in _SOURCE_FILENAMES.items():
        packaged = BASELINE_DIR / filename
        local = _LOCAL_SOURCE_DIR / filename
        if packaged.exists():
            paths[key] = packaged
        elif local.exists():
            paths[key] = local
    return paths


def _rows(path, sheet=None):
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    headers = [str(x).strip() if x is not None else "" for x in next(it, ())]
    out = []
    for row in it:
        if not any(x is not None for x in row):
            continue
        out.append({headers[i]: row[i] if i < len(row) else None for i in range(len(headers))})
    wb.close()
    return out


def _number(value, default=0.0):
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _round(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _code(product):
    raw = str(product or "").upper()
    m = re.search(r"T0?[1-6]", raw)
    return f"CC-{m.group(0)}" if m else None


def _region(value):
    return REGION_CODES.get(str(value or "").upper())


def _detect_sheet_rows(path):
    """Inspect sheets and classify common SAP export header patterns."""
    wb = load_workbook(path, data_only=True, read_only=True)
    found = []
    for ws in wb.worksheets:
        values = ws.iter_rows(values_only=True)
        headers = [str(x).strip().lower() if x is not None else "" for x in next(values, ())]
        found.append((ws.title, headers))
    wb.close()
    return found


def _file_report(path):
    for sheet, h in _detect_sheet_rows(path):
        hs = set(h)
        if {"round", "day", "material", "quantity"}.issubset(hs) and ("area" in hs or "location" in hs):
            return "detailed_sales"
        if {"order", "status", "quantity"}.issubset(hs) or {"purchasing_order", "status", "quantity"}.issubset(hs):
            return "purchase_orders"
        if {"location", "stock", "material"}.issubset(hs) or {"storage_location", "current_inventory", "material_number"}.issubset(hs):
            return "inventory"
        if "simulation round" in hs and "company valuation" in hs:
            return "valuation"
        if {"gl_account_number", "amount", "fs_level_1"}.issubset(hs):
            return "financial"
        if {"material_number", "price", "currency"}.issubset(hs) and ("sales_organization" in hs or "distribution_channel" in hs):
            return "pricing"
        if {"material_number", "price", "vendor_code", "currency"}.issubset(hs):
            return "procurement_source"
        if {"round", "day", "material", "quantity"}.issubset(hs):
            return "summary_sales"
        if sheet == "Current_Pricing_Conditions":
            return "pricing"
    return "unknown"


def load_data(upload_dir=None):
    """Read the provided baseline workbooks, then apply matching uploaded exports."""
    paths = default_files()
    if "po_round8" in paths: paths["purchase_orders"] = paths["po_round8"]
    if "sales_round8" in paths: paths["detailed_sales"] = paths["sales_round8"]
    uploaded = []
    if upload_dir and Path(upload_dir).exists():
        for path in sorted(Path(upload_dir).glob("*.xlsx"), key=lambda p:p.stat().st_mtime):
            typ = _file_report(path)
            uploaded.append((path, typ))
            if typ != "unknown":
                paths[typ] = path

    data = {
        "sales": [], "inventory": {}, "inbound": defaultdict(float), "prices": {},
        "valuations": [], "financial": {}, "regional_round_sales": defaultdict(float),
        "round_totals": defaultdict(lambda: defaultdict(float)), "round_days": defaultdict(set),
        "files": [], "rules": {}, "has_inventory": False, "has_sales": False,
        "has_po": False, "has_financial": False, "costs": {p["code"]:p["cost"] for p in PRODUCTS},
    }
    # Source workbook contains the historic transaction tables and current rule rows.
    base = paths.get("all_rounds")
    if base:
        sheet_names = set(_detect_sheet_rows(base)[i][0] for i in range(len(_detect_sheet_rows(base))))
        if "Sales" in sheet_names:
            for r in _rows(base, "Sales"):
                code = _code(r.get("MATERIAL_NUMBER"))
                rnd = _round(r.get("SIM_ROUND")); day = _round(r.get("SIM_STEP"))
                if code and rnd and day:
                    reg = _region(r.get("AREA") or r.get("STORAGE_LOCATION"))
                    record = {"round": rnd, "day": day, "product": code, "region": reg,
                              "quantity": _number(r.get("QUANTITY")),
                              "revenue": _number(r.get("NET_VALUE")), "cost": _number(r.get("COST")),
                              "price": _number(r.get("NET_PRICE"))}
                    data["sales"].append(record)
        if "Current_Inventory" in sheet_names:
            for r in _rows(base, "Current_Inventory"):
                c = _code(r.get("MATERIAL_NUMBER")); loc = str(r.get("STORAGE_LOCATION") or "")
                if c:
                    data["inventory"][(c, loc)] = _number(r.get("STOCK"))
        if "Purchase_Orders" in sheet_names:
            for r in _rows(base, "Purchase_Orders"):
                c = _code(r.get("MATERIAL_NUMBER")); status = str(r.get("STATUS") or "").lower()
                if c and status not in {"delivered", "received", "closed", "cancelled", "canceled"}:
                    data["inbound"][c] += _number(r.get("QUANTITY"))
        if "Current_Pricing_Conditions" in sheet_names:
            for r in _rows(base, "Current_Pricing_Conditions"):
                c = _code(r.get("MATERIAL_NUMBER"))
                if c: data["prices"][c] = _number(r.get("PRICE"))
        if "Financial_Postings" in sheet_names:
            finance_rows = _rows(base, "Financial_Postings")
            total_profit = 0.0; gross_profit = 0.0; revenue = 0.0; cash = 0.0
            latest_round = 0; latest_step = 0
            for r in finance_rows:
                amt = _number(r.get("AMOUNT")); lvl = str(r.get("FS_LEVEL_1") or ""); acc = str(r.get("GL_ACCOUNT_NAME") or "")
                total_profit -= amt if lvl == "Income Statement" else 0
                if lvl == "Income Statement" and str(r.get("FS_LEVEL_2")) == "Revenues": revenue -= amt
                if lvl == "Income Statement" and str(r.get("FS_LEVEL_2")) in {"Revenues", "Cost of Goods Sold"}: gross_profit -= amt
                if acc == "Bank Cash Account": cash += amt
                latest_round = max(latest_round, _round(r.get("SIM_ROUND")) or 0)
                latest_step = max(latest_step, _round(r.get("SIM_STEP")) or 0)
            data["financial"] = {"profit": total_profit, "gross_profit": gross_profit,
                                 "revenue": revenue, "cash": cash,
                                 "through_round": latest_round, "through_day": latest_step}
            data["has_financial"] = True
        if "Current_Game_Rules" in sheet_names:
            for r in _rows(base, "Current_Game_Rules"):
                data["rules"][str(r.get("ELEMENT"))] = {"detail": r.get("DETAIL"), "value": r.get("VALUE")}
        data["has_sales"] = bool(data["sales"])
        data["has_inventory"] = bool(data["inventory"])
        data["has_po"] = bool(data["inbound"])

    # Specific reports supplied beside the all-round source extend/refresh it.
    sales_path = paths.get("detailed_sales") or paths.get("sales_round8")
    if sales_path:
        existing = {(s["round"], s["day"], s["product"], s["region"], s["quantity"], s["revenue"]) for s in data["sales"]}
        for r in _rows(sales_path):
            code = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); rnd = _round(r.get("Round") or r.get("SIM_ROUND")); day = _round(r.get("Day") or r.get("SIM_STEP"))
            if code and rnd and day:
                region = _region(r.get("Area") or r.get("Location") or r.get("STORAGE_LOCATION"))
                rec = {"round": rnd, "day": day, "product": code, "region": region,
                       "quantity": _number(r.get("Quantity") or r.get("QUANTITY")),
                       "revenue": _number(r.get("Net Value") or r.get("NET_VALUE")),
                       "cost": _number(r.get("Cost") or r.get("COST")),
                       "price": _number(r.get("Net Price") or r.get("NET_PRICE"))}
                key = (rec["round"], rec["day"], rec["product"], rec["region"], rec["quantity"], rec["revenue"])
                if key not in existing: data["sales"].append(rec); existing.add(key)
    # Summary sales is a safe fallback for round/day/product keys not present in detailed sales.
    # This lets later summary-only exports extend the history without duplicating the provided detail.
    summary_path = paths.get("summary_sales")
    if summary_path:
        existing_keys = defaultdict(float)
        for s in data["sales"]: existing_keys[(s["round"],s["day"],s["product"])] += s["quantity"]
        summary = defaultdict(float)
        for r in _rows(summary_path):
            code = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); rnd = _round(r.get("Round") or r.get("SIM_ROUND")); day = _round(r.get("Day") or r.get("SIM_STEP"))
            if code and rnd and day: summary[(rnd,day,code)] += _number(r.get("Quantity") or r.get("QUANTITY"))
        for (rnd,day,code),qty in summary.items():
            if (rnd,day,code) not in existing_keys:
                data["sales"].append({"round":rnd,"day":day,"product":code,"region":None,"quantity":qty,"revenue":0,"cost":0,"price":0})
    if "pricing" in paths and paths["pricing"] != base:
        for r in _rows(paths["pricing"]):
            c=_code(r.get("Material") or r.get("MATERIAL_NUMBER"))
            if c and r.get("Price") is not None: data["prices"][c]=_number(r.get("Price"))
    if "procurement_source" in paths and paths["procurement_source"] != base:
        for r in _rows(paths["procurement_source"]):
            c=_code(r.get("Material") or r.get("MATERIAL_NUMBER"))
            if c and r.get("Price") is not None:
                data["costs"][c]=_number(r.get("Price"),data["costs"].get(c,0))
    if "financial" in paths and paths["financial"] != base:
        fr = _rows(paths["financial"])
        total_profit=gross_profit=revenue=cash=0.0; latest_round=latest_step=0
        for r in fr:
            amt=_number(r.get("AMOUNT")); lvl=str(r.get("FS_LEVEL_1") or ""); acc=str(r.get("GL_ACCOUNT_NAME") or "")
            if lvl=="Income Statement": total_profit-=amt
            if lvl=="Income Statement" and str(r.get("FS_LEVEL_2"))=="Revenues": revenue-=amt
            if lvl=="Income Statement" and str(r.get("FS_LEVEL_2")) in {"Revenues","Cost of Goods Sold"}: gross_profit-=amt
            if acc=="Bank Cash Account": cash+=amt
            latest_round=max(latest_round,_round(r.get("SIM_ROUND")) or 0); latest_step=max(latest_step,_round(r.get("SIM_STEP")) or 0)
        data["financial"]={"profit":total_profit,"gross_profit":gross_profit,"revenue":revenue,"cash":cash,"through_round":latest_round,"through_day":latest_step}
        data["has_financial"]=True
    if "inventory" in paths and paths["inventory"] != base:
        data["inventory"] = {}
        for r in _rows(paths["inventory"]):
            c = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); loc = str(r.get("Location") or r.get("STORAGE_LOCATION") or "")
            if c: data["inventory"][(c, loc)] = _number(r.get("Stock") or r.get("STOCK"))
        data["has_inventory"] = bool(data["inventory"])
    if "purchase_orders" in paths and paths["purchase_orders"] != base:
        # Current transaction export can supplement the historic schedule, keyed to avoid double counting.
        prior = {(c, round(q, 4)) for c, q in data["inbound"].items()}
        data["inbound"] = defaultdict(float)
        for r in _rows(paths["purchase_orders"]):
            c = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); status = str(r.get("Status") or r.get("STATUS") or "").lower()
            qty = _number(r.get("Quantity") or r.get("QUANTITY"))
            if c and status not in {"delivered", "received", "closed", "cancelled", "canceled"}:
                data["inbound"][c] += qty
        data["has_po"] = True
    if "valuation" in paths:
        for r in _rows(paths["valuation"]):
            rnd = _round(r.get("Simulation Round")); day = _round(r.get("Simulation Step"))
            if rnd and day is not None:
                val = _number(r.get("Company Valuation"))
                data["valuations"].append({"round": rnd, "day": day, "value": val})
    # Prefer each actual sale price as price context when a current list is absent.
    data["price_history"] = defaultdict(list)
    for s in data["sales"]:
        if s["price"] > 0: data["price_history"][s["product"]].append((s["round"], s["price"]))
    # Rebuild aggregate lookup after all rows have been combined.
    data["round_totals"] = defaultdict(lambda: defaultdict(float)); data["round_days"] = defaultdict(set)
    data["regional_round_sales"] = defaultdict(float)
    for s in data["sales"]:
        data["round_totals"][s["round"]][s["product"]] += s["quantity"]
        data["round_days"][s["round"]].add(s["day"])
        if s["region"]: data["regional_round_sales"][(s["round"], s["product"], s["region"])] += s["quantity"]
    data["rounds"] = sorted(data["round_totals"])
    data["max_round"] = max(data["rounds"], default=0)
    data["complete_rounds"] = [r for r in data["rounds"] if max(data["round_days"].get(r,{0})) >= 10]
    data["incomplete_rounds"] = [r for r in data["rounds"] if r not in data["complete_rounds"]]
    detailed_through = max((s["round"] for s in data["sales"] if s["region"]),default=0)
    data["files"] = _file_status(paths, uploaded, data["max_round"], data["financial"].get("through_round",0),detailed_through)
    return data


def _file_status(paths, uploaded, current_round=0, financial_round=0, detailed_round=0):
    labels = [("Sales summary", "summary_sales"), ("Detailed sales", "detailed_sales"),
              ("Inventory", "inventory"), ("Purchase orders", "purchase_orders"),
              ("Procurement source", "all_rounds"), ("Financial", "all_rounds")]
    report = []
    for label, key in labels:
        p = paths.get(key)
        if key == "all_rounds" and p:
            ok = True
        else: ok = bool(p)
        status = "Uploaded" if ok else "Missing"
        if label == "Financial" and ok and financial_round and current_round and financial_round < current_round:
            status = "Outdated"
        if label == "Detailed sales" and ok and detailed_round and current_round and detailed_round < current_round:
            status = "Outdated"
        report.append({"name": label, "status": status,
                       "source": p.name if p else "Upload report", "round": financial_round if label=="Financial" and ok else None})
    return report


def build_plan(data, target_round, transfer_mode="auto", frequency=None):
    target_round = max(1, int(target_round)); hist_rounds = [r for r in data["rounds"] if r < target_round]
    complete_rounds = [r for r in hist_rounds if max(data["round_days"].get(r, {0})) >= 10]
    recent = complete_rounds[-3:]
    round_count = len(complete_rounds)
    replay = target_round <= max(complete_rounds,default=0)
    # Current inventory and open PO snapshots are undated, so omit them in historical replay.
    inventory_valid = data["has_inventory"] and not replay
    inbound_valid = data["has_po"] and not replay
    last_value = data["valuations"][-1] if data["valuations"] else None
    if transfer_mode == "auto": transfer_mode = "PULL" if round_count >= 2 else "PUSH"
    if frequency is None: frequency = 2 if round_count >= 3 else 3
    frequency = max(1, int(frequency))
    rows = []
    for p in PRODUCTS:
        code = p["code"]
        vals = [data["round_totals"][r].get(code, 0.0) for r in recent]
        if vals:
            weights = [0.2, 0.3, 0.5][-len(vals):]
            weights = [w / sum(weights) for w in weights]
            forecast = sum(v*w for v, w in zip(vals, weights))
            prev = vals[-1]
            daily_vals = [v/max(1, len(data["round_days"].get(r, set()))) for v, r in zip(vals, recent)]
            daily = forecast / 10
            variability = pstdev(daily_vals) if len(daily_vals) > 1 else max(1, daily * .25)
            protection_horizon = frequency + 3
            buffer = math.ceil(variability * math.sqrt(protection_horizon))
            backtest_error = None
            if len(vals) >= 2 and vals[-1] > 0:
                prior=vals[:-1][-3:]; bw=[0.2,0.3,0.5][-len(prior):]; bw=[x/sum(bw) for x in bw]
                backtest_error=abs(sum(v*w for v,w in zip(prior,bw))-vals[-1])/vals[-1]
            if round_count >= 2 and backtest_error is not None and backtest_error <= .3:
                conf = "Medium"
            else: conf = "Low"
            reason = f"Weighted from {len(vals)} completed rounds; newest round has the greatest weight."
        else:
            forecast = 0; prev = 0; daily = 0; buffer = 0; conf = "Low"
            reason = "No completed sales history before this round; exploration forecast is unavailable."
        md61 = round(forecast) + buffer
        onhand = sum(q for (c, _loc), q in data["inventory"].items() if c == code) if inventory_valid else None
        central = data["inventory"].get((code, "03"), 0) if inventory_valid else None
        reg_stock = {reg: data["inventory"].get((code, loc), 0) for reg, loc in [("North", "03N"), ("South", "03S"), ("West", "03W")]} if inventory_valid else None
        inbound = data["inbound"].get(code, 0) if inbound_valid else None
        mrp = max(0, round(md61 - onhand - inbound)) if onhand is not None and inbound is not None else None
        price = data["prices"].get(code)
        cost = data["costs"].get(code,p["cost"])
        cogs_rows = [s for s in data["sales"] if s["product"]==code and s["round"] in recent and s["cost"]>0 and s["quantity"]>0]
        cogs_total = sum(s["cost"] for s in cogs_rows); cogs_qty = sum(s["quantity"] for s in cogs_rows)
        cost_basis = cogs_total/cogs_qty if cogs_qty else cost
        cost_basis_type = "Recent transactional COGS" if cogs_qty else "Supplier reference cost"
        margin = (price-cost_basis)/price if price and price > 0 else None
        regional_totals = {reg: sum(data["regional_round_sales"].get((r, code, reg), 0) for r in recent) for reg in REGIONS}
        reg_sum = sum(regional_totals.values())
        shares = {reg: (regional_totals[reg]/reg_sum if reg_sum else 1/3) for reg in REGIONS}
        transfers = None
        if reg_stock is not None and central is not None:
            needs = {reg: max(0, math.ceil(daily * frequency * shares[reg] + buffer*shares[reg] - reg_stock[reg])) for reg in REGIONS}
            # The transfer decision follows ME59N in the workflow. Quantities may therefore use
            # the planned receipt, but remain conditional on that PO arriving as expected.
            available = max(0, central + (inbound or 0) + (mrp or 0))
            transfers = {}
            for reg in REGIONS:
                qty = min(needs[reg], available); transfers[reg] = qty; available -= qty
        if price is not None:
            rec_price = price
            pricing_reason = "Hold the observed one-price-per-product list; supplied history does not establish a reliable price response."
            price_conf = "Low"
        else:
            rec_price = None; pricing_reason = "Upload the current price list before entering VK32 prices."; price_conf = "Low"
        if onhand is None:
            risk = "Pending inventory"
        elif daily and onhand < daily * (1.5 + frequency):
            risk = "High"
        elif daily and onhand < daily * (frequency + 3):
            risk = "Watch"
        else:
            risk = "Low"
        projected_end = max(0, round(onhand + inbound + mrp - round(forecast))) if onhand is not None and inbound is not None else None
        expected_revenue = round(forecast * price, 2) if price is not None else None
        expected_profit = round(forecast * (price - cost_basis), 2) if price is not None else None
        rows.append({"code": code, "product": p["name"], "forecast": round(forecast), "previous_sales": round(prev),
                     "daily": round(daily, 1), "buffer": buffer, "md61": md61, "confidence": conf,
                     "backtest_error": backtest_error if vals else None,
                     "reason": reason, "inventory": round(onhand) if onhand is not None else None,
                     "central": round(central) if central is not None else None,
                     "regional_stock": {k: round(v) for k,v in reg_stock.items()} if reg_stock is not None else None,
                     "inbound": round(inbound) if inbound is not None else None, "mrp": mrp,
                     "po_qty": mrp, "po_value": (mrp*cost if mrp is not None else None),
                     "cost": cost, "price": price, "recommended_price": rec_price, "margin": margin,
                     "cost_basis": cost_basis, "cost_basis_type": cost_basis_type,
                     "price_reason": pricing_reason, "price_confidence": price_conf,
                     "expected_revenue": expected_revenue, "expected_gross_profit": expected_profit,
                     "expected_end_inventory": projected_end, "risk": risk,
                     "regional_shares": shares, "transfers": transfers,
                     "valuation_impact": "Directional only; official lookup table missing."})
    total_po = sum(r["po_value"] or 0 for r in rows)
    total_qty = sum(r["po_qty"] or 0 for r in rows)
    expected_revenue = sum(r["expected_revenue"] or 0 for r in rows) if all(r["expected_revenue"] is not None for r in rows) else None
    expected_gross_profit = sum(r["expected_gross_profit"] or 0 for r in rows) if all(r["expected_gross_profit"] is not None for r in rows) else None
    expected_end_inventory = sum(r["expected_end_inventory"] or 0 for r in rows) if all(r["expected_end_inventory"] is not None for r in rows) else None
    current_value = last_value["value"] if last_value else None
    finance = data["financial"]
    central_units = sum(q for (c, loc), q in data["inventory"].items() if loc == "03") if inventory_valid else None
    projected_central = (central_units + sum(data["inbound"].values()) + total_qty) if central_units is not None and inbound_valid else None
    return {"target_round": target_round, "through_round": max(complete_rounds, default=0),
            "historical_rounds": complete_rounds, "replay": replay, "mode": transfer_mode,
            "frequency": frequency, "protection_horizon": frequency+3,
            "rows": rows, "products": len(rows), "purchase_value": total_po, "purchase_qty": total_qty,
            "expected_revenue": expected_revenue, "expected_gross_profit": expected_gross_profit,
            "expected_margin": (expected_gross_profit/expected_revenue if expected_revenue else None),
            "expected_end_inventory": expected_end_inventory,
            "fixed_po_cost": 1000 if total_qty else 0,
            "warehouse_units": round(central_units) if central_units is not None else None,
            "warehouse_utilization": (central_units/4000) if central_units is not None else None,
            "projected_warehouse_units": round(projected_central) if projected_central is not None else None,
            "company_value": current_value, "valuation_asof": last_value,
            "financial": finance, "inventory_valid": inventory_valid, "inbound_valid": inbound_valid,
            "data_warning": ("Historical replay excludes undated current inventory and purchase orders to prevent future-data leakage." if replay else
                             "Inventory export has no round stamp; verify it is current before relying on transfer and MRP quantities." +
                             (f" Financial postings are through round {finance.get('through_round')} while the latest complete sales round is {max(data.get('complete_rounds',[]),default=0)}; refresh the financial report." if finance.get('through_round',0) < max(data.get('complete_rounds',[]),default=0) else "") +
                             (f" Round {data['incomplete_rounds'][-1]} is incomplete and excluded from the forecast." if data.get('incomplete_rounds') else "")),
            "valuation_direction": "Not calculated: official valuation credit-rating and risk-rate lookup is not in the supplied files."}


def state_json(upload_dir, target_round=None, transfer_mode="auto", frequency=None):
    data = load_data(upload_dir)
    target = int(target_round or max(data["complete_rounds"],default=0)+1)
    plan = build_plan(data, target, transfer_mode, frequency)
    return {"plan": plan, "files": data["files"], "rounds": data["rounds"], "max_round": data["max_round"],
            "complete_rounds": data["complete_rounds"], "incomplete_rounds": data["incomplete_rounds"],
            "sales_available": data["has_sales"], "rules": data["rules"], "known_costs": PRODUCTS,
            "valuations": data["valuations"],
            "round_totals": {str(r): dict(values) for r, values in data["round_totals"].items()}}
