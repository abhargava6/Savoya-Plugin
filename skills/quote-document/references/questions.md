# The document questions

Loaded at Stage 2. `decide.py --next` drives the order; option labels are in `asking-questions.md`.

Six questions, fixed order, **one per message, wait after each**. Don't decide which to ask — the script does:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py --next          # prints "next: <key>" and the exact question text
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py <key> <answer>  # records it, prints the next one
```

Loop: run `--next` → ask its question with **`ask_user_input_v0`** (tappable options — see `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md` for the labels; never bare prose) → wait → record the answer → run `--next` again → until it prints `all answered`. This is what makes the flow consistent: you never skip a question the script lists, never merge two, never ask one it has already marked answered. **The script decides which questions apply** — if the user has already said what they want ("just the email"), record `format` first and `--next` drops the cover and route-map questions, because nothing but the PDF and the printable document reads those answers. If the user answers several at once ("no discount, add fuel, PDF"), record each key in turn and still confirm the ones they didn't mention by asking them.

What each answer does:
1. **discount_pct** — a **document-level line**, applied by `apply_adjustments.py --add "Preferred client discount|percent|-<N>"`. **Do not re-quote through the engine.** If the engine already applied a discount (it shows as an engine-sourced line), this is additional and the question says so.
2. **fuel** — `keep` (nothing), `waive` (`--waive "Fuel surcharge"`, and tell them the booking needs the waiver in Savoya), `add` (`--add "Fuel surcharge|percent|5"`, after the discount line), `none`.
3. **greeter_cost** *(only when the client asked for a greeter or on-site staff — the script inserts it)* — an amount becomes a document line: `apply_adjustments.py --add "On-site coordinator|flat|<amount>"`, and the email names it. No amount → a client-facing line note that it's arranged separately and not included in the vehicle pricing.
4. **cover** — a catalog key, or a path to their upload → `render_print.py --cover-file`.
5. **personalization** — set `personalization.*` from the answer; defaults stand for anything not mentioned.
6. **map** — `true` → run `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/route_map.py quote.json` before rendering.
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
