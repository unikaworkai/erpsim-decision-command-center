"""Check 3: missing or invalid input gives a clear reason and no misleading numbers."""
import shutil
import tempfile
import unittest
from pathlib import Path

from src.engine import build_plan, load_data

BAD = Path(__file__).resolve().parents[1] / "data" / "test_inputs"


def plan_with_upload(name):
    folder = tempfile.mkdtemp()
    shutil.copy(BAD / name, folder)
    data = load_data(folder)
    return data, build_plan(data, 9, "auto", 2)


class InvalidInput(unittest.TestCase):
    def test_inventory_without_stock_column_is_rejected_and_numbers_withheld(self):
        data, plan = plan_with_upload("INVALID_inventory_no_Stock_column.xlsx")
        self.assertEqual(len(data["rejected_uploads"]), 1)
        self.assertIn("no Stock column", data["rejected_uploads"][0]["reason"])
        self.assertIsNone(plan["purchase_qty"])            # shown as "Pending", not "0 units"
        self.assertIsNone(plan["policy"])                  # no Push/Pull recommendation
        self.assertTrue(all(r["mrp"] is None and r["transfers"] is None for r in plan["rows"]))

    def test_text_in_stock_cell_is_not_turned_into_zero(self):
        data, plan = plan_with_upload("INVALID_inventory_text_in_Stock.xlsx")
        self.assertTrue(any("not numbers" in r["reason"] for r in data["rejected_uploads"]))
        self.assertIsNone(plan["purchase_qty"])

    def test_unrelated_workbook_is_rejected_but_baseline_still_works(self):
        data, plan = plan_with_upload("INVALID_not_an_ERP_report.xlsx")
        self.assertIn("do not match", data["rejected_uploads"][0]["reason"])
        self.assertEqual(plan["purchase_qty"], 2403)        # packaged data still used, and the page says so


if __name__ == "__main__":
    unittest.main()
