---
name: quote-document
description: Turn an existing Savoya quote into a client-facing document — PDF proposal (cover, quote, rate card), email copy, HTML email, Word/DOCX, or Excel — through a fixed sequence of questions (discount, fuel surcharge, cover, personalization, route map, format). Use when a Savoya ops, sales, or CSM user says "make the PDF", "send it to the client", "client version", "make a proposal", "draft the email", "add a discount / take off the fuel surcharge", or "make it pretty" after a quote exists — usually right after the quote-intake skill finishes. This skill does not build quotes from client requests; quote-intake does that.
compatibility: Requires the Savoya MCP connector (resolve_itinerary_stops, preview_rate_batch, calculate_quote_units / calculate_temporary_quote_units) and Python 3 for the bundled scripts. DOCX output uses the docx skill; PDF uses the pdf skill.
---

# Savoya Quote Document

Take what the quoting engine produced, let the user shape it, and hand them something a client can read. Three stages, always in this order:

1. **Gather** — get the engine output into a canonical `quote.json`
2. **Adjust** — engine-native changes go back through the engine; document-level changes layer on top
3. **Render** — one format at a time, from the same `quote.json`

Then close with the feedback check-in (below). The audience for the *document* is a Savoya client. The audience for *this conversation* is a Savoya ops/sales/CSM user who knows the business — talk to them like a colleague, not a customer.

## Context budget
Never put a binary in a tool call — every file reaches the user via `present_files`, every email as chat text; this skill uses no mail connector. Never read back a rendered artifact (print HTML, email, PDF, map, capture). One reference per deliverable. One script call per step; they're deterministic. If a call fails on size, stop — don't retry with another encoding.

## Where these files live
Every `scripts/`, `references/` and `assets/` path below is written out in full. **Run and read them exactly as written** — a shortened, bare path looks in the user's own folder, not this skill's, and always fails.

`${CLAUDE_PLUGIN_ROOT}/skills/quote-document` **is this skill's own folder** — the same path as the *Base directory* printed at the top of this skill. If a path errors *No such file or directory*, the prefix didn't expand in this runtime: substitute that Base directory verbatim (and its sibling `…/skills/quote-intake` for the one cross-skill reference) and carry on. Do it silently; it's plumbing.

**Never guess a path.** `/mnt/skills/plugins/savoya-quoting:quote-document` and anything else built from the skill's display name does not exist. The Base directory header is the only path you need.

Never work around a missing script by hand-building the document or inventing the question sequence — that produces a plausible-looking document with invented numbers. The seven question keys are listed inline in Stage 2 so the flow still holds if a reference fails to load.

## Stage 0 — Machine check (once per conversation, before the first render)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/preflight.py
```
Exit 0 = everything available; exit 1 = some formats unavailable, and it prints which. If anything is missing, say so once in plain terms when it first matters — *"PDF output isn't set up on this computer, so I'll give you the document as a web page — open it and Print → Save as PDF for an identical file."* — then carry on.

**Never show install commands, package managers or Terminal instructions to the user.** Setup is a one-time IT task (`SETUP.md`). The only technical instruction a CSM gets is Print → Save as PDF, worded for their OS by `preflight.py`.

| Format | Needs | Without it |
|---|---|---|
| Quote, email copy, printable document | nothing | always works |
| PDF | Chromium or wkhtmltopdf | the **printable document** instead — same file, they print it |
| Full verification | poppler | structural checks only — say so |
| Route map | Pillow | skipped |

## Stage 1 — Gather

**Normal path: the handoff exists.** `handoff/intake.json` was written by the quote-intake skill. Check it first:
- `final` is false → stop: *"The quote isn't final yet — say when it is and I'll build the document."*
- `final` is true → normalize straight from it and ask **nothing** about the quote:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/normalize_quote.py --from-handoff handoff quote.json --prepared-by "<user>"
  ```
  That reads client, profile, selection, alternatives, and placeholders from `intake.json`, and the engine result from `raw_quote.json`.

**Fallback: no handoff.** The user brought a quote from somewhere else. Save it to `raw_quote.json`, ask which units are chosen vs. alternatives, and normalize with `--select` / `--alternative` (semantics in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/quote-schema.md`).

**Answer the client's carried questions.** `intake.json → client_questions` holds what the client asked that didn't change pricing. Three kinds (`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/client-questions.md`):
- **Boilerplate** (tax, gratuity, cancellation) — the terms block and per-leg cancellation column already answer it. No extra work.
- **Operational** (on-site staff, greeter, signage, PA, luggage vehicle) — a client-facing line note: arranged separately, **not included in the vehicle pricing**.
- **Data-answered** (pickup times, drive times, vehicle counts, how long the vehicle is held) — the quote already contains the answer but only implicitly. **Surface it as an explicit callout** near the top of the first quote page (usually `personalization.intro_note`) *and* near the top of the email, before the line-item breakdown. A client asking "can you suggest pick-up times?" should not have to read sixteen timestamps to find out.

**Never put an internal question in a client document.** A missing year, an unresolved headcount or an ambiguous location was settled during intake; if one somehow reaches here, stop and ask the user — don't write "please confirm the date" into the client's PDF or email. The single exception is a TBD flight, which is a normal client-facing line.

After normalizing, fix any `Stop N` labels (airport stops arrive unlabeled — use the display name from the resolve results) and rewrite leg labels for the client: date, purpose, route.

## Stage 2 — The questions

Six questions, fixed order, **one per message, wait after each**. You don't decide which comes next — the script does:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py --next          # prints "next: <key>" and the exact question text
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py <key> <answer>  # records it, prints the next one
```

Ask what it prints using **`ask_user_input_v0` with tappable options** (labels in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md`), record the answer, repeat until `all answered`. Never ask one of these in prose and never fold two into one sentence — that is what makes the flow skip questions.

The keys, in order, so you can still run the loop if the script or the reference won't load: **discount_pct · fuel · greeter_cost** *(only when the client asked for a greeter or on-site staff)* **· cover · personalization · map · format**.

**If the user has already said which format they want — "just draft the email", "send me the spreadsheet" — record it first: `decide.py format <value>`.** Only the PDF and the printable document use a cover page or a route map, so once the format is known the script stops asking about them. Asking a CSM to pick a cover for an email is not a neutral extra question, and answering the map question costs 10–20 seconds of routing for a field the email never reads.

**Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/questions.md` now** — it says what each answer does, and it's the only place those details live.

## Stage 3 — Adjust (mechanics)

Two kinds of change, and they're handled differently because they *are* different:

**Engine-applied** — a discount or custom rate the engine already applied (the normalizer shows the standard rate on the line and a "Preferred client discount (N%)" line marked `source: engine`). Never re-quote from the document flow; the quote is final when it reaches here. Don't `--remove` engine lines — `--clear` preserves them on purpose.

**Document-level** — fuel surcharge, special handling, greeter fees, parking estimates, anything the engine has no concept of. These live in `quote.json` under `adjustments` and are applied by `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/apply_adjustments.py`. The engine subtotal is never mutated; the document shows *engine subtotal → adjustments → total*.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/apply_adjustments.py quote.json \
  --add "Fuel surcharge|percent|5" \
  --add "Special handling — event coordinator on site|flat|150|9/16 offsite"
```

Format is `label|percent or flat|amount|optional applies-to leg key`. Negative values are discounts. Adjustments apply **in list order on the running total** — a 25% group discount followed by a 5% fuel surcharge computes the surcharge on the *discounted* amount. That's how Savoya bills (the CSM-built reference quote does exactly this), so always add the discount before the surcharge.

Two discounts can coexist: the profile's contracted discount lives in the engine rate (you'll see `effective_rate_amount` already reduced), and a deal-specific group discount is a document-level percent line. Don't collapse them — the rate card shows the standard rate and the net rate, and the client should be able to see the group discount as its own line.

**Fuel surcharge specifically.** Three states, all handled by the scripts:
- *Engine applied it* → the normalizer surfaces it as an engine-sourced line. If the user wants it off the client document, `apply_adjustments.py --waive "Fuel surcharge"` — the line disappears, the terms bullet disappears, and a note is recorded that the engine total still includes it and the booking needs the waiver applied in Savoya. Tell the user that last part; it's the one that bites at invoicing.
- *Engine didn't, user wants it* → `--add "Fuel surcharge|percent|5"` (after any discount line, since it compounds on the discounted amount).
- *Neither* → no line, and the terms bullet about the 5% surcharge is omitted automatically. The terms adapt; you don't edit them.
Ask about it in the post-rate-sheet question above; never add or omit it silently.

**Cover page** — the PDF opens with one of Savoya's audience covers (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/covers/catalog.json`): general, executive-assistants, event-planners, high-demand-events, security-teams, flight-departments, athletic-recruiters, or `custom` (generated, for a hosted hero image). Ask which fits the buyer — in one line, with your recommendation first: *"This reads like an events planner — go with the Meetings & Events cover, or would you rather General?"* Infer from the request (an EA booking one exec → executive-assistants; a 120-person offsite → event-planners; FBO pickup → flight-departments). Default to general only if they don't care. Set `personalization.cover` to the key.

**Personalization** — set from the one question above; defaults if unmentioned. `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/personalization.md` has the menu and rules (hosted URLs only, what a good intro note looks like, where each element lands). The route map (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/route_map.py`) needs internet, adds ~10–20s, and skips itself if a service is down — no map at all rather than a blank panel.

**Drive times come from the engine, not the map.** `travel_times` on the quote is Savoya's own number and the one the web app shows; the map's router only supplies distance and the drawn line. If a leg has no drive time, the map couldn't resolve every stop on it — say the drive time isn't available for that leg rather than quoting a routed guess, which understates any leg whose middle stop was lost.

## Stage 4 — Render

Ask which format if the user hasn't said. Default to **PDF** for "proposal", "quote for the client", "send them the quote". When they say "draft the email", "write the email", or name a recipient, that is a stated format: record `format = email`, deliver the email copy, and **offer** the PDF in one line at the end rather than building one they didn't ask for — the old default quietly attached a PDF, which is also what made the cover and route-map questions look justified. HTML email only when they explicitly want a designed HTML message. Everything is delivered in the chat: text as a copy-ready block, files via `present_files`. This skill never creates drafts, attaches, or sends through a mail connector.

| Format | Read first | Notes |
|---|---|---|
| PDF (default) | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-print.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_print.py quote.json out.pdf [--cover key]` — audience cover page, quote page (hero total, refs, line notes, breakdown), rate card page (standard vs net, cancellation table, terms). Light print theme. |
| Email copy | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-print.md` § Email copy + `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/README.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/draft_email.py quote.json --json draft.json` gives the house structure (per-leg quote block, cancellation note, inclusions). Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/README.md` and two samples — one Robyn, one Julia — then adjust the opener, recommendation sentence, and closer to match; keep the numbers block exactly. Then put the finished email **in the chat** as a copy-ready block (subject line, blank line, body) and hand the PDF over with `present_files` in the same reply. That's the whole deliverable: the user copies the text into their own mail client and drags the PDF in. Do not create drafts in Gmail/Outlook, do not attach anything, do not send. |
| HTML email | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-html.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_html.py quote.json out.html` — dark brand theme, quote inline, email-safe |
| DOCX | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-docx.md` + the docx skill | For clients who need to edit; same page plan as the PDF |
| XLSX | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-xlsx.md` + the xlsx skill | Line-item sheet with live formulas for adjustments |

Before rendering anything, read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/client-safe-rules.md`. It is the translation table from engine vocabulary to client vocabulary, and it decides what must be shown (special-event pricing, cancellation windows, minimums, TBD flights) and what must never be shown (rate ids, market inventory counts, "hourly fallback" warnings). The scripts apply most of it, but DOCX and XLSX are assembled by hand and it's easy to leak an internal field.

The terms block is fixed text in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/terms.md`. Every rendered document includes it verbatim. The last bullet ("This is a quoting tool…") is not optional — it's what keeps a quote from becoming a promise.

## Stage 5 — Verify before delivering

Every rendered deliverable goes through the checker first — it has caught dropped legs, missing dates, unlabeled stops and terms/fuel mismatches:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/verify_document.py quote.json --pdf out.pdf [--email draft.txt]
```

Exit codes: **0 PASS** → deliver. **1 FAIL** → fix, re-render, verify again; never deliver a failing document and never describe the failure as the user's problem. **2 PARTIAL** → deliver, but say in one line that it couldn't be fully verified on this machine and why. Warnings are judgement calls; read them and decide.

The checker reconciles totals against `quote.json`, confirms every leg's reference and line total actually appear in the PDF (page overflow silently drops legs), requires the terms block, keeps the fuel bullet and the fuel line in sync, flags TBD flights that aren't disclosed, and refuses internal vocabulary.

## What the document always contains

- Client name, prepared-by, travel coordinator, service area, passenger count, date prepared, validity note, and the discount / fuel-surcharge percentages when present
- A hero estimated total near the top — the client should not have to scroll to the bottom to find the number
- Line references (A1, A2 …) so the client and the CSM can talk about "A3" instead of "the second bus thing"
- Every leg: date/time, pickup → drop-off (with intermediate stops), passenger count, vehicle × quantity, pricing basis (hourly hours × rate with minimum, or transfer), cancellation window, per-leg total
- Any special-event pricing, called out visibly on the affected leg
- Any TBD flight, marked as to-be-confirmed
- Engine subtotal, each adjustment as its own line (in billing order), total
- A rate card: every vehicle type used, standard rate and net rate (after global discount and surcharge), minimum, minimum total, cancellation notice
- Line notes per reference when there's anything operational to say (staging, waves, continuous-charter rationale, distance/duration)
- Personalization elements the user chose
- Terms, verbatim — except the fuel-surcharge bullet, which appears only when a fuel line is on the quote
- If the user asked for it: drive time per leg and a route-overview page with a map

## Capture — once, at the end

Twice, and the first one is not optional:

1. **The moment a document is verified and delivered** — `capture_session.py … --auto`, plus `--workaround "…"` if you did anything outside the documented path. Upload the one file it lists. Silent; say nothing to the user. A session that ends right here is then still on record, which is the only reason we ever hear about a document that went out wrong.
2. **After the feedback exchange** — re-run for the same slug with `--worked` / `--change` / `--fixed`.

**Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`** for the flags, the size rule, and the ask → fix → log sequence. `--change` is the user's words; your own notes go in `--workaround`.

## Hard-won rules

All in `RULES.md` — read it before rendering; it's short. The dated history is in `feedback-archive.md` (weekly pass only).
