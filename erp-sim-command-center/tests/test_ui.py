"""Drives the real Streamlit app through its sidebar controls (no browser needed)."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")



class UITests(unittest.TestCase):
    def run_with(self, mode, page="Command center"):
        at = AppTest.from_file(APP, default_timeout=120).run()
        at.sidebar.selectbox[1].select(mode).run()          # "Transfer mode"
        at.sidebar.radio[0].set_value(page).run()
        self.assertFalse(at.exception, at.exception)
        return at

    def test_changing_mode_in_ui_changes_zmb1b_but_not_purchase_plan(self):
        push, pull = self.run_with("PUSH"), self.run_with("PULL")
        purchase_push, zmb_push = push.dataframe[0].value, push.dataframe[1].value
        purchase_pull, zmb_pull = pull.dataframe[0].value, pull.dataframe[1].value
        self.assertTrue(purchase_push.equals(purchase_pull))          # purchase plan identical (legitimate)
        self.assertFalse(zmb_push.equals(zmb_pull))                   # ZMB1B entries differ
        self.assertEqual(int(zmb_push.loc[zmb_push.Product == "Milk", "North"].iloc[0]), 105)
        self.assertEqual(int(zmb_pull.loc[zmb_pull.Product == "Milk", "North"].iloc[0]), 133)
        self.assertTrue(any("PUSH" in c.value for c in push.caption))  # "Calculated just now for ... PUSH"

    def test_auto_shows_recommendation(self):
        at = self.run_with("Auto")
        self.assertTrue(any("Use PULL" in m.value for m in at.markdown))

    def test_every_page_renders(self):
        for page in ["Command center", "Final round plan", "Forecast + MRP", "Procurement", "Stock transfer",
                     "Pricing", "Finance + valuation", "Round review", "Data center", "Game rules"]:
            with self.subTest(page=page):
                self.run_with("Auto", page)


if __name__ == "__main__":
    unittest.main()
