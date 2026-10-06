# ERPsim Decision Command Center

**Live app (no login, no payment, no API key needed):**
https://erpsim-decision-command-center-vicd6jnz7ngn5azcg88vnt.streamlit.app/

A decision-support app for the ERPsim **Logistics Extended** game (HEC Montréal). It reads our team's SAP exports and gives a plan for the next round: what to enter in **MD61**, whether to use **Push or Pull** in **ZMB1B** (with the exact numbers to type), and a prices review.

It does not connect to SAP. We read the plan and type every decision into SAP ourselves.

## User, task and value

- **User:** me, as Pricing Lead on a five-person team, and my teammates.
- **Task:** between rounds we have a few minutes to decide purchase quantities, regional transfers and prices. The data is spread across five SAP reports.
- **Value:** the app puts the reports together, shows the numbers and the reasons behind them, and makes it hard to miss a stockout or to enter a number with the wrong meaning.

## What goes in and what comes out

**Inputs**
- Our team's exports, already packaged in `erp-sim-command-center/data/baseline/` (OData workbook, ZVA05 detailed sales, ZMB52 inventory, ZME2N purchase orders, company valuation).
- Optional newer `.xlsx` exports, uploaded in the sidebar. The app recognises each report by its column headers.
- Three sidebar choices: **Planning round**, **Transfer mode** (Auto, Pull, Push) and **Transfer cycle** (1, 2, 3 or 5 days).

**Outputs**
- **Purchase plan:** forecast, safety buffer, MD61 target, stock, inbound POs and expected MRP need for each product.
- **Transfer plan:** the ZMB1B entries for North, South and West, and a Push vs Pull recommendation with two reasons, the main risk and what would change it. The "Why this result?" box shows formulas, a comparison table and a day-by-day trace.
- **Pages for prices, finance and round review**, and a downloadable decision sheet (CSV) on the **Final round plan** page.

---

## Option A: use the live app (nothing to install)

1. Open the link at the top of this file in any browser.
2. If the page says the app is asleep, click **Yes, get this app back up!** and wait about one minute.
3. Follow "How to use it" below.
4. To stop, close the browser tab. There is nothing to shut down.

## Option B: run it on your own computer

You need **Python 3.11 or newer** and an internet connection to install the packages. No account, API key, SAP login or paid service is needed.

**1. Get the project folder.** Unzip the submitted ZIP file, or on the GitHub repository click **Code**, then **Download ZIP**, and unzip it. The top folder contains `erp-sim-command-center` and a hidden folder `.streamlit`. Keep them together, because `.streamlit/config.toml` holds the colour theme.

**2. Open a terminal in that top folder.**

- **Mac:** open **Terminal**, type `cd ` (with a space), drag the top folder into the window, press Enter.
- **Windows:** open the top folder in File Explorer, click the address bar, type `cmd`, press Enter.

**3. Create a virtual environment and install the packages** (about 1 to 2 minutes, once only).

Mac or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r erp-sim-command-center/requirements.txt
```

Windows:

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r erp-sim-command-center\requirements.txt
```

**4. Start the app.**

```bash
streamlit run erp-sim-command-center/streamlit_app.py
```

On Windows, use `streamlit run erp-sim-command-center\streamlit_app.py`.

Your browser opens at **http://localhost:8501**. If it does not open by itself, paste that address into a browser. If Streamlit asks for an email address, press Enter to skip it.

**5. Stop the app.** Go back to the terminal window and press **Ctrl + C**. Then type `deactivate` to leave the virtual environment. To start again later, repeat step 2, run the `activate` line from step 3, and then step 4.

---

## How to use it (a 3-minute walkthrough)

1. **Command center** opens first. With the packaged data it shows **Round 9 planner**. Check the five cards: valuation **€1,125,701**, cumulative profit **€100,610**, expected PO need **2,403 units**, expected gross profit €13,170 and products to watch 4 / 6.
2. Read the **Purchase plan** table. Milk, for example: MD61 target 946, stock 281, expected MRP need **665**.
3. Scroll to **Transfer plan (ZMB1B): Push or Pull?** and read the recommendation box (with the packaged data: **Use PULL**, about €985 more estimated gross profit after transfer fees).
4. In the sidebar, set **Transfer mode** to **PUSH**. The table now shows the quantity to **send every cycle**: Milk North **105**. Switch to **PULL**: the table shows the **target stock to keep**: Milk North **133**. The purchase plan stays at 2,403 units, which is correct, because Push and Pull only decide how stock moves from the main warehouse to the regions.
5. Change **Planning round** to **4**. The app opens a replay of a past round: it uses only Rounds 1 to 3, the valuation card shows the SAP value at the end of Round 3 (**€1,221,778**), and stock-based numbers show **Pending**.
6. Open **Final round plan** to download the decision sheet, and **Data center** to see which reports the app is using.
7. In SAP, enter the MD61 targets, run MD01 and ME59N, then enter the ZMB1B numbers.

## Demo inputs

| Case | What to do | What you should see |
|---|---|---|
| Normal | Open the app, leave the settings as they are | Round 9 planner, 2,403 units, recommendation "Use PULL" |
| Push vs Pull | Change **Transfer mode** between PUSH and PULL | Milk North 105 (Push) and 133 (Pull). Purchase plan unchanged |
| Past round | Set **Planning round** to 4 | Replay message, valuation €1,221,778, PO need "Pending" |
| Same file again | Upload `erp-sim-command-center/data/baseline/SalesExportData.xlsx` | Blue message: "Nothing new: all ... rows were already in the data, so results do not change" |
| Invalid input | Upload `erp-sim-command-center/data/test_inputs/INVALID_inventory_no_Stock_column.xlsx` | Red message naming the file and the missing Stock column. PO need shows "Pending". No crash. Remove the file afterwards with the **x** next to it |

## Tests

From the `erp-sim-command-center` folder, with the virtual environment active:

```bash
python3 -m unittest discover -s tests
```

30 tests run: the engine, Push and Pull, invalid inputs, past rounds and uploads, the real sidebar controls, and every tab with every planning round, transfer mode and cycle (330 page views). They take about two minutes. The results, with hand arithmetic and my own Excel recheck, are in [TEST_RESULTS.md](erp-sim-command-center/TEST_RESULTS.md). The two revisions are explained in [REVISION_LOG.md](erp-sim-command-center/REVISION_LOG.md), and the one-page summary is [BUILD_NOTE.md](erp-sim-command-center/BUILD_NOTE.md).

## Rules the app follows

- **Purchasing and transfers are separate.** Push and Pull follow the course definitions (guide slides 13 and 14): Push sends a fixed quantity every cycle, and Pull keeps a target level and ships the gap. They never change MD61, MD01 or ME59N.
- **Forecast:** the last three finished rounds, weighted 20%, 30% and 50%. A round that is not finished is left out.
- **KPIs follow the planning round.** Valuation and profit are SAP results at the end of the round before the one you plan, and they do not change with Push or Pull.
- **Uploads add to the packaged data.** The sidebar says what each file did. A file with nothing new changes nothing, and the app tells you.
- **Unreadable files are reported.** If stock cannot be read, the app shows "Pending" instead of guessing.
- **One price per product** across all regions, as in the game.

## Limitations

- Sales show what we sold, not what customers wanted. When a region runs out of stock, real demand is hidden, so the forecast can be too low.
- The inventory export has no date. Check it against SAP ZMB52 before using the plan.
- Some Push and Pull timing details in the simulation are my assumptions (for example, that a transfer arrives the next morning). They are listed in the app under "Why this result?".
- Python rounds .5 to the nearest even number, so a forecast of 112.5 shows as 112, while Excel shows 113.
- The app recommends. It does not run any SAP transaction.

## Files

- `erp-sim-command-center/streamlit_app.py`: the app (screens and layout).
- `erp-sim-command-center/src/engine.py` and `src/transfer_policy.py`: the calculations.
- `erp-sim-command-center/data/`: packaged team data (`baseline`) and the invalid test files (`test_inputs`).
- `erp-sim-command-center/tests/`: the 30 automated tests.
- `.streamlit/config.toml`: the colour theme (readable text on every screen).
- `erp-sim-command-center/app.py`, `static/` and `cloud_app.py`: the first local version and an earlier deployment file. They are not used by the live app.

## AI use

I used AI coding assistants. OpenAI Codex built the first version. Claude (Anthropic) helped with the revisions, fixes and tests after I reached my Codex usage limit. I set the goals and the course rules, tested the app, found the errors, checked the key results myself in Excel and make every game decision. The details are in the build note.

## Privacy

All data comes from our class simulation (company code C2). It contains no personal information. Uploaded files are read only during the browser session and are not saved.
