# Build note: ERPsim Decision Command Center

**Purpose and user.** I am Pricing Lead on a five-person team in ERPsim Logistics Extended. Between rounds we have a few minutes to decide MD61 quantities, Push or Pull transfers, and prices. The data for this is spread across several SAP reports. This app turns our exports into one plan that we type into SAP ourselves. It never connects to SAP.

**Inputs and outputs.**
- **Inputs:** our SAP exports (OData workbook, detailed sales, ZMB52 inventory, ZME2N POs, valuation), packaged or uploaded, plus the planning round, transfer mode and cycle days.
- **Outputs:**
  - the MD61 target and expected MRP need for each product;
  - ZMB1B entries for each region;
  - a Push vs Pull recommendation with two reasons, the main risk and what would change it;
  - prices and a downloadable decision sheet.

**Revision 1: readable text.** The KPI cards were white on white on my Mac (dark mode, 1.04:1 contrast), and the sidebar dropdowns were white on white in light mode (1.00:1). The cause was a missing theme file plus CSS that painted everything in the sidebar white. I added a fixed light theme at the repo root, which is the only place Streamlit Cloud reads it. I also replaced the broad CSS with narrow rules that set text and background together, and removed misleading green up arrows from the KPIs. After the fix, the worst contrast on all 10 pages is 5.05:1.

**Revision 2: Push/Pull did nothing.** Switching the mode gave identical numbers. In the code, the mode was read and then never used. One formula was applied to every mode, and in Pull mode that formula would subtract regional stock twice.
- I rebuilt this to follow the course definitions: Push sends a fixed quantity every cycle, and Pull keeps a target level.
- The app now simulates both modes over the round on the same demand and recommends one.
- The purchase plan correctly stays the same in both modes, and the page now says why.
- With our data the app recommends Pull: about €985 more gross profit after transfer fees.

**Three checks** (details in TEST_RESULTS.md):

| Check | Expected | Actual |
|---|---|---|
| Known example: sales of 100 and 120, stock 18, inbound 3 | Forecast 112.5, buffer 3, MRP need 94 (95 with Excel rounding) | 112, 3, 94. Pass |
| Realistic: our Round 9 data | No negative needs, Cream 0, same purchases in both modes, Push and Pull transfers differ | 2,403 units in both modes. Milk North Push 105, Pull 133. Pass |
| Invalid: inventory file with no Stock column | Clear message, no misleading numbers, no crash | Before: silently ignored (Fail). After: named error, "Pending", stock numbers withheld. Pass |

**Independent verification:** Pending. I will redo the known example and the Milk row of the realistic example in Excel. One difference is already known: Python rounds 112.5 down to 112, while Excel rounds it up to 113.

**One limitation.** The forecast uses observed sales. When a region was out of stock, true demand is hidden, so the forecast and the Push/Pull comparison can understate demand. The inventory export also has no date, so I must check it against SAP first.

**How AI helped vs what I did.** OpenAI Codex built the first version. Claude (Anthropic) did Revisions 1 and 2 after I hit my Codex limit. It traced the bugs, wrote the fixes and tests, and measured contrast in a browser. I defined the problems, chose the course rules to follow, decided what counts as correct (including keeping equal purchase numbers), and am doing the independent checks. I make all game decisions. I have asked the instructor whether Claude-assisted revisions meet the "Build with Codex" requirement.
