# Presentation notes

## One-minute walkthrough

1. Start the local server and open the browser at `http://127.0.0.1:8765`.
2. Show **Command center**: the selected target round, source-derived valuation and finance cards, readiness warnings, five priority cards and the product decision table.
3. Open **Forecast + MRP**. Explain that MD61 includes the demand buffer, while expected MRP requirement is a separate net quantity after stock and confirmed inbound supply.
4. Open **Stock transfer**. Point to the regional demand shares, copyable North/South/West grid and the cap at observed central stock.
5. Open **Pricing** and show that there is one observed price per product and that the planner carries it forward when elasticity cannot be supported.
6. Open **Finance + valuation** to distinguish actual valuation history from a valuation forecast. Explain that the official lookup table is absent.
7. Return to **Data center** to show header-based report status, local file upload and the inventory-date warning.

## Suggested explanation

“This is designed around the decisions entered in SAP: demand plan, MRP, procurement, transfer, then price. Every quantity traces to uploaded data or a visible assumption. If a required stock snapshot is missing or undated, the app marks the affected recommendation rather than inventing a value.”
