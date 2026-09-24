# XLSX format

For procurement teams that want to see the math. Use the xlsx skill. One workbook, two sheets.

## Sheet 1 — Quote
Header rows: Savoya logo cell, client, prepared by/on, valid until, event name.
Then one row per leg with columns:
`Date | Leg | Route | Passengers | Vehicle | Qty | Basis (Hourly/Transfer) | Hours | Rate | Cancellation | Leg total`

Below the legs:
- Engine subtotal = `SUM` of leg totals (formula, not a pasted number)
- One row per adjustment; percent adjustments as `=subtotal*value/100` so the client can flex the discount and watch the total move
- Total = subtotal + SUM(adjustments)

Amounts formatted `$#,##0.00`. Freeze the header row. Copper fill (#B87333, white text) on the header row; light copper tint (#F7EDE4) on the total row.

## Sheet 2 — Terms
The six verbatim bullets, one per row, plus a "Notes" row listing any TBD items (placeholder flights, unconfirmed dates).

## Never on the sheet
Rate ids, inventory counts, engine warnings, profile ids. Same rules as `client-safe-rules.md`.
