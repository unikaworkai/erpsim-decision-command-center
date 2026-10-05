"""Checks for Revision 2 (Push vs Pull). Every expected number here can be redone by hand;
see TEST_RESULTS.md for the arithmetic."""
import unittest
from pathlib import Path

from src import transfer_policy as tp
from src.engine import build_plan, load_data

NONE = {"North": 0, "South": 0, "West": 0}


def one_region_product(demand, push_qty, pull_target, start=100, central=1000, price=None, cost=None):
    """One product, only North has stock and demand. Everything else is zero."""
    return {"code": "X", "name": "Test", "central": central, "regional": {**NONE, "North": start},
            "inbound": 0, "new_po": 0, "daily_by_region": {**NONE, "North": demand},
            "entries": {"PUSH": {**NONE, "North": push_qty}, "PULL": {**NONE, "North": pull_target}},
            "price": price, "unit_cost": cost}


class HandExamples(unittest.TestCase):
    def test_c4_push_and_pull_differ_when_demand_drops(self):
        p = one_region_product([50, 50, 20, 20, 20, 20], push_qty=100, pull_target=200)
        push = tp.simulate([p], "PUSH", frequency=2, days=6, po_usable_day=99, inbound_usable_day=99)
        pull = tp.simulate([p], "PULL", frequency=2, days=6, po_usable_day=99, inbound_usable_day=99)
        self.assertEqual(push["products"][0]["shipped"], 300)   # 100 + 100 + 100
        self.assertEqual(pull["products"][0]["shipped"], 240)   # 100 + 100 + 40
        self.assertEqual(push["end_regional"], 220)
        self.assertEqual(pull["end_regional"], 160)
        self.assertEqual(push["fees"], 300); self.assertEqual(pull["fees"], 300)
        self.assertEqual(push["lost"], 0); self.assertEqual(pull["lost"], 0)

    def test_c5_push_and_pull_match_when_demand_is_steady(self):
        p = one_region_product(50, push_qty=100, pull_target=200)
        push = tp.simulate([p], "PUSH", frequency=2, days=6, po_usable_day=99, inbound_usable_day=99)
        pull = tp.simulate([p], "PULL", frequency=2, days=6, po_usable_day=99, inbound_usable_day=99)
        self.assertEqual(push["products"][0]["shipped"], pull["products"][0]["shipped"])
        self.assertEqual(push["end_regional"], 100); self.assertEqual(pull["end_regional"], 100)

    def test_zmb1b_entries_follow_course_definitions(self):
        e = tp.zmb1b_entries(daily=10, frequency=2, shares={"North": .5, "South": .3, "West": .2}, buffer=10)
        self.assertEqual(e["PUSH"], {"North": 10, "South": 6, "West": 4})   # 10 x 2 x share
        self.assertEqual(e["PULL"], {"North": 15, "South": 9, "West": 6})   # plus buffer x share


class Recommendation(unittest.TestCase):
    def test_tie_is_reported_not_forced(self):
        p = one_region_product(50, push_qty=100, pull_target=150, start=100, price=30, cost=20)
        res = tp.compare([p], frequency=2)
        self.assertIsNone(res["recommended"])
        self.assertIn("No real difference", res["headline"])

    def test_push_can_win(self):
        # Pull target set too low (60 for 100 units of cycle demand): Pull runs short, Push does not.
        p = one_region_product(50, push_qty=100, pull_target=60, start=100, price=60, cost=20)
        self.assertEqual(tp.compare([p], frequency=2)["recommended"], "PUSH")

    def test_pull_can_win(self):
        # Same pattern as real Milk data: warehouse stock is scarce, North already holds plenty,
        # West is empty. Push splits scarce stock across both regions every cycle, so West runs short.
        # Pull sends nothing to North (already above target) and everything to West.
        p = {"code": "X", "name": "Test", "central": 120, "regional": {"North": 300, "South": 0, "West": 0},
             "inbound": 0, "new_po": 0, "daily_by_region": {"North": 10, "South": 0, "West": 50},
             "entries": {"PUSH": {"North": 20, "South": 0, "West": 100}, "PULL": {"North": 30, "South": 0, "West": 120}},
             "price": 60, "unit_cost": 20}
        res = tp.compare([p], frequency=2)
        self.assertEqual(res["recommended"], "PULL")
        base = res["scenarios"]["Expected demand"]
        self.assertLess(base["PULL"]["lost"], base["PUSH"]["lost"])


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()

    def test_mode_changes_transfers_but_not_purchasing(self):
        push = build_plan(self.data, 9, "push", 2)
        pull = build_plan(self.data, 9, "pull", 2)
        self.assertEqual(push["purchase_qty"], pull["purchase_qty"])            # legitimate equality
        self.assertEqual([r["mrp"] for r in push["rows"]], [r["mrp"] for r in pull["rows"]])
        self.assertNotEqual([r["transfers"] for r in push["rows"]], [r["transfers"] for r in pull["rows"]])
        self.assertEqual(push["mode"], "PUSH"); self.assertEqual(pull["mode"], "PULL")

    def test_stock_is_conserved_in_every_scenario(self):
        self.assertTrue(build_plan(self.data, 9, "auto", 2)["policy"]["conservation_ok"])

    def test_missing_inventory_gives_no_transfer_numbers(self):
        data = dict(self.data); data["has_inventory"] = False
        plan = build_plan(data, 9, "auto", 2)
        self.assertIsNone(plan["policy"])
        self.assertTrue(all(r["transfers"] is None and r["mrp"] is None for r in plan["rows"]))


if __name__ == "__main__":
    unittest.main()
