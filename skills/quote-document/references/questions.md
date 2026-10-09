# The document questions

Loaded at Stage 2. `decide.py --next` drives the order; option labels are in `asking-questions.md`.

Five questions, fixed order, **one per message, wait after each**. Don't decide which to ask — the script does:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py --next          # prints "next: <key>" and the exact question text
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py <key> <answer>  # records it, prints the next one
```

Loop: run `--next` → ask its question with **`ask_user_input_v0`** (tappable options — see `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md` for the labels; never bare prose) → wait → record the answer → run `--next` again → until it prints `all answered`. This is what makes the flow consistent: you never skip a question the script lists, never merge two, never ask one it has already marked answered. **The script decides which questions apply** — if the user has already said what they want ("just the email"), record `format` first and `--next` drops the cover and route-map questions, because nothing but the PDF and the printable document reads those answers. If the user answers several at once ("no discount, add fuel, PDF"), record each key in turn and still confirm the ones they didn't mention by asking them.

What each answer does:
1. **discount_pct** — **a Core re-quote, not a document line.** Call
   `calculate_temporary_quote_units` with `temporary_discount.basis_points` (500 = 5%) and
   re-normalize from the response. This file used to say *"Do not re-quote through the
   engine"*; that was right under the old contract and is wrong now. A discount applied
   here was our arithmetic on Core's number; a discount applied through Core **is** Core's
   number, and Core returns `subtotal_amount`, `total_amount`,
   `temporary_discount_amount` and `temporary_discount_label` — the whole standard →
   discount → net line, with nothing left to compute.
   - Discounts are **additive in basis points**: 30% contracted + 10% here =
     `effective_discount_basis_points: 4000`, not 37%. Whole percentages only.
   - The result is **never persisted**. Say so.
2. **greeter_cost** *(only when the client asked for a greeter or on-site staff — the script
   inserts it)* — **check Core first; never ask a human for a number Core has.** Greeters are
   vehicle types (12 Hourly Greeter/Coordinator, 13 Single Greet) and price as a quote unit:
   pickup + an `as_directed` stop carrying the hours. Only a market with no greeter rate
   falls back to asking for a cost. See the greeter node in
   `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md`. A hand-entered
   figure on an Irvine quote was **$940** against Core's **$404.20**.
3. **cover** — a catalog key, or a path to their upload → `render_print.py --cover-file`.
4. **personalization** — set `personalization.*` from the answer; defaults stand for anything not mentioned.
5. **map** — `true` → run `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/route_map.py quote.json` before rendering.
   - **Say which map they got, in one line at delivery.** The script sets
     `route_map.style`: `tiled` is a street map, `offline` is a schematic of the stops in
     order with straight connecting lines, drawn when the network blocks the mapping
     services. The document labels them differently, but the CSM decides whether a
     schematic is acceptable for that client and cannot see the PDF as the client will
     until it has gone. For `offline`: *"The map came out as a stops-in-order overview
     rather than a street map — this network blocks the mapping service. Still accurate,
     just schematic."* Say nothing extra for `tiled`.
   - If they want a street map and can't have one, that is the setup check's territory
     (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/setup-check.md`), not a retry.

**The `fuel` question is gone.** Fuel is market-scoped and engine-applied, and nothing in
the contract subtracts it — `temporary_discount` is additive, and a surcharge is not a
discount. The old `waive` already told the CSM the booking needed the waiver applied in
Savoya, so it was never really ours to give; a CSM who needs it waived does that in Savoya
first. The `[if:fuel_surcharge]` terms bullet stays, because it reflects what Core actually
applied.
7. **format** — decides the render step.

## Stage 0 — Machine check (once per conversation, before the first render)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/preflight.py
```
It never fails hard. Exit 0 = everything available; exit 1 = some formats unavailable, and it prints exactly which and how to enable them.

If anything is missing, **say so in one line when it first matters** — not as an error, as a fact: *"PDF output isn't set up on this computer, so I'll give you the document as a web page — open it and Print → Save as PDF and you'll have the identical file. I can note it for IT if you'd like native PDFs."* Then carry on.

**Never show install commands, package managers, or Terminal instructions to the user.** They are salespeople, not engineers; a command they can't run reads as a broken tool. Setup is a one-time IT task documented in `SETUP.md` at the plugin root. If they ask how to fix it, offer to note it for whoever set up their machine. The only technical instruction a CSM should ever get is **Print → Save as PDF**, which is a normal thing to do in a browser — `preflight.py` prints the exact wording for their OS.

Formats and what they need:
| Format | Needs | Without it |
|---|---|---|
| Quote in chat, email copy, HTML | nothing | always works |
| PDF | Chromium (Playwright) or wkhtmltopdf | HTML is produced instead |
| Full verification | poppler (`pdftotext`, `pdfinfo`) | structural checks only — say the document wasn't fully verified |
| Route map | Pillow | skipped |
| Uploaded cover from a PDF | poppler + Pillow | an image file still works |
