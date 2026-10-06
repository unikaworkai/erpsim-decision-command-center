# Build note: ERPsim Decision Command Center

**Purpose and user.** I am Pricing Lead on a five-person team in ERPsim Logistics Extended. Between rounds we have a few minutes to decide MD61 quantities, Push or Pull transfers, and prices, and the data is spread across several SAP reports. The app turns our exports into one plan that we type into SAP ourselves. It never connects to SAP.

**Inputs and outputs.** Inputs: our SAP exports (OData workbook, ZVA05 sales, ZMB52 inventory, ZME2N POs, valuation), packaged or uploaded, plus the planning round, transfer mode and cycle days. Outputs: the MD61 target and expected MRP need per product; ZMB1B entries per region; a Push vs Pull recommendation with two reasons, the main risk and what would change it; prices and a downloadable decision sheet.

**Revision 1: readable text.** The KPI cards were white on white in Mac dark mode (1.04:1 contrast), and the sidebar dropdowns were white on white in light mode (1.00:1). The cause was a missing theme file plus CSS that painted the whole sidebar white. I added a fixed light theme at the repo root, replaced the broad CSS with narrow rules that set text and background together, and removed misleading green up arrows from the KPIs. Now the worst contrast on all 10 pages is 5.05:1.

**Revision 2: Push/Pull did nothing.** Switching the mode gave identical numbers, because the code read the mode and never used it. Now Push sends a fixed quantity every cycle and Pull keeps a target level (course slides 13 and 14). The app simulates both on the same demand and recommends one: Pull, about €985 more gross profit after transfer fees. The purchase plan correctly stays the same in both modes, and the page says why.

**Errors found in my own testing, and fixed.** Picking a past round used today's stock, the valuation and profit cards never followed the round, and a sales upload replaced older rounds instead of adding to them. All three are fixed. The cards now match the course valuation formula (Round 3: 45,816.66 / 3 x 8 / 10% = 1,221,777.60, the same as SAP).

**Three checks** (details in TEST_RESULTS.md; 27 automated tests pass):

| Check | Expected | Actual |
|---|---|---|
| Known: sales 100 and 120, stock 18, inbound 3 | Forecast 112.5, buffer 3, MRP need 94 (95 with Excel rounding) | 112, 3, 94. Pass |
| Realistic: our Round 9 data | No negative needs, Cream 0, same purchases in both modes, Push and Pull transfers differ | 2,403 units in both modes; Milk North Push 105, Pull 133. Pass |
| Invalid: inventory file with no Stock column | Clear message, no misleading numbers, no crash | Before: silently ignored (Fail). After: named error, "Pending", stock numbers withheld. Pass |

**Independent verification.** On 5 October 2026 I redid the known example, the Milk row (from the raw exports) and the Push/Pull example in Excel (Independent_Check_Unika.xlsx). Everything matched, except one unit on MD61 because Excel rounds 112.5 up and Python rounds it down.

**One limitation.** The forecast uses observed sales. When a region was out of stock, true demand is hidden, so the forecast and the Push/Pull comparison can understate demand. The inventory export has no date, so I must check it against SAP first.

**How AI helped vs what I did.** I used AI coding assistants: OpenAI Codex built the first version, and Claude (Anthropic) helped with the revisions and fixes. They wrote the code and tests and traced the bugs. I chose the problem and the user, decided which course rules the app must follow and what counts as correct (for example, that equal purchase numbers in Push and Pull are right), tested the live app and found the round and upload errors, and checked the key numbers myself in Excel. I make all game decisions.
