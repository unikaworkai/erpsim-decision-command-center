# Revision log

App: ERPsim Decision Command Center (Logistics Extended)
Live app: https://erpsim-decision-command-center-vicd6jnz7ngn5azcg88vnt.streamlit.app/

## Tools actually used

| Stage | Tool |
|---|---|
| First version (engine, pages, first tests) | OpenAI Codex |
| Revision 1 and Revision 2 (diagnosis, code changes, tests, checks) | Claude (Anthropic), used after I reached my Codex usage limit |
| Decisions, testing in SAP, independent arithmetic checks | Me |

**Open question for the instructor:** the brief says "Build with Codex" and "note what you asked Codex to change". Both revisions below were made with Claude, not Codex. I am asking whether that is acceptable. Status: **Pending**.

The old version is kept in GitHub history (the commit before these changes), so it can be restored.

---

## Revision 1: unreadable KPIs and sidebar

**Status: Verified** (rendered in a real browser before and after, contrast measured on all 10 pages)

**Before-state problem.** The repo had no theme file, so Streamlit followed the viewer's computer setting.
- On my Mac in dark mode, Streamlit used light text (#FAFAFA), but our CSS painted the KPI cards white. KPI text was 1.04 : 1 contrast. Basically invisible.
- In light mode the KPIs were fine, but the rule `[data-testid="stSidebar"] * { color: #f6f9ff }` made every sidebar item white, including the Upload button and the dropdown values. Those were 1.00 : 1. My professor would probably see this version.
- Grey captions were drawn at 60% opacity, so they were only 3.88 : 1.
- The KPI notes sat in the metric "delta" slot, which drew a green up arrow next to things like a purchase cost. That suggests "went up, good", which is misleading.

**What I requested.** Make all text readable, keep the layout and colours, and do not use global white-text rules.

**Why it mattered.** I read these numbers during a live round. If I cannot read them, the app fails its main job.

**Tool used.** Claude.

**Files changed.**
- `.streamlit/config.toml` at the **repo root** (new). Streamlit Cloud only reads the config from the repo root, even when the app is in a subfolder. It fixes the light theme, keeps the navy sidebar through the supported `[theme.sidebar]` section, and sets readable error text colours.
- `erp-sim-command-center/streamlit_app.py`: removed the global sidebar and page colour rules. The remaining rules always set text and background colour together. Captions set to full opacity. KPI notes moved from the delta slot to a plain caption (new `kpi()` helper).
- `erp-sim-command-center/requirements.txt`: Streamlit at least 1.50 (the code already used features that older versions do not have).

**Verification.**
- I measured every visible text item against its real background, including opacity, in a headless browser, with the computer set to dark and to light.
- Before: up to 16 failures per page, worst 1.00 : 1. After: 0 failures on all 10 pages and on the error message state, worst 5.05 : 1.
- Screenshots are in `docs/evidence/rev1_*`.

**Remaining limitation.** Tables are drawn on a canvas, so the contrast script cannot read their text. I checked them by eye in the screenshots. The live Cloud app still needs to be checked after the update is pushed.

---

## Revision 2: Push / Pull gave the same numbers

**Status: Verified** (unit tests, UI test through the real sidebar, browser screenshots)

**Before-state problem.** Switching Transfer mode between Auto, PULL and PUSH changed nothing. I traced the code. In `src/engine.py`, `build_plan()` turned "auto" into "PULL", saved the name, and **never used the mode again**. Every mode used one formula: (cycle demand + buffer) minus regional stock. With my real data, Milk transfers were North 133, South 0, West 0 in all three modes.

That old number was also unsafe. In SAP's Pull mode, you type a target and SAP subtracts regional stock itself. Typing a number that already had stock subtracted would subtract it twice.

**What the course says** (Logistics Extended guide, slides 13 and 14; Job Aid page 1):
- **Push:** you enter the quantity to **send** to each region every cycle.
- **Pull:** you enter the **target** to keep in each region, and each cycle SAP ships target minus stock.

Both are ZMB1B only. Neither changes MD61, MD01 or ME59N.

**Legitimate equality kept.** The purchase plan (MD61 target, MRP need, 2,403 units) is the same in both modes, and that is correct: purchasing is calculated before transfer mode is ever used. The page now says so directly above the table.

**What I requested.** Make the mode actually change the transfer numbers, follow the course definitions, compare both modes fairly, and help me choose, without forcing different numbers where they should be equal.

**Tool used.** Claude.

**Files changed.**
- `src/transfer_policy.py` (new):
  - ZMB1B entries for each mode.
  - A day-by-day simulation of the 10-day round, with both modes run on the same demand.
  - A recommendation with two reasons, the main risk and what would change it.
- `src/engine.py`:
  - The mode now picks which entries are shown.
  - "Auto" uses the comparison's recommendation.
  - Purchase totals show "Pending" instead of 0 when stock is unknown.
  - Rejected uploads are reported with a reason.
  - Text in a Stock cell is no longer silently turned into 0.
- `streamlit_app.py`:
  - The purchase table is now labelled "Purchase plan".
  - New transfer decision box and "Why this result?" view with formulas, a comparison table, the assumptions and a day-by-day trace.
  - A line showing which inputs produced the results.
  - Push and Pull side by side on the Stock transfer page.
  - Clear ZMB1B labels in the final plan and the CSV.
- Fixed a display bug: margins, regional shares and forecast errors were fractions shown with a % sign (an 18% margin showed as "0.2%").
- `tests/`:
  - Two old tests used `/Users/unikamaharjan/Downloads`, so they only worked on my Mac. They now use the packaged data.
  - Added tests for Push/Pull, invalid input and the UI.

**Before / after (my real data, Round 9, 2-day cycle).**

| | Before | After |
|---|---|---|
| Milk North, PUSH | 133 | 105 (send every cycle) |
| Milk North, PULL | 133 | 133 (target to keep) |
| Purchase plan | 2,403 units in every mode | 2,403 units in every mode (correct) |
| Recommendation | none | Use Pull: about €985 more gross profit after transfer fees |

**Verification.**
- 20 automated tests pass:
  - the hand examples C4 and C5;
  - a tie case, a case where Push should win and a case where Pull should win;
  - stock conservation in every scenario;
  - mode changes transfers but not purchasing;
  - invalid inputs;
  - a UI test that changes the real sidebar dropdown and checks that Milk North changes from 105 to 133 while the purchase table stays the same.
- Screenshots: `docs/evidence/rev2_*`.

**Remaining limitations.**
- The simulation uses the forecast as demand. It does not know true demand when a region was out of stock.
- Several timing details are my assumptions, not confirmed game rules, and they are listed in the app under "Why this result?":
  - whether transfers start on day 1;
  - what happens when the main warehouse is short;
  - whether a small Pull shipment still costs €100.
- The inventory export has no date, so I must check it against SAP before using it.

---

## Extra fixes found during my own testing (after Revisions 1 and 2)

**Status: Verified** (27 automated tests, real browser checks)

While testing the live app I noticed three problems:
- Company valuation and Cumulative profit never changed when I picked another planning round.
- Picking an old round (for example Round 4) still used today's stock.
- Uploading a sales report seemed to do nothing.

1. **Replay of past rounds never switched on.** The code compared the chosen round only with rounds before it, so "replay" was always off. Planning Round 4 used stock from after Round 8, and the warning talked about Round 9. Now a past round opens as a replay. It uses only Rounds 1 to (round minus 1) and shows "Pending" for stock-based numbers. The sidebar only offers Rounds 2 up to the next real round.
2. **KPIs now follow the planning round.** Valuation and profit show the SAP results at the end of the round before the one you plan. I cross-checked these with the course formula, (profit / rounds) x 8 / (7% + 3%):
   - End of Round 3: (45,816.66 / 3) x 8 / 0.10 = 1,221,777.60, the same as SAP.
   - End of Round 7: (100,610.24 / 7) x 8 / 0.10 = 1,149,831.31, the same as SAP.

   Push/Pull does not change these cards, which is correct, and the page now says so.
3. **Sales uploads replaced the packaged sales instead of adding to them.** An upload with only some rounds made older rounds disappear without any message. Now every sales upload is added, and each real row is counted once. A file uploaded twice is not double counted, but two identical SAP order lines are both kept. The sidebar shows what each upload did, for example "Added 74 new rows" or "Nothing new, results do not change".

I also set readable colours for the sidebar's green and blue messages (they were 3.87:1, now at least 4.5:1).

**Files changed:** `src/engine.py`, `streamlit_app.py`, `.streamlit/config.toml`, `tests/test_rounds_and_uploads.py` (new), `tests/test_ui.py`, `tests/test_engine.py`. In `test_engine.py`, detailed sales is now "current", because it covers every finished round. Round 9 has only started.

---

## Last fix: the app felt like "Push and Pull do nothing"

**Status: Verified** (27 automated tests, real browser timing and upload checks)

**Problem.** After I uploaded the final version and switched between Push and Pull in Round 9, the transfer table seemed not to change. The numbers were right, but every click made the app re-read all the Excel reports. On my test server a click took about 5 seconds, and the old table stayed on screen the whole time. The box with the Push vs Pull recommendation (and the "Both modes side by side" tables) also stay the same by design, because they compare both modes.

**Fix.** `streamlit_app.py` now reads the reports once and reuses them (a click takes about 0.5 seconds). The cache key contains the uploaded file contents and the packaged files' timestamps, so a new upload is always read, and each visitor gets a private copy, so one visitor's upload never changes what another sees. I also added two plain sentences on screen: the recommendation box compares both modes, so it does not change; the choice in the sidebar changes the table below it.

**Verification.** Time from click to updated table: about 5 seconds before, about 0.5 seconds after. A bad upload shows "Pending" for that visitor only, and a second visitor still sees 2,403 units. Removing the upload restores the normal plan, uploading the same file says "Nothing new", and a new Round 9 file moves the app to Round 10. All 27 tests pass, and the contrast check still shows at least 5.05:1.

**Files changed:** `streamlit_app.py`, `REVISION_LOG.md`.

---

## Final full audit (every tab, every setting)

**Status: Verified** (30 automated tests, including 330 page views; real browser contrast and speed checks)

I asked for one last check of every tab. Opening every tab with every planning round, transfer mode and cycle found four more problems, now fixed:

1. **Round review compared the forecast with an unfinished round.** Round 9 had only started, so its sales were 0 and the page showed a forecast error of 89,900% for Milk. Now it explains that the round is not finished and asks you to pick a finished round. Picking Round 4 compares the forecast made from Rounds 1 to 3 with the real Round 4 sales.
2. **Finance + valuation mixed time periods.** In a past round, profit followed the round, but revenue, gross profit and bank cash still showed Round 7. All five figures now come from the end of the round before the one you plan, with a label saying which round.
3. **Procurement said "No PO" when stock was unknown.** It now says "Pending inventory". "No PO needed" only appears when the need is really 0.
4. **Final round plan showed a dash instead of a number** for ending stock in a past round. It now says "Pending".

Smaller clean-ups: the Game rules tab now shows units (for example "EUR per purchase order"), the valuation chart is in the right order (R1 D01, D02 ... instead of D1, D10, D2), and it states the valuation formula from the course guide.

The new test `tests/test_every_tab.py` opens all 10 tabs for every setting (330 page views). It checks for crashes, broken values and negative quantities, and checks that Push and Pull give different tables on both transfer tabs. One value is allowed to be negative: "Gross profit after fees" in the Push/Pull comparison. With a 1-day cycle, Push pays EUR 9,900 in transfer fees against EUR 9,836 of gross margin, so the result is really minus EUR 64.

**Files changed:** `streamlit_app.py`, `src/engine.py`, `tests/test_every_tab.py` (new), `REVISION_LOG.md`, `TEST_RESULTS.md`, `README.md`, `BUILD_NOTE.md`.
