# Build note

## Concise game-rules summary

- Six finished products are identified by material suffixes T01–T06; one price per product applies across the three regional storage locations.
- Central warehouse is storage `03`; North, South and West are `03N`, `03S` and `03W`.
- Supplied workbook rules list V04 lead time of 1–2 virtual days, a €1,000 purchase-order cost, €100 per inter-storage transfer, 4,000 units of main capacity, €300/day per additional 1,000 units, customer payment after 4 days and supplier payment after 5 days.
- Sales, stock, inbound POs and prices must be read as separate facts. MD61 is the demand-planning target; MD01's expected net requirement is reduced by current stock and open inbound orders.
- An incomplete round must not be treated as a zero-demand round. This build uses rounds with sales through day 10 as complete.
- Forecast confidence uses completed-round count and a simple one-round-back error screen; it does not account for historical stockouts, regional availability or price changes.
- Company valuation is an objective, but the brief's formula references an official credit-rating / risk-rate lookup not supplied in the attachments. Only the actual valuation series is therefore displayed.

## Data inspected

The all-round source contains daily sales through round 7, inventory movements through round 8, purchase-order rows through round 7, financial postings through round 7, transfer records, current supplier prices, current price conditions, a current inventory KPI, current inventory, and a `Current_Game_Rules` tab. The supplied detail sales workbook extends observed sales through round 8, day 10. The summary sales export includes day 1 of round 9; that partial round is detected and excluded from forecasts. The valuation export continues through round 8, day 10. The separately supplied current inventory and round-8 PO export have no open PO quantities (all PO lines show Delivered). Financial postings and detailed sales are marked Outdated against the partial round-9 summary; inventory is explicitly flagged as undated.

The SAP screenshots were inspected: the financial statement shows round-end income statement totals; the stock transfer screen shows a push-mode allocation grid and 5-day schedule; the valuation graph shows an actual rising historical series; the pricing-condition screen shows one wholesale price list for each of six products. The screenshot images were not used as machine-readable data inputs.

## Architecture

- `app.py`: Python standard-library local HTTP server, JSON API, upload endpoint and round snapshot save.
- `src/engine.py`: `.xlsx` reading, round selection, deterministic forecasts, MRP netting, transfer allocation and output data.
- `static/index.html`, `styles.css`, `app.js`: responsive Fiori-inspired browser interface with decision pages, CSV download, upload, copy and snapshot controls.
- `game_rules.yaml`: transcribed source rules and explicit unknowns.
- `tests/test_engine.py`: known-example, realistic source-data, invalid-input and independent formula checks.

## Purposeful revisions

1. The first forecast pass considered only an average. It was revised to weight newer completed rounds more heavily and to exclude rounds without day-10 data, reducing stale-history influence and incomplete-period distortion.
2. The first transfer idea allocated target stock directly. It was revised to subtract regional inventory and cap actual dispatch at central stock, preventing the app from recommending goods the warehouse does not hold.
3. Historical replay initially reused current inventory and PO snapshots. It was revised to suppress those undated snapshots during replay to prevent future-state leakage.

## Known limitation

No referenced participant guide, job aid, assignment documents, current financial report export, or valuation credit-rating lookup was attached. Forecast buffers, transfer-cycle choice and demand-weighting are transparent planning assumptions; they are not claimed as official game rules. Phase 1 does not correct regional sales for past stockouts, so regional shares may understate censored demand. Inventory lacks an embedded date, so the user must verify synchronization. The app is a decision aid and does not connect to SAP or execute transactions.
