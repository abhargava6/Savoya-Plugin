# XLSX format

For procurement teams that want to see the math. Use the xlsx skill. One workbook, two sheets.

## Sheet 1 — Quote
Header rows: Savoya logo cell, client, prepared by/on, valid until, event name.
Then one row per leg with columns:
`Date | Leg | Route | Passengers | Vehicle | Qty | Basis (Hourly/Transfer) | Hours | Rate | Cancellation | Leg total`

Below the legs:
- Copy any Core-returned subtotal as a value; omit the row when Core did not return one.
- Show returned adjustment metadata without inventing amounts.
- Copy the Core aggregate total as a value. Do not use pricing formulas.

Amounts formatted `$#,##0.00`. Freeze the header row. Copper fill (#B87333, white text) on the header row; light copper tint (#F7EDE4) on the total row.

## Sheet 2 — Terms
The six verbatim bullets, one per row, plus a "Notes" row listing any TBD items (placeholder flights, unconfirmed dates).

## Never on the sheet
Rate ids, inventory counts, engine warnings, profile ids. Same rules as `client-safe-rules.md`.
