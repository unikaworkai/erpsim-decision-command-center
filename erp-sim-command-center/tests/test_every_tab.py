"""Opens EVERY tab with EVERY planning round, transfer mode and cycle, through the real sidebar controls.

On each page it checks: no crash, no broken values ("nan", "None", "—") in the KPI cards or text,
no negative quantities in the tables, and that Push and Pull show different ZMB1B tables when stock is known.
"""
import math
import re
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
PAGES = ["Command center", "Final round plan", "Forecast + MRP", "Procurement", "Stock transfer",
         "Pricing", "Finance + valuation", "Round review", "Data center", "Game rules"]
SIGNED = {"Forecast error", "Gross profit after fees (€)"}   # a minus sign is real here (e.g. daily transfers can cost more than the margin)
BAD_TEXT = re.compile(r"\bnan\b|\bNaN\b|None units|€nan|€None")


def problems(at):
    found = []
    if at.exception:
        found.append(f"exception: {at.exception[0].value[:120]}")
    for m in at.metric:
        if m.value in ("—", "None", "nan") or "nan" in str(m.value):
            found.append(f"KPI '{m.label}' shows {m.value!r}")
    for el in list(at.markdown) + list(at.caption) + list(at.info) + list(at.warning):
        if BAD_TEXT.search(str(el.value)):
            found.append(f"text: {str(el.value)[:100]}")
    for df in at.dataframe:
        frame = df.value
        for col in frame.columns:
            if col in SIGNED:
                continue
            for v in frame[col]:
                if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) and v < 0:
                    found.append(f"negative value {v} in column '{col}'")
                    break
    return found


class EveryTab(unittest.TestCase):
    def check(self, round_, mode, cycle):
        at = AppTest.from_file(APP, default_timeout=120).run()
        at.sidebar.selectbox[0].select(round_).run()
        at.sidebar.selectbox[1].select(mode).run()
        at.sidebar.selectbox[2].select(cycle).run()
        for page in PAGES:
            at.sidebar.radio[0].set_value(page).run()
            with self.subTest(round=round_, mode=mode, cycle=cycle, page=page):
                self.assertEqual(problems(at), [])

    def test_every_round_mode_and_tab(self):
        for round_ in range(2, 10):
            for mode in ("Auto", "PULL", "PUSH"):
                self.check(round_, mode, 2)

    def test_every_cycle_in_the_next_round(self):
        for cycle in (1, 3, 5):
            for mode in ("Auto", "PULL", "PUSH"):
                self.check(9, mode, cycle)

    def test_push_and_pull_tables_differ_on_both_transfer_tabs(self):
        for page in ("Command center", "Stock transfer"):
            tables = {}
            for mode in ("PUSH", "PULL"):
                at = AppTest.from_file(APP, default_timeout=120).run()
                at.sidebar.selectbox[1].select(mode).run()
                at.sidebar.radio[0].set_value(page).run()
                zmb = next(df.value for df in at.dataframe if "What you type in ZMB1B" in df.value.columns)
                tables[mode] = zmb
            with self.subTest(page=page):
                self.assertFalse(tables["PUSH"].equals(tables["PULL"]))
                self.assertEqual(int(tables["PUSH"].loc[tables["PUSH"].Product == "Milk", "North"].iloc[0]), 105)
                self.assertEqual(int(tables["PULL"].loc[tables["PULL"].Product == "Milk", "North"].iloc[0]), 133)


if __name__ == "__main__":
    unittest.main()
