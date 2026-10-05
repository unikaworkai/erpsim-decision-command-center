# Presentation: slides and 4-minute demo

Use the packaged course data only. Backup screenshots are in `docs/evidence/`.

## Slide 1. Problem and user
- **Title:** ERPsim Decision Command Center
- **User:** me, Pricing Lead on a team of 5, ERPsim Logistics Extended.
- **Problem:** a few minutes between rounds to decide MD61, Push or Pull, and prices. The data sits in 5 SAP reports.
- **What it does:** reads our exports and shows what to type into MD61 and ZMB1B, with the reason behind it. It never touches SAP.

## Slide 2. One input, one output
- **Input:** Transfer mode in the sidebar (PUSH, then PULL), Round 9, 2-day cycle.
- **Output:** the purchase plan stays at 2,403 units, while the ZMB1B entries change. Milk North is 105 to send every cycle (Push) versus a target of 133 (Pull).
- **Recommendation:** Use Pull, about €985 more gross profit after transfer fees.
- **Screenshots:** `rev2_AFTER_stock_transfer_PUSH.png` and `rev2_AFTER_stock_transfer_PULL.png`.

## Slide 3. A check that gave me confidence
- **The check:** a broken inventory file (Stock column deleted).
- **Before:** the app showed no message and kept the old 2,403-unit plan, which is a silent and misleading result.
- **After:** a named error, "Pending" instead of a number, and stock-based numbers withheld.
- **Also:** hand arithmetic for the Milk row (281 on hand, 665 to buy, Push 105, Pull 133). My Excel recheck: Pending.

## Slide 4. A revision and a limitation
- **Revision 2:** Push and Pull used to give identical numbers. The code read the mode and never used it. Now the modes follow the course definitions and are simulated on the same demand.
- **Revision 1 (briefly):** KPI cards were white on white in dark mode (1.04:1). After the fix the worst case is 5.05:1.
- **Limitation:** sales hide true demand when a region is out of stock, and the inventory export has no date.

## 4-minute demo script

| Time | Do | Say |
|---|---|---|
| 0:00 | Slide 1 | Who it is for and the problem |
| 0:40 | Open the live app, Command center | "These are the next-round numbers from our real exports." |
| 1:10 | Point at the Purchase plan, then switch Transfer mode PUSH to PULL | "Purchasing stays 2,403: transfer mode does not change MD61. The ZMB1B numbers do change: Milk North 105 versus 133." |
| 1:50 | Open the recommendation and "Why this result?" | "Pull wins by about €985. The big risk is that a quarter of demand is lost in both modes because the warehouse is empty, so purchasing timing matters more." |
| 2:40 | Upload `data/test_inputs/INVALID_inventory_no_Stock_column.xlsx` | "A bad file gets a clear message and no fake numbers." |
| 3:20 | Slide 4 | One revision and one limitation |
| 3:50 | End | Questions |

## Likely questions
- **Why is the purchase plan the same in Push and Pull?** In the course, Push and Pull are only ZMB1B modes. They move stock to the regions after it is bought.
- **Why is Pull recommended?** In our data, South already holds more Milk than it needs. Pull sends nothing there, while Push keeps sending. Pull pays fewer transfer fees.
- **What would change the answer?** Stale inventory, a shift in regional demand, or settings where Push sells more units than its extra fees cost. The app reruns the comparison at 80% demand, 120% demand and with a slow PO.
- **Did AI do it?** Codex built version 1 and Claude did the two revisions. I chose the rules, checked the results and enter every decision in SAP myself.
