# ERPsim Decision Command Center

**Live app (no login needed):** https://erpsim-decision-command-center-vicd6jnz7ngn5azcg88vnt.streamlit.app/

A Streamlit app that helps a player in the ERPsim **Logistics Extended** game plan the next round. It reads the SAP exports, then shows:

- what to enter in **MD61** and what MD01 should buy;
- whether to use **Push or Pull** in ZMB1B, with the numbers to type in;
- the current prices for VK32.

It is decision support only. It does not connect to SAP. I read the plan and enter every decision in SAP myself.

## Who it is for

Me, as Pricing Lead on a five-person team, and any teammate who needs a quick plan between rounds.

## Inputs and outputs

**Inputs**
- **Packaged data.** Our team's exports are in `data/baseline/`, so the app works straight away: O data for all rounds, detailed sales, inventory (ZMB52), PO export (ZME2N) and company valuation.
- **Your own uploads.** Newer `.xlsx` exports uploaded in the sidebar. The app recognises the report type from the column headers.
- **Sidebar choices.** Planning round, transfer mode (Auto, Pull, Push) and transfer cycle (1, 2, 3 or 5 days).

**Outputs**
- **Purchase plan.** Forecast, safety buffer, MD61 target, stock, inbound PO and expected MRP need for each product.
- **Transfer plan.** The ZMB1B entries for each region, a Push vs Pull recommendation with two reasons, the main risk and what would change it, plus a "Why this result?" view with formulas and a day-by-day trace.
- **Prices, finance and review pages.** Prices, finance figures, a round review and a downloadable decision sheet (CSV).

## Install and start (Mac)

You need Python 3.11 or newer. Open **Terminal** and run these lines one at a time.

1. Go to the **top** folder of the project. That is the folder that contains `erp-sim-command-center` and the hidden `.streamlit` folder.

   ```bash
   cd path/to/erpsim-decision-command-center
   ```

2. Create and activate a virtual environment, then install the requirements.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r erp-sim-command-center/requirements.txt
   ```

   On Windows, use `.venv\Scripts\activate` instead of the `source` line.

3. Start the app.

   ```bash
   streamlit run erp-sim-command-center/streamlit_app.py
   ```

The browser opens at **http://localhost:8501**. If it doesn't, paste that address into a browser.

Start the app from the top folder, as shown. The colour settings live in `.streamlit/config.toml` at the top level. Streamlit Cloud reads them from there too.

## Stop

Go back to the Terminal window and press **Ctrl + C**. Type `deactivate` to leave the virtual environment.

## How to use it before a round

1. Open **Data center**. Check that the reports are current. The inventory export has no date, so compare it with SAP ZMB52.
2. In the sidebar, choose the round you are planning. The default is the next round after the last complete one.
3. **Command center, Purchase plan.** Type the MD61 targets into MD61, run MD01, and compare its requisitions with the "Expected MRP need" column.
4. **Command center or Stock transfer, Transfer plan.** Read the recommendation, then enter the ZMB1B numbers:
   - **Push:** quantity to send every cycle.
   - **Pull:** target stock to keep.
   - Set **Scheduling** in ZMB1B to the same cycle days as the sidebar.
5. Open **Why this result?** if you want to see the comparison table, the assumptions and the day-by-day trace.
6. **Final round plan.** Download the decision sheet.
7. After the round, upload the new reports and use **Round review**.

## Demo inputs

- **Normal case:** just open the app (packaged data, Round 9, Auto, 2-day cycle). Then switch Transfer mode between PUSH and PULL. The purchase plan stays at 2,403 units, and Milk North changes from 105 (Push) to 133 (Pull).
- **Invalid input:** upload `data/test_inputs/INVALID_inventory_no_Stock_column.xlsx`. The app names the problem, shows "Pending", and withholds stock-based numbers.

## Tests

From the `erp-sim-command-center` folder:

```bash
python3 -m unittest discover -s tests -v
```

The suite has 27 tests. Details and hand arithmetic are in [TEST_RESULTS.md](TEST_RESULTS.md). The changes are explained in [REVISION_LOG.md](REVISION_LOG.md).

## Rules the app follows

- **Purchasing and transfer mode are separate.** Push and Pull only change ZMB1B. They never change MD61, MD01 or ME59N, so the purchase plan is the same in both modes.
- **Push and Pull follow the course definitions.** Push sends a fixed quantity every cycle. Pull keeps a target level, and SAP ships the gap (guide slides 13 and 14).
- **Incomplete rounds are left out of the forecast.**
- **Uploads add to the packaged data.** A sales upload is added to what is already there, and the sidebar says what it changed. If it has nothing new, the results stay the same, and the app tells you.
- **Planning round.** The default is the next real round. An earlier round opens as a replay that only uses data from before that round, so the KPIs show SAP results at the end of the previous round.
- **Unreadable files are reported, not hidden.** If an uploaded file can't be read, the app says so. If stock is unknown, it shows "Pending" instead of guessing.
- **One price per product** across all regions.

## Limitations

- Sales are observed sales. When a region was out of stock, real demand is hidden, so the forecast can be too low.
- The inventory export has no date. You must check that it matches the current SAP state.
- Some Push/Pull timing details are my assumptions, not confirmed game rules. They are listed in the app under "Why this result?".
- Company valuation is only shown as the imported actual value. The app does not forecast it.
- Python rounds .5 to the nearest even number, so a forecast of 112.5 shows as 112 (Excel shows 113).

## Older files in this repo

`app.py` with `static/` is the first local version, a plain Python web server on port 8765. `cloud_app.py` is an earlier deployment attempt. Neither is used by the live app. The live app runs `erp-sim-command-center/streamlit_app.py`.

## AI use

The first version was built with **OpenAI Codex**. Revisions 1 and 2 were made with **Claude (Anthropic)** after I reached my Codex usage limit. I set the goals, chose what to change, checked the results against the course rules and my team's SAP data, and I make every game decision myself. See [BUILD_NOTE.md](BUILD_NOTE.md).

## Privacy

The files are simulation data from our class game (company C2). They contain no personal information. Uploaded files are only read for the current browser session and are not saved.
