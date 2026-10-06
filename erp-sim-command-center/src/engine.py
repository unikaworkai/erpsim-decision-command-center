"""Deterministic ERPsim workbook reader and next-round planning rules."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
import math
import re

from openpyxl import load_workbook

from src import transfer_policy

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


def _explain_unknown(path):
    """Plain reason why an uploaded workbook was not used, plus which report it seems to be."""
    try:
        sheets = _detect_sheet_rows(path)
    except Exception as exc:  # unreadable or not really .xlsx
        return "unreadable", f"the file could not be opened as an Excel workbook ({type(exc).__name__})"
    headers = set()
    for _name, hdrs in sheets:
        headers |= {re.sub(r"[^a-z0-9]+", "_", str(h or "").strip().lower()).strip("_") for h in hdrs}
    looks_inventory = {"location", "material"} <= headers or {"storage_location", "material_number"} <= headers
    if looks_inventory and not ({"stock"} & headers or {"current_inventory"} & headers):
        return "inventory", "it looks like a ZMB52 inventory export but has no Stock column"
    shown = ", ".join(sorted(h for h in headers if h)[:8]) or "no column headers"
    return "unknown", f"its columns ({shown}) do not match any ERPsim report the app knows"


def _finance(rows):
    """Profit, revenue, cash from financial postings, plus cumulative profit at the end of each round."""
    total_profit = gross_profit = revenue = cash = 0.0; latest_round = latest_step = 0
    per_round = defaultdict(float)
    for r in rows:
        amt = _number(r.get("AMOUNT")); lvl = str(r.get("FS_LEVEL_1") or ""); acc = str(r.get("GL_ACCOUNT_NAME") or "")
        rnd = _round(r.get("SIM_ROUND")) or 0
        if lvl == "Income Statement":
            total_profit -= amt; per_round[rnd] -= amt
        if lvl == "Income Statement" and str(r.get("FS_LEVEL_2")) == "Revenues": revenue -= amt
        if lvl == "Income Statement" and str(r.get("FS_LEVEL_2")) in {"Revenues", "Cost of Goods Sold"}: gross_profit -= amt
        if acc == "Bank Cash Account": cash += amt
        latest_round = max(latest_round, rnd); latest_step = max(latest_step, _round(r.get("SIM_STEP")) or 0)
    cumulative, running = {}, 0.0
    for rnd in sorted(per_round):
        running += per_round[rnd]; cumulative[rnd] = running
    return {"profit": total_profit, "gross_profit": gross_profit, "revenue": revenue, "cash": cash,
            "through_round": latest_round, "through_day": latest_step, "profit_by_round": cumulative}


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
            if typ in ("detailed_sales", "summary_sales"):
                continue  # sales uploads are ADDED to the packaged sales below, never swapped in
            if typ != "unknown":
                paths[typ] = path

    rejected = []
    for path, typ in uploaded:
        if typ == "unknown":
            kind, reason = _explain_unknown(path)
            rejected.append({"file": path.name, "looks_like": kind, "reason": reason})

    data = {
        "rejected_uploads": rejected, "upload_report": [],
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
            data["financial"] = _finance(_rows(base, "Financial_Postings"))
            data["has_financial"] = True
        if "Current_Game_Rules" in sheet_names:
            for r in _rows(base, "Current_Game_Rules"):
                data["rules"][str(r.get("ELEMENT"))] = {"detail": r.get("DETAIL"), "value": r.get("VALUE")}
        data["has_sales"] = bool(data["sales"])
        data["has_inventory"] = bool(data["inventory"])
        data["has_po"] = bool(data["inbound"])

    # Specific reports supplied beside the all-round source extend/refresh it.
    def _sales_key(rec):
        return (rec["round"], rec["day"], rec["product"], rec["region"], round(rec["quantity"], 4), round(rec["revenue"], 2))

    def _merge_detailed(path):
        """Add rows not already in the data. A multiset is used, so two identical order lines
        (a real thing in SAP) are both kept, but a file uploaded twice is not double counted."""
        have = Counter(_sales_key(x) for x in data["sales"])
        added = skipped = 0; rounds = set()
        for r in _rows(path):
            code = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); rnd = _round(r.get("Round") or r.get("SIM_ROUND")); day = _round(r.get("Day") or r.get("SIM_STEP"))
            if not (code and rnd and day):
                continue
            region = _region(r.get("Area") or r.get("Location") or r.get("STORAGE_LOCATION"))
            rec = {"round": rnd, "day": day, "product": code, "region": region,
                   "quantity": _number(r.get("Quantity") or r.get("QUANTITY")),
                   "revenue": _number(r.get("Net Value") or r.get("NET_VALUE")),
                   "cost": _number(r.get("Cost") or r.get("COST")),
                   "price": _number(r.get("Net Price") or r.get("NET_PRICE"))}
            rounds.add(rnd); key = _sales_key(rec)
            if have[key] > 0:
                have[key] -= 1; skipped += 1
            else:
                data["sales"].append(rec); added += 1
        return added, skipped, rounds

    def _merge_summary(path):
        """Summary sales only fill round/day/product keys that have no detailed rows at all."""
        existing_keys = {(x["round"], x["day"], x["product"]) for x in data["sales"]}
        summary = defaultdict(float); rounds = set()
        for r in _rows(path):
            code = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); rnd = _round(r.get("Round") or r.get("SIM_ROUND")); day = _round(r.get("Day") or r.get("SIM_STEP"))
            if code and rnd and day:
                summary[(rnd, day, code)] += _number(r.get("Quantity") or r.get("QUANTITY")); rounds.add(rnd)
        added = 0
        for (rnd, day, code), qty in summary.items():
            if (rnd, day, code) not in existing_keys:
                data["sales"].append({"round": rnd, "day": day, "product": code, "region": None,
                                      "quantity": qty, "revenue": 0, "cost": 0, "price": 0}); added += 1
        return added, len(summary) - added, rounds

    def _report(path, label, added, skipped, rounds):
        span = ("no rounds found" if not rounds else f"Round {min(rounds)}" if min(rounds) == max(rounds)
                else f"Rounds {min(rounds)} to {max(rounds)}")
        if added:
            detail = f"{span}. Added {added} new row(s); {skipped} were already in the data."
        else:
            detail = f"{span}. Nothing new: all {skipped} row(s) were already in the data, so results do not change."
        data["upload_report"].append({"file": Path(path).name, "used_as": label, "detail": detail, "changed": bool(added)})

    # Packaged sales first, then every uploaded sales file on top.
    for sp in [p for p in (paths.get("detailed_sales") or paths.get("sales_round8"),) if p]:
        _merge_detailed(sp)
    for up, typ in uploaded:
        if typ == "detailed_sales":
            _report(up, "Detailed sales (ZVA05)", *_merge_detailed(up))
    if paths.get("summary_sales"):
        _merge_summary(paths["summary_sales"])
    for up, typ in uploaded:
        if typ == "summary_sales":
            _report(up, "Summary sales (ZVC2)", *_merge_summary(up))
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
        data["financial"] = _finance(_rows(paths["financial"]))
        data["has_financial"]=True
    if "inventory" in paths and paths["inventory"] != base:
        data["inventory"] = {}; bad_cells = 0
        for r in _rows(paths["inventory"]):
            c = _code(r.get("Material") or r.get("MATERIAL_NUMBER")); loc = str(r.get("Location") or r.get("STORAGE_LOCATION") or "")
            raw = r.get("Stock") if r.get("Stock") is not None else r.get("STOCK")
            if c and raw not in (None, "") and _number(raw, None) is None:
                bad_cells += 1
            if c: data["inventory"][(c, loc)] = _number(raw)
        data["has_inventory"] = bool(data["inventory"])
        if bad_cells:
            # Do not turn unreadable stock into zero; that would invent a purchase need.
            data["rejected_uploads"].append({"file": Path(paths["inventory"]).name, "looks_like": "inventory",
                                             "reason": f"{bad_cells} Stock value(s) are not numbers"})
    if any(r["looks_like"] == "inventory" for r in data["rejected_uploads"]):
        # You tried to give new stock but it could not be read: withhold stock-based numbers
        # instead of quietly using the older packaged inventory.
        data["inventory"] = {}; data["has_inventory"] = False
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
    labels = {"inventory": "Inventory (ZMB52), replaces the packaged stock", "purchase_orders": "Purchase orders (ZME2N), replaces the packaged PO list",
              "financial": "Financial report, replaces the packaged postings", "valuation": "Company valuation",
              "all_rounds": "ERPsim OData workbook", "pricing": "Price list", "procurement_source": "Supplier prices (ZME13)"}
    for up, typ in uploaded:
        if typ in labels and not any(r["file"] == up.name for r in data["rejected_uploads"]):
            data["upload_report"].append({"file": up.name, "used_as": labels[typ], "detail": "Read and used.", "changed": True})
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
    data["files"] = _file_status(paths, uploaded, max(data["complete_rounds"], default=0), data["financial"].get("through_round",0),detailed_through)
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
    # Replay = planning a round that has already been played. Compare with ALL complete rounds in the data.
    # (Before: compared with rounds before the target only, so replay was never switched on and today's
    # stock was used to "plan" old rounds.)
    latest_complete = max(data.get("complete_rounds", []), default=0)
    replay = target_round <= latest_complete
    # Current inventory and open PO snapshots are undated, so omit them in historical replay.
    inventory_valid = data["has_inventory"] and not replay
    inbound_valid = data["has_po"] and not replay
    # KPIs follow the selected round: show SAP results at the end of the round before it.
    as_of_round = target_round - 1
    past_values = [v for v in data["valuations"] if v["round"] <= as_of_round]
    last_value = max(past_values, key=lambda v: (v["round"], v["day"])) if past_values else None
    # Transfer mode is resolved after all products are calculated (see policy comparison below).
    # Before this fix, "auto" became PULL/PUSH here and the mode was never used again.
    requested_mode = str(transfer_mode or "auto").upper()
    if requested_mode not in {"AUTO", "PUSH", "PULL"}: requested_mode = "AUTO"
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
        transfers = None; entries = None
        if reg_stock is not None and central is not None:
            # ZMB1B entries differ by mode (course definitions, guide slides 13-14):
            # PUSH = quantity sent every cycle, PULL = target level kept in each region.
            # The old code always used one formula (target minus regional stock) for every mode.
            # Entering that net number as a Pull target would subtract regional stock twice.
            entries = transfer_policy.zmb1b_entries(daily, frequency, shares, buffer)
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
                     "regional_shares": shares, "transfers": transfers, "zmb1b": entries,
                     "valuation_impact": "Directional only; official lookup table missing."})
    # Compare PUSH and PULL on the same demand path, then resolve the mode.
    policy = None
    if all(r["zmb1b"] is not None for r in rows) and rows:
        sim_products = [{
            "code": r["code"], "name": r["product"], "central": r["central"] or 0,
            "regional": r["regional_stock"], "inbound": r["inbound"] or 0, "new_po": r["mrp"] or 0,
            "daily_by_region": {reg: r["daily"] * r["regional_shares"][reg] for reg in REGIONS},
            "entries": r["zmb1b"], "price": r["price"], "unit_cost": r["cost_basis"],
        } for r in rows]
        policy = transfer_policy.compare(sim_products, frequency)
    if requested_mode == "AUTO":
        transfer_mode = (policy["recommended"] if policy and policy["recommended"] else "PULL")
        mode_source = ("Auto: recommended by the Push/Pull comparison" if policy and policy["recommended"]
                       else "Auto: no real difference found, Pull kept as default" if policy
                       else "Auto: comparison needs current inventory")
    else:
        transfer_mode = requested_mode; mode_source = "Chosen by you in the sidebar"
    for r in rows:
        r["transfers"] = r["zmb1b"][transfer_mode] if r["zmb1b"] else None
    # If any product's need is unknown (no usable inventory), the total is unknown too.
    # Summing None as 0 used to show "0 units", which looks like "buy nothing".
    if all(r["po_qty"] is not None for r in rows):
        total_po = sum(r["po_value"] for r in rows); total_qty = sum(r["po_qty"] for r in rows)
    else:
        total_po = None; total_qty = None
    expected_revenue = sum(r["expected_revenue"] or 0 for r in rows) if all(r["expected_revenue"] is not None for r in rows) else None
    expected_gross_profit = sum(r["expected_gross_profit"] or 0 for r in rows) if all(r["expected_gross_profit"] is not None for r in rows) else None
    expected_end_inventory = sum(r["expected_end_inventory"] or 0 for r in rows) if all(r["expected_end_inventory"] is not None for r in rows) else None
    current_value = last_value["value"] if last_value else None
    finance = dict(data["financial"])
    by_round = finance.get("profit_by_round") or {}
    known = [r for r in by_round if r <= as_of_round]
    if known:
        finance["profit"] = by_round[max(known)]; finance["through_round"] = max(known)
    elif by_round:
        finance["profit"] = None; finance["through_round"] = None
    central_units = sum(q for (c, loc), q in data["inventory"].items() if loc == "03") if inventory_valid else None
    projected_central = (central_units + sum(data["inbound"].values()) + total_qty) if central_units is not None and inbound_valid and total_qty is not None else None
    return {"target_round": target_round, "through_round": max(complete_rounds, default=0),
            "historical_rounds": complete_rounds, "replay": replay, "mode": transfer_mode,
            "requested_mode": requested_mode, "mode_source": mode_source, "policy": policy,
            "frequency": frequency, "protection_horizon": frequency+3,
            "rows": rows, "products": len(rows), "purchase_value": total_po, "purchase_qty": total_qty,
            "expected_revenue": expected_revenue, "expected_gross_profit": expected_gross_profit,
            "expected_margin": (expected_gross_profit/expected_revenue if expected_revenue else None),
            "expected_end_inventory": expected_end_inventory,
            "fixed_po_cost": None if total_qty is None else (1000 if total_qty else 0),
            "rejected_uploads": data.get("rejected_uploads", []),
            "warehouse_units": round(central_units) if central_units is not None else None,
            "warehouse_utilization": (central_units/4000) if central_units is not None else None,
            "projected_warehouse_units": round(projected_central) if projected_central is not None else None,
            "company_value": current_value, "valuation_asof": last_value,
            "financial": finance, "inventory_valid": inventory_valid, "inbound_valid": inbound_valid,
            "as_of_round": as_of_round, "latest_complete": latest_complete,
            "data_warning": ((f"Replay of Round {target_round}: the forecast uses only Rounds 1 to {target_round - 1}, and the KPIs show "
                              f"SAP results at the end of Round {target_round - 1}. Your stock and open POs are from after Round "
                              f"{latest_complete}, so MRP need, transfers and Push/Pull are not shown for a past round. "
                              f"Pick Round {latest_complete + 1} to plan the next real round, or open Round review.") if replay else
                             "Inventory export has no round stamp; verify it is current before relying on transfer and MRP quantities." +
                             (f" Financial postings are through round {data['financial'].get('through_round')} while the latest complete sales round is {latest_complete}; refresh the financial report." if (data['financial'].get('through_round') or 0) < latest_complete else "") +
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
