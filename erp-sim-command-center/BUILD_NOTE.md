# Build note: ERPsim Decision Command Center

Unika Maharjan | Individual App Assignment | ERPsim Logistics Extended
Live app: https://erpsim-decision-command-center-vicd6jnz7ngn5azcg88vnt.streamlit.app/

**Purpose and user.** I am Pricing Lead on a five-person team in ERPsim Logistics Extended. Between rounds we have a few minutes to decide MD61 quantities, ZMB1B Push or Pull transfers and prices, and the data sits in five SAP reports. The app combines our exports into one plan. It never connects to SAP; we enter every decision ourselves.

**Inputs and outputs.** Inputs: our SAP exports (OData workbook, ZVA05 sales, ZMB52 inventory, ZME2N purchase orders, valuation), packaged or uploaded, plus the planning round, transfer mode and cycle days. Outputs: the MD61 target and expected MRP need for each product; ZMB1B entries for North, South and West; a Push vs Pull recommendation with two reasons, the main risk and what would change it; prices and a downloadable decision sheet. All calculations are plain Python, with no paid service.

**Revision 1: readable text.** I asked the AI assistant to fix KPI cards that were white on white in Mac dark mode (1.04:1 contrast) and sidebar controls that were white on white in light mode (1.00:1). The cause was a missing theme file and CSS that turned the whole sidebar white. We added a fixed theme and narrow CSS rules. A browser check now shows at least 5.05:1 on all 10 pages.

**Revision 2: Push and Pull.** Switching the mode gave identical numbers. I asked the assistant to trace it: the code read the mode but never used it, and its Pull number would have made SAP subtract regional stock twice. Now Push is the quantity to send every cycle and Pull is the target level to keep (course slides 13 and 14). The app simulates both on the same demand and recommends one. The purchase plan correctly stays the same in both modes.

**Also found in my own testing and fixed:** a past round used today's stock, the finance figures ignored the planning round (they now match SAP and the course formula), Round review compared with an unfinished round, and a sales upload replaced older rounds.

**Three checks** (30 automated tests also pass, including every tab with every setting; details in TEST_RESULTS.md):

| Check | Expected | Actual |
|---|---|---|
| 1. Known example | Sales 100 and 120, stock 18, inbound 3, 3-day cycle. Forecast 112.5, buffer 3, MRP need 94 (Python rounding) or 95 (Excel rounding). Push North 17, Pull North 19. | App: forecast 112, buffer 3, MRP need 94, Push 17, Pull 19. Excel: 95. **Pass.** The 1-unit gap is only the rounding of 112.5. |
| 2. Realistic example | Our Round 9 data: no negative needs, Cream needs 0, same purchase plan in Push and Pull, different transfers. | 2,403 units (EUR 82,033.83) in both modes, Cream 0, Milk North Push 105 vs Pull 133. **Pass.** |
| 3. Invalid input | Inventory file with no Stock column: clear message, no misleading numbers, no crash. | Before the fix: ignored silently and the old plan stayed (Fail). After: named error, "Pending" instead of numbers, no crash. **Pass.** |

**Independent verification (Excel, 5 October 2026).** I rebuilt the Milk plan from the raw exports myself: sales of 892, 1,218 and 711 gave a forecast of 899.3, buffer 47 and MD61 target 946; stock of 281 gave an MRP need of 665; Milk North Push 105 and Pull 133; total 2,403 units and EUR 82,033.83. I also rebuilt the six-day Push and Pull example (Push ships 300, ends with 220; Pull ships 240, ends with 160). Everything matched the app.

**One limitation.** The forecast uses observed sales. When a region runs out of stock, true demand is hidden, so the forecast and the Push vs Pull comparison can understate demand. The inventory export also has no date, so I must check it against SAP first.

**How AI helped, and what I decided and verified.** I used AI coding assistants. OpenAI Codex built the first version; after I reached its usage limit, Claude (Anthropic) helped with the revisions, fixes and tests. They wrote the code and tests and traced the causes of the bugs. I chose the user and the problem, set the course rules the app must follow (Push is a quantity per cycle, Pull is a target level), decided that equal purchase totals in both modes are correct, tested the live app and found the round and upload errors, and checked the key results myself in Excel. I make all game decisions.
