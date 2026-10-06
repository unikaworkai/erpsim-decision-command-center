# Test results

Last run: 5 October 2026, Streamlit 1.65, Python 3.12. **30 automated tests: all passed.**

How to run them yourself (from the `erp-sim-command-center` folder):

```bash
python3 -m unittest discover -s tests -v
```

Status words:
- **Pass / Fail** means the check was run and this was the result.
- **My independent check: Pending** means I (Unika) have not yet redone the arithmetic myself in Excel or on a calculator. A test written by an AI tool does not count as my independent check. I change it to "Done" only after I do it myself.

Note: the old version of this file said "Independent verification: passed". That was a test written by Codex, not a check I did myself.

---

## Check 1. Known example (small, hand-checkable)

**Inputs** (`tests/test_engine.py`, `sample_data()`): one product (Milk). Round 1 sold 100 units and round 2 sold 120, each over 10 days. Regional split North 50%, South 30%, West 20%. Stock: main warehouse 10, North 5, South 2, West 1. Open PO 3 units. No cycle chosen, so the app uses 3 days (fewer than 3 finished rounds).

**Expected** (worked out by hand before looking at the app):

| Step | Arithmetic | Result |
|---|---|---|
| Weights for 2 rounds | 0.3 and 0.5, scaled to add to 1: 0.375 and 0.625 | |
| Forecast | 0.375 × 100 + 0.625 × 120 = 37.5 + 75 | 112.5 |
| Daily sales | 100 / 10 = 10 and 120 / 10 = 12; population std. dev. | 1.0 |
| Buffer | protection days = 3 + 3 = 6; 1.0 × √6 = 2.449, rounded up | 3 |
| MD61 target | forecast + buffer | 115 or 116 (see note) |
| On hand | 10 + 5 + 2 + 1 | 18 |
| Expected MRP need | MD61 minus 18 minus 3 | 94 or 95 |
| Push North | 11.25 per day × 3 days × 0.5 = 16.875, rounded up | 17 |
| Pull North | 16.875 + (3 × 0.5 = 1.5) = 18.375, rounded up | 19 |

**Rounding note.** Python rounds 112.5 to **112** (it rounds .5 to the nearest even number). Excel's ROUND gives **113**. So the app shows MD61 115 and MRP need 94, while Excel will show 116 and 95. This is a one-unit difference, not a logic error, but I need to know it when I check the app in Excel.

**Actual** (app): forecast 112, buffer 3, MD61 115, on hand 18, inbound 3, MRP need 94. Push North 17, South 11, West 7. Pull North 19, South 12, West 8.

**Result: Pass.** **My independent check: Done on 5 October 2026 in Excel (`Independent_Check_Unika.xlsx`, sheet Check1).** All numbers matched, except MD61 was 116 and MRP need 95, because Excel rounds 112.5 up (Python rounds it to 112).

---

## Check 2. Realistic example (our real course data)

**Inputs:** the packaged exports in `data/baseline/` (our team C2): O data for all rounds, detailed sales through Round 8, inventory export `ExportData (1).xlsx`, and the Round 8 PO export. Planning Round 9, 2-day cycle.

**Expected before running:**
- Round 9 is detected as incomplete and left out of the forecast.
- No negative purchase quantities.
- Cream needs 0 because its stock (185) covers its MD61 target (92).
- Yoghurt has the largest need because it has no stock anywhere.
- The purchase plan is the same for Push and Pull.
- Push and Pull transfers should differ, because Milk stock is in the wrong regions: South holds 176 but only gets about 15% of Milk demand, while North gets about 58% and has 0.

**Actual:**
- Rounds 1 to 8 complete, Round 9 excluded.
- Purchase need: Milk 665, Cream 0, Yoghurt 1,179, Cheese 170, Butter 326, Ice Cream 63. Total 2,403 units, €82,033.83 at supplier cost. Same in both modes.
- Milk ZMB1B entries: Push North 105 / South 28 / West 48. Pull targets North 133 / South 35 / West 61.
- Because South already holds 176, which is above its target of 35, Pull ships nothing there. Push keeps sending 28 every cycle anyway.
- Recommendation: **Use Pull**. Estimated gross profit after fees is Push €4,658 vs Pull €5,643. Push sells 62 more units but pays €1,200 more in transfer fees.
- Main risk: about 752 units (25% of demand) are lost in both modes. The main warehouse is empty in the inventory export, so nothing reaches the regions until the new PO arrives.

**Hand arithmetic for one row** (Milk, so I can check it in Excel):

| Step | Arithmetic | Result |
|---|---|---|
| On hand | sum of Stock for CC-T01 in `ExportData (1).xlsx`: 0 + 0 + 176 + 105 | 281 |
| MRP need | MD61 946 minus 281 minus 0 inbound | 665 |
| Push North | 89.9 per day × 2 days × 0.5824 North share = 104.7, rounded up | 105 |
| Pull North | 104.7 + (buffer 47 × 0.5824 = 27.4) = 132.1, rounded up | 133 |

The app uses the unrounded daily rate, so it shows 104.8 and 132.2 inside. The rounded-up results are the same.

**Result: Pass.** **My independent check: Done on 5 October 2026 in Excel (sheet Milk).** I summed the raw exports myself: Milk sales 892, 1218, 711; regions 1643, 427, 751; stock 281; all POs Delivered. Results matched: MD61 946, need 665, Push North 105, Pull North 133, total 2,403 units and €82,033.83.

---

## Check 3. Missing or invalid input

**Inputs** (files in `data/test_inputs/`, uploaded through the sidebar):
- (a) `INVALID_inventory_no_Stock_column.xlsx`: my real inventory export with the Stock column deleted.
- (b) `INVALID_inventory_text_in_Stock.xlsx`: one Stock cell says "lots".
- (c) `INVALID_not_an_ERP_report.xlsx`: a workbook with unrelated columns.

**Expected:** a clear message naming the file and the problem, no crash, and no stock-based numbers shown as if they were valid.

**Actual before the fix** (original app, real browser upload): no crash, but **no message at all**. The app kept showing 2,403 units and the old plan, as if my file had been used. Screenshot: `docs/evidence/check3_BEFORE_invalid_upload_silent.png`. **Fail.**

**Actual after the fix:**
- (a) A red message: "Not used: ... it looks like a ZMB52 inventory export but has no Stock column". The MRP need, transfers and Push/Pull are withheld. The KPI shows "Pending" instead of "0 units".
- (b) The same, with "1 Stock value(s) are not numbers". Before, the text was quietly turned into 0, which would have made the app suggest buying more.
- (c) A message that the columns do not match any report. The page says it is still using the packaged data.

No crash in any case. Tested by real browser upload for (a) and (c), and automatically for all three (`tests/test_invalid_input.py`). Screenshot: `docs/evidence/check3_AFTER_invalid_upload_message.png`. **Pass.**

---

## Focused checks for Revision 2

| Check | Inputs | Expected | Actual | Result |
|---|---|---|---|---|
| C4: Push and Pull should differ | One region, start 100, Push 100, Pull target 200, 2-day cycle, demand 50, 50, then 20 a day for 4 days | Push ships 300, ends 220. Pull ships 100 + 100 + 40 = 240, ends 160 | Same | Pass |
| C5: Push and Pull should match | Same, demand 50 every day | Both ship 100 three times and end with 100 | Same | Pass |
| Tie is reported, not forced | Steady demand, both modes sell everything | "No real difference" | Same | Pass |
| Push can win | Pull target set too low | Recommends Push | Same | Pass |
| Pull can win | Scarce warehouse stock, North full, West empty | Recommends Pull, fewer lost sales | Same | Pass |
| Stock conservation | Real data, all 4 scenarios, both modes | start + received minus sold = end, every product | Holds | Pass |
| UI control reaches calculation | Real app, change the sidebar dropdown PUSH to PULL (`tests/test_ui.py`) | Purchase table identical. Milk North changes 105 to 133 | Same | Pass |
| All 10 pages render | Real app | No error on any page | No error | Pass |
| Past round opens as a replay | Planning round 4 | Uses only Rounds 1 to 3; no stock from after Round 8; KPIs at end of Round 3 | Valuation 1,221,778, profit 45,817, PO need "Pending" | Pass |
| KPIs follow the round through the real UI | Change Planning round to 4 in the sidebar (`tests/test_ui.py`) | Valuation card changes | Changes from 1,125,701 to 1,221,778 | Pass |
| Same sales file uploaded again | Packaged ZVA05 uploaded | No change, and the sidebar says so | "Nothing new" message, same plan | Pass |
| Partial sales upload | A file with only Round 1 | Older rounds stay | Rounds 1 to 8 still complete | Pass |
| New round uploaded | A file with a full Round 9 | Plan moves to Round 10 | Round 10 planner, based on 9 rounds | Pass |
| Every tab, every setting | All 10 tabs x Planning rounds 2 to 9 x Auto/Pull/Push, plus cycles 1, 3 and 5 in Round 9 (330 page views, `tests/test_every_tab.py`) | No crash, no "nan"/"None" values, no negative quantities | All clean | Pass |
| Push and Pull on both transfer tabs | Command center and Stock transfer, PUSH then PULL | Different ZMB1B tables, Milk North 105 vs 133 | Same | Pass |
| Speed of a click | Change Transfer mode in a real browser | Table updates within about 1 second | 0.6 to 0.8 seconds (before: about 5 seconds) | Pass |

Hand arithmetic for C4 (one row per day; open = morning stock, ship = sent that day, arrives next morning):

| Day | Push: open / ship / sold / close | Pull: open / ship / sold / close |
|---|---|---|
| 1 | 100 / 100 / 50 / 50 | 100 / 200 minus 100 = 100 / 50 / 50 |
| 2 | 150 / 0 / 50 / 100 | 150 / 0 / 50 / 100 |
| 3 | 100 / 100 / 20 / 80 | 100 / 100 / 20 / 80 |
| 4 | 180 / 0 / 20 / 160 | 180 / 0 / 20 / 160 |
| 5 | 160 / 100 / 20 / 140 | 160 / 200 minus 160 = 40 / 20 / 140 |
| 6 | 240 / 0 / 20 / **220** | 180 / 0 / 20 / **160** |

**My independent check of C4 and C5: Done on 5 October 2026 in Excel (sheets C4 and C5).** C4: Push 300 shipped, end 220; Pull 240 shipped, end 160. C5: both 300 shipped, end 100.

---

## Readability check (Revision 1)

I rendered the real app in a headless browser with the computer set to dark mode and to light mode. Then I measured the contrast of every visible text item against its real background, including opacity. The target is 4.5 : 1, or 3 : 1 for large text.

| Version | Worst contrast | Failing text items |
|---|---|---|
| Before, dark mode | 1.04 : 1 (KPI cards) | up to 16 per page |
| Before, light mode | 1.00 : 1 (sidebar Upload and dropdowns) | 4 to 6 per page |
| After, both modes, all 10 pages and the error state | 5.05 : 1 | 0 |

Screenshots: `docs/evidence/rev1_*`. **Pass.**

## Not run

- **The live Streamlit Cloud app after the update.** This must be checked after I push the files to GitHub (see README).
- **Using the recommendation in a real ERPsim round.** Not done yet.
