"""Push vs Pull stock-transfer policy (ZMB1B) for ERPsim Logistics Extended.

Course definitions (Logistics Extended guide, slides 13-14; Job Aid page 1):
  PUSH: you enter the QUANTITY of each product to SEND to each region.
        That same quantity is shipped every cycle (the "Scheduling" days).
  PULL: you enter the TARGET quantity to MAINTAIN in each region.
        Each cycle SAP ships (target - stock in that region).

Transfer mode only changes how stock moves from the main warehouse (03) to the
regions. It does not change MD61, MD01 or ME59N, so purchase quantities are
the same for both modes.

Everything here is deterministic. Both policies are run on the SAME demand
path, so any difference comes from the policy, not from different demand.

Simulation timing assumptions (shown in the app under "Why this result?"):
  * Transfers run on day 1, 1+cycle, 1+2*cycle, ... up to the last day.
  * A transfer sent on day d is in the region at the opening of day d+1
    (verified in game_rules.yaml from OData Inventory and Stock_Transfers).
  * The new PO is placed on day 1. Lead time is 1-2 days and goods received on
    day d are usable on day d+1. Base case: usable day 3 (12 of our 15 POs
    arrived after 1 day). Slow case (usable day 4) is run as a stress test.
  * PULL decides from the region's opening stock, before that day's sales.
  * If the main warehouse cannot cover all requests, it ships to each region
    in proportion to what was requested.
  * No stock, no sale: unmet demand is lost, not backordered (game rule 1).
  * EUR 100 is charged per destination that actually receives goods in a run.
"""
from __future__ import annotations

import math

REGIONS = ["North", "South", "West"]
TRANSFER_FEE = 100.0          # EUR per destination per transfer (game rule)
STORAGE_CAPACITY = 4000       # units, all locations together (game rule)
EXTRA_BLOCK = 1000            # units per extra block
EXTRA_BLOCK_COST = 300.0      # EUR per extra block per day (game rule)
TIE_EUR = 100.0               # differences smaller than one transfer fee are "no real difference"


def zmb1b_entries(daily: float, frequency: int, shares: dict, buffer: float) -> dict:
    """What to type into ZMB1B for each mode, per region.

    PUSH quantity = expected demand in one cycle (sent every cycle, so a buffer
    added here would pile up every cycle).
    PULL target  = expected demand in one cycle + the region's share of the buffer.
    """
    cycle = {r: daily * frequency * shares[r] for r in REGIONS}
    buf = {r: buffer * shares[r] for r in REGIONS}
    return {
        "PUSH": {r: math.ceil(round(cycle[r], 6)) for r in REGIONS},
        "PULL": {r: math.ceil(round(cycle[r] + buf[r], 6)) for r in REGIONS},
        "cycle_demand": {r: round(cycle[r], 1) for r in REGIONS},
        "buffer_share": {r: round(buf[r], 1) for r in REGIONS},
    }


def simulate(products: list[dict], policy: str, frequency: int, days: int = 10,
             demand_factor: float = 1.0, po_usable_day: int = 3, inbound_usable_day: int = 2) -> dict:
    """Run one policy for one round on a shared, deterministic demand path.

    Each product dict needs: code, name, central, regional (dict), inbound, new_po,
    daily_by_region (dict of a number, or a list with one value per day),
    entries (from zmb1b_entries), price, unit_cost.
    """
    ship_days = set(range(1, days + 1, max(1, frequency)))
    state = {}
    for p in products:
        state[p["code"]] = {"central": float(p["central"]), "reg": {r: float(p["regional"][r]) for r in REGIONS},
                            "transit": {r: 0.0 for r in REGIONS}}
    totals = {p["code"]: {"sold": 0.0, "lost": 0.0, "demand": 0.0, "shipped": 0.0, "fees": 0.0,
                          "received": 0.0, "runs": 0, "trace": []} for p in products}
    storage_cost = 0.0
    for day in range(1, days + 1):
        company_units = 0.0
        for p in products:
            s, t = state[p["code"]], totals[p["code"]]
            # 1. Opening: arrivals from yesterday's transfers and from suppliers.
            for r in REGIONS:
                s["reg"][r] += s["transit"][r]; s["transit"][r] = 0.0
            if day == inbound_usable_day and p["inbound"]:
                s["central"] += p["inbound"]; t["received"] += p["inbound"]
            if day == po_usable_day and p["new_po"]:
                s["central"] += p["new_po"]; t["received"] += p["new_po"]
            opening = {r: s["reg"][r] for r in REGIONS}
            # 2. Transfer run.
            shipped_today = {r: 0 for r in REGIONS}
            if day in ship_days:
                if policy == "PUSH":
                    want = {r: float(p["entries"]["PUSH"][r]) for r in REGIONS}
                else:
                    want = {r: max(0.0, p["entries"]["PULL"][r] - s["reg"][r]) for r in REGIONS}
                need = sum(want.values())
                scale = 1.0 if need <= s["central"] or need == 0 else s["central"] / need
                for r in REGIONS:
                    q = math.floor(want[r] * scale + 1e-9)
                    if q > 0:
                        s["central"] -= q; s["transit"][r] += q
                        t["shipped"] += q; t["fees"] += TRANSFER_FEE; shipped_today[r] = q
                if any(shipped_today.values()):
                    t["runs"] += 1
            # 3. Sales from regional stock. No stock, no sale.
            sold_today, lost_today = {}, {}
            for r in REGIONS:
                base_d = p["daily_by_region"][r]
                d = (base_d[day - 1] if isinstance(base_d, (list, tuple)) else base_d) * demand_factor
                sold = min(s["reg"][r], d)
                s["reg"][r] -= sold
                t["sold"] += sold; t["lost"] += d - sold; t["demand"] += d
                sold_today[r] = round(sold, 1); lost_today[r] = round(d - sold, 1)
            t["trace"].append({"day": day, "central_after_ship": round(s["central"]),
                               **{f"{r} open": round(opening[r]) for r in REGIONS},
                               **{f"{r} ship": shipped_today[r] for r in REGIONS},
                               **{f"{r} lost": lost_today[r] for r in REGIONS}})
            company_units += s["central"] + sum(s["reg"].values()) + sum(s["transit"].values())
        extra = max(0.0, company_units - STORAGE_CAPACITY)
        storage_cost += math.ceil(extra / EXTRA_BLOCK - 1e-9) * EXTRA_BLOCK_COST if extra > 0 else 0.0

    per_product, gp_total, all_priced = [], 0.0, True
    for p in products:
        s, t = state[p["code"]], totals[p["code"]]
        start = p["central"] + sum(p["regional"].values())
        end = s["central"] + sum(s["reg"].values()) + sum(s["transit"].values())
        # Stock conservation: start + received - sold must equal end.
        balance_error = abs(start + t["received"] - t["sold"] - end)
        if p.get("price") is None or p.get("unit_cost") is None:
            all_priced = False; margin_gp = None
        else:
            margin_gp = t["sold"] * (p["price"] - p["unit_cost"])
            gp_total += margin_gp
        per_product.append({"code": p["code"], "product": p["name"], "demand": t["demand"], "sold": t["sold"],
                            "lost": t["lost"], "shipped": t["shipped"], "runs": t["runs"], "fees": t["fees"],
                            "end_regional": sum(s["reg"].values()) + sum(s["transit"].values()),
                            "end_central": s["central"], "gross_margin": margin_gp,
                            "balance_error": balance_error, "trace": t["trace"]})
    fees = sum(x["fees"] for x in per_product)
    return {"policy": policy, "products": per_product,
            "lost": sum(x["lost"] for x in per_product), "sold": sum(x["sold"] for x in per_product),
            "demand": sum(x["demand"] for x in per_product), "fees": fees, "storage_cost": storage_cost,
            "end_regional": sum(x["end_regional"] for x in per_product),
            "profit_after_logistics": (gp_total - fees - storage_cost) if all_priced else None,
            "max_balance_error": max((x["balance_error"] for x in per_product), default=0.0)}


def _winner(push: dict, pull: dict):
    a, b = push["profit_after_logistics"], pull["profit_after_logistics"]
    if a is not None and b is not None:
        if abs(a - b) <= TIE_EUR:
            return None
        return "PULL" if b > a else "PUSH"
    if abs(push["lost"] - pull["lost"]) < 1:
        return None
    return "PULL" if pull["lost"] < push["lost"] else "PUSH"


SCENARIOS = [("Expected demand", 1.0, 3), ("Low demand (80%)", 0.8, 3),
             ("High demand (120%)", 1.2, 3), ("Slow PO (usable day 4)", 1.0, 4)]


def compare(products: list[dict], frequency: int, days: int = 10) -> dict:
    """Run both policies on the same demand paths and pick a recommendation."""
    scenarios = {label: {pol: simulate(products, pol, frequency, days, factor, po_day) for pol in ("PUSH", "PULL")}
                 for label, factor, po_day in SCENARIOS}
    base = scenarios["Expected demand"]
    push, pull = base["PUSH"], base["PULL"]
    winner = _winner(push, pull)
    a, b = push["profit_after_logistics"], pull["profit_after_logistics"]

    reasons = []
    if a is not None and b is not None:
        lead = "" if winner is None else f" ({winner.title()} +€{abs(b - a):,.0f})"
        reasons.append(f"Estimated gross profit after transfer and storage fees: Push €{a:,.0f}, Pull €{b:,.0f}{lead}.")
    lost_gap = push["lost"] - pull["lost"]
    fee_gap = push["fees"] - pull["fees"]
    sales_part = ("both lose the same sales" if abs(lost_gap) < 1 else
                  f"Pull sells {lost_gap:,.0f} more units" if lost_gap > 0 else
                  f"Push sells {-lost_gap:,.0f} more units")
    fee_part = ("the same transfer fees" if abs(fee_gap) < 1 else
                f"Pull pays €{fee_gap:,.0f} less in transfer fees" if fee_gap > 0 else
                f"Push pays €{-fee_gap:,.0f} less in transfer fees")
    reasons.append(f"Tradeoff: {sales_part}, and {fee_part} "
                   f"(Push €{push['fees']:,.0f} vs Pull €{pull['fees']:,.0f}).")

    both_short = min(push["lost"], pull["lost"])
    share_lost = both_short / push["demand"] if push["demand"] else 0
    if share_lost >= 0.05:
        risk = (f"About {both_short:,.0f} units ({share_lost:.0%} of forecast demand) are lost in BOTH modes, mostly in the "
                "first days before the new PO can reach the regions. Transfer mode cannot fix missing stock; "
                "only earlier or larger purchasing can.")
    elif winner == "PUSH":
        risk = "Push keeps sending the same quantity even if demand drops, so regional stock can pile up."
    else:
        risk = "Pull holds a buffer in every region, so more stock sits in regions at the end of the round."

    flips = []
    for label, _, _ in SCENARIOS[1:]:
        w = _winner(scenarios[label]["PUSH"], scenarios[label]["PULL"])
        if w != winner:
            flips.append(f"{label}: {'no real difference' if w is None else w.title() + ' becomes better'}")
    if flips:
        change = "The choice changes if: " + "; ".join(flips) + "."
    else:
        change = ("Same answer at 80% and 120% of forecast demand and with a slow PO. It would change if the "
                  "inventory export is out of date or regional demand shares shift.")

    if winner is None:
        headline = "No real difference: either mode works this round"
        why_equal = ("The two modes end within one transfer fee (€100) of each other. This is legitimate: "
                     + ("both are held back by the same stock shortage." if share_lost >= 0.05
                        else "the fixed Push quantity is close to what Pull would refill."))
    else:
        headline = f"Use {winner}"
        why_equal = None
    conservation_ok = all(s[p]["max_balance_error"] < 1e-6 for s in scenarios.values() for p in s)
    return {"recommended": winner, "headline": headline, "reasons": reasons[:2], "risk": risk, "change": change,
            "why_equal": why_equal, "scenarios": scenarios, "conservation_ok": conservation_ok,
            "assumptions": __doc__.split("Simulation timing assumptions")[1].strip()}
