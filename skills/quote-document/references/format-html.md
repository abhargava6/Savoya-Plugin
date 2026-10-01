# HTML email format

`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_html.py quote.json out.html` does the work. Read this to know what it produces and when to hand-edit.

## Theme
Dark brand theme from `design-system.md` (page #0F0F0F, cards #1A1A1A, copper #B87333, Georgia headings, DM Sans body). Same visual family as the internal release-notes email so clients see one Savoya. Table-based layout, inline styles, no `<svg>`, Unicode icons only, hosted images only — the same constraints the release-notes skill learned the hard way.

## Structure (top to bottom)
1. Savoya logo (hosted PNG) — client logo on the right if provided
2. Cover image if provided
3. Title (Georgia 34px) + subtitle (event name / client / dates)
4. Meta strip: Prepared for · Prepared by · Date · Valid until
5. Intro note (if provided)
6. One card per leg: heading, route with stops, passenger/vehicle line, pricing basis, cancellation, special-event callout (amber) if present, TBD flight marker, client notes
7. Pull quote (if provided)
8. Totals card: engine subtotal → each adjustment → total (copper)
9. Closing note + account manager card
10. Terms (muted, 12px, verbatim)
11. Footer

## When to hand-edit the output
- Long itineraries (>6 legs): consider grouping cards by date with a date header row.
- The handoff contains one complete selected Core option. Do not add synthetic comparison cards or totals.
- Anything the script prints as a WARNING to stderr — it lists unresolved "Stop N" labels and placeholder flags.

## Copy-paste into Front/Gmail/Outlook
Open the HTML in a browser, select-all, copy, paste. Same procedure as release notes. Verify the logo renders and the copper divider survives.
