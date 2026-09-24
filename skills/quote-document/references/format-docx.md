# DOCX / PDF format

Use the docx skill (`/mnt/skills/public/docx/SKILL.md`) to build; use the pdf skill to convert when PDF is requested. Read `client-safe-rules.md` first — this format is assembled by hand and leaks are easy.

## Theme — light print variant
The email is dark; paper is light. Keep the brand through accents, not background.
- Page: white. Body text #1A1A1A, DM Sans (fallback Calibri) 10.5pt.
- Headings: Georgia. Title 26pt, section 16pt, leg heading 13pt. Copper #B87333 for section headings and rules.
- Tables: copper 1pt top rule on header row, hairline #DDD row dividers, no vertical borders, right-aligned amounts.
- Callouts (special event, TBD flight): light amber fill #FFF7E6 with amber left border #F59E0B.
- Totals: engine subtotal and adjustments in body weight; total row bold with a copper top rule.

## Page plan
1. **Cover** (only if cover image or client logo provided, otherwise skip to page 1): cover image full-bleed, Savoya logo, client logo, title, event name, dates, prepared for/by.
2. **Page 1**: title block (if no cover), meta strip, intro note, then itinerary.
3. **Itinerary**: one section per leg. Heading → route table (Stop · Address · Time/Wait) → pricing line → cancellation line → callouts → client notes.
4. **Pricing summary**: table with each leg's total, engine subtotal, adjustment lines, total.
5. **Contact + closing**: account manager block, closing note.
6. **Terms**: verbatim bullets from `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/terms.md`, 9pt, muted #6B6560.

## Letterhead
Savoya logo (hosted PNG — download to a temp file for docx embedding), copper hairline under it, page number footer "Prepared by Savoya · Page X of Y".

## PDF
Render DOCX first, then convert with the pdf skill's LibreOffice path. Check page breaks around the totals table — it should never split across pages.
