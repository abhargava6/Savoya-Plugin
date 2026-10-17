---
name: quote-document
description: Turn an existing Savoya quote into a client-facing document — PDF proposal (cover, quote, rate card), email copy, HTML email, Word/DOCX, or Excel — through a fixed sequence of questions (discount, cover, personalization, route map, format). Use when a Savoya ops, sales, or CSM user says "make the PDF", "send it to the client", "client version", "make a proposal", "draft the email", "add a discount", or "make it pretty" after a quote exists — usually right after the quote-intake skill finishes. Also use it when someone asks whether their setup is working — "check my quoting setup", "is this saving?", "why isn't anything showing up?" — which runs the setup check. This skill does not build quotes from client requests; quote-intake does that.
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

**If you must find this folder by hand, take the newest copy — never a bare name match.**
More than one build of this plugin can be installed at once: an upload whose name collides
is unpacked beside the old one as `savoya-quoting~g2`, `~g3`, and so on, and **every older
copy stays on disk**. So a glob on the plain name matches the *oldest* directory and
nothing else:

```bash
# WRONG — matches only the oldest copy, whatever its version
ls ~/.claude/plugins/synced/*/savoya-quoting/skills

# RIGHT — the highest version wins
python3 - <<'PY'
import glob, json, os, re
def key(p):
    # numeric, not lexical: "0.9" sorts above "0.25" as a string
    v = json.load(open(p)).get("version", "")
    return [int(n) for n in re.findall(r"\d+", v)]
best = max((p for p in glob.glob(os.path.expanduser(
               "~/.claude/plugins/synced/*/savoya-quoting*/.claude-plugin/plugin.json"))
            if ".trash" not in p), key=key, default=None)
print(os.path.dirname(os.path.dirname(best)) if best else "not found")
PY
```

This is not hypothetical. On 10 Oct 2026 two uploads were installed — 0.19.1 from
September and 0.25.0-sourcing.1 — and the bare-name glob reached the September one. The
instructions still came from the current copy, so the flow looked right, but a session
that located a *script* that way ran September's: its `capture_session.py` has no `--auto`
flag at all and requires `--request`, so the capture call was rejected with bare argparse
usage and the session recorded nothing. Prefer the Base directory header over any of
this; it is already correct.


Never work around a missing script by hand-building the document or inventing the question sequence — that produces a plausible-looking document with invented numbers. The question keys are listed inline in Stage 2 so the flow still holds if a reference fails to load.

## Stage 0 — Machine check (once per conversation, before the first render)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/preflight.py
```
Exit 0 = everything available; exit 1 = some formats unavailable, and it prints which. If anything is missing, say so once in plain terms when it first matters — *"PDF output isn't set up on this computer, so I'll give you the document as a web page — open it and Print → Save as PDF for an identical file."* — then carry on.

**Never show install commands, package managers or Terminal instructions to the user.** Setup is a one-time IT task (`SETUP.md`). The only technical instruction a CSM gets is Print → Save as PDF, worded for their OS by `preflight.py`.

**Load the Drive tool now, in this same stage** — `tool_search "Google Drive create_file"` — not later at the capture step. It is needed only at the end, which is exactly why it has to be loaded here: the capture runs after delivery, when the session is winding down and one more setup step is the easiest thing in the flow to skip. Three live sessions in a row ended with the capture written locally and never uploaded, one of them saying plainly *"I didn't upload it because it needs the Google Drive connector, which I hadn't loaded."* If the search returns nothing, Drive isn't connected — carry on, and the capture step has a line for that.

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

**If `handoff/blocked.json` exists, the handoff write was refused (R92).** `normalize_quote.py` and `decide.py` stop and print the gate, the reason and the fix. Do what the fix says and run the write again, or tell the user why you cannot go on and report the session (`capture_session.py --blocked`). This is not the "no handoff" fallback below: never build `intake.json` or the decisions by hand, and never call the scripts' internals, to get past a refusal.

**Fallback: no handoff.** The user brought a quote from somewhere else. Save it to `raw_quote.json`, ask which units are chosen vs. alternatives, and normalize with `--select` / `--alternative` (semantics in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/quote-schema.md`).

**Answer the client's carried questions.** `intake.json → client_questions` holds what the client asked that didn't change pricing. Three kinds (`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/client-questions.md`):
- **Boilerplate** (tax, gratuity, cancellation) — the terms block and per-leg cancellation column already answer it. No extra work.
- **Operational** (signage, PA, luggage vehicle) — carried into `client_requests` by `normalize_quote.py` and shown as one neutral line near the top ("We've noted your requests (…) and will confirm each with you"). **Never write that it is included, excluded or arranged separately**: you do not know (R73). The answer is confirmed with the user before send (R72).
- **On-site staff / greeter** is no longer in that group: Core prices it as a quote unit (vehicle types 12 and 13). See node G3 in `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md`. Only a market with no greeter rate falls back to a flat line or a note.
- **Data-answered** (pickup times, drive times, vehicle counts, how long the vehicle is held) — the quote already contains the answer but only implicitly. **Surface it as an explicit callout** near the top of the first quote page (usually `personalization.intro_note`) *and* near the top of the email, before the line-item breakdown. A client asking "can you suggest pick-up times?" should not have to read sixteen timestamps to find out.

**Never put an internal question in a client document.** A missing year, an unresolved headcount or an ambiguous location was settled during intake; if one somehow reaches here, stop and ask the user — don't write "please confirm the date" into the client's PDF or email. The single exception is a TBD flight, which is a normal client-facing line.

After normalizing, fix any `Stop N` labels (airport stops arrive unlabeled — use the display name from the resolve results) and rewrite leg labels for the client: date, purpose, route.

## Stage 2 — The questions

Five questions, fixed order, **one per message, wait after each**. You don't decide which comes next — the script does:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py --next          # prints "next: <key>" and the exact question text
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py <key> <answer>  # records it, prints the next one
```

Ask what it prints using **`ask_user_input_v0` with tappable options** (labels in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md`), record the answer, repeat until `all answered`. Never ask one of these in prose and never fold two into one sentence — that is what makes the flow skip questions.

The keys, in order, so you can still run the loop if the script or the reference won't load: **discount_pct · greeter_cost** *(only when the client asked for a greeter or on-site staff)* **· commission_pct · cover · personalization · map · format**. There is no `fuel` key — fuel is Core's and not adjustable here.

**Deliver exactly the format the user chose (R85).** `verify_document.py` prints a `DELIVERABLES:` line from the recorded decision. If it says PDF only, do **not** run `draft_email.py` (it refuses) and do not write or paste an email; after delivering, offer one in a single line. Run it with `--asked` only when the user has since asked for an email.

**When the flow cannot produce a document (R80):** run `capture_session.py --blocked` as `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md` describes, so the failure is still reported.

**Capture consent (R76):** if verify prints `CAPTURE CONSENT UNASKED`, follow `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md` before presenting the files.

**commission_pct** is the one that changes no totals. *"Does this client get a commission on this quote? No, 1%, 5%, or another percentage."* Record it with `apply_adjustments.py quote.json --commission-pct <pct|none>`, which also rebuilds the terms so the rate and its bullet cannot get out of step. It never enters `adjustments` and the total is identical with it and without it. `apply_adjustments.py` also computes the amount per option — the subtotal after every discount, before fuel, times the rate, rounded half-up — and states it as *"A 5% commission applies to this program, calculated after discounts and before the fuel surcharge: $600.50 on Option A, $728.61 on Option B."* **Never work the amount out yourself or edit one into `quote.json`**; re-run the script. It names no beneficiary, because the commission may be the client's or an agency's. Once recorded it appears in a hero line under each option total in the PDF (smaller than the total, same on every option), in the terms list (which is how the HTML email gets it), and as one flat sentence in the email copy. **Keep it flat in the email** — it moves the needle sometimes, but the client is reading a quote, not an offer.

**If the user has already said which format they want — "just draft the email", "send me the spreadsheet" — record it first: `decide.py format <value>`.** Only the PDF and the printable document use a cover page or a route map, so once the format is known the script stops asking about them. Asking a CSM to pick a cover for an email is not a neutral extra question, and answering the map question costs 10–20 seconds of routing for a field the email never reads.

**Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/questions.md` now** — it says what each answer does, and it's the only place those details live.

## Stage 3 — Adjust (mechanics)

Two kinds of change, and they're handled differently because they *are* different:

**Engine-applied** — a discount or custom rate the engine already applied (the normalizer shows the standard rate on the line and a "Preferred client discount (N%)" line marked `source: engine`). Leave it alone: the *contracted* discount and the fuel surcharge are settled, and the quote is final when it reaches here. Don't `--remove` engine lines — `--clear` preserves them on purpose. (An **additional** discount is a different thing and does go back to Core — see below.)

**Document-level** — only **flat amounts**, for things Core genuinely cannot price: a fallback on-site cost in a market with no greeter rate, a parking estimate. These live in `quote.json` under `adjustments` and are applied by `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/apply_adjustments.py`, which **refuses a document percentage line**. Percentages are Core's: an additional discount is a re-quote through `calculate_temporary_quote_units`, fuel is market-scoped and engine-applied, and a greeter is a priced Core unit. The engine subtotal is never mutated; the document shows *standard → discount → net → any flat line → total*, and refuses to render if the total doesn't match Savoya's.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/apply_adjustments.py quote.json \
  --add "Special handling — event coordinator on site|flat|150|9/16 offsite"
```

Format is `label|flat|amount|optional applies-to leg key`. **Flat only** — a `percent` line here is refused (C2), whatever it is for, so do not write one and do not expect one to work. Flat lines apply in list order on the running total.

Two discounts can coexist, but **neither of them is a document line**: the profile's contracted discount lives in the engine rate (`effective_rate_amount` arrives already reduced), and a deal-specific one is a **Core re-quote** through `calculate_temporary_quote_units` with `temporary_discount.basis_points`. Both then come back as engine lines carrying Core's own amounts, and the rate card shows standard and net. Don't collapse them, and don't recreate either as a percentage here.

**Fuel surcharge.** Market-scoped and engine-applied — 5% in most markets, 10% in London and others — so read it from the quote and never hardcode it. **There is no fuel question**: it was removed on 7 Oct (C3), because nothing in the contract subtracts a surcharge and `temporary_discount` is additive rather than a way to remove one. The `[if:fuel_surcharge]` terms bullet appears only when a live fuel line exists and states the engine's percentage; the terms adapt and you don't edit them.

If a CSM wants it off a client document, the answer is that **they waive it in Savoya first and you re-quote** — it was never ours to give, and waiving it only here leaves the booking still charging it. `--waive "Fuel surcharge"` exists for that case and records the discrepancy, but **don't offer it.** Use it only if they ask directly after hearing the Savoya route, and tell them the engine total still includes it; that is the part that bites at invoicing.

**Cover page** — the PDF opens with one of Savoya's audience covers (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/covers/catalog.json`): general, executive-assistants, event-planners, high-demand-events, security-teams, flight-departments, athletic-recruiters, or `custom` (generated, for a hosted hero image). Ask which fits the buyer — in one line, with your recommendation first: *"This reads like an events planner — go with the Meetings & Events cover, or would you rather General?"* Infer from the request (an EA booking one exec → executive-assistants; a 120-person offsite → event-planners; FBO pickup → flight-departments). Default to general only if they don't care. Set `personalization.cover` to the key.

**Personalization** — set from the one question above; defaults if unmentioned. **Write it with the setter, never by editing `quote.json`:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/set_personalization.py quote.json \
  --event-name "…" --intro-note "…" [--cover KEY] [--am-name "…"] [--closing-note "…"]
```

`decide.py` records the answer in the handoff; it does not reach the document on its own, and before the setter existed every session hand-edited `quote.json` to get it there. That is also how a wrong claim got into a client PDF — an intro note asserting tax and gratuity were included, contradicting the terms on its own final page. The setter refuses the contradictions it can recognise, so if it rejects a note, the note is wrong, not the check.

`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/personalization.md` has the menu and rules (hosted URLs only, what a good intro note looks like, where each element lands). The route map (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/route_map.py`) needs internet, adds ~10–20s, and skips itself if a service is down — no map at all rather than a blank panel.

**Drive times come from the engine, not the map.** `travel_times` on the quote is Savoya's own number and the one the web app shows; the map's router only supplies distance and the drawn line. If a leg has no drive time, the map couldn't resolve every stop on it — say the drive time isn't available for that leg rather than quoting a routed guess, which understates any leg whose middle stop was lost.

## Stage 4 — Render

Ask which format if the user hasn't said. Default to **PDF** for "proposal", "quote for the client", "send them the quote". When they say "draft the email", "write the email", or name a recipient, that is a stated format: record `format = email`, deliver the email copy, and **offer** the PDF in one line at the end rather than building one they didn't ask for — the old default quietly attached a PDF, which is also what made the cover and route-map questions look justified. HTML email only when they explicitly want a designed HTML message. Everything is delivered in the chat: text as a copy-ready block, files via `present_files`. This skill never creates drafts, attaches, or sends through a mail connector.

| Format | Read first | Notes |
|---|---|---|
| PDF (default) | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-print.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_print.py quote.json out.pdf [--cover key]` — audience cover page, quote page (hero total, refs, line notes, breakdown), rate card page (standard vs net, cancellation table, terms). Light print theme. |
| Email copy | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-print.md` § Email copy + `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/README.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/draft_email.py quote.json --json draft.json` gives the house structure (per-leg quote block, cancellation note, inclusions). Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/README.md` and two samples — one Robyn, one Julia — then adjust the opener, recommendation sentence, and closer to match; keep the numbers block exactly. Then put **both** finished emails **in the chat** as labelled copy-ready blocks, "Full" and "Short" (subject line, blank line, body each; the script prints both). Adjust only the wording around the numbers in each and hand the PDF over with `present_files` in the same reply. That's the whole deliverable: the user copies the text into their own mail client and drags the PDF in. Do not create drafts in Gmail/Outlook, do not attach anything, do not send. |
| HTML email | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-html.md` | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_html.py quote.json out.html` — dark brand theme, quote inline, email-safe |
| DOCX | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-docx.md` + the docx skill | For clients who need to edit; same page plan as the PDF |
| XLSX | `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-xlsx.md` + the xlsx skill | Line-item sheet with live formulas for adjustments |

Before rendering anything, read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/client-safe-rules.md`. It is the translation table from engine vocabulary to client vocabulary, and it decides what must be shown (special-event pricing, cancellation windows, minimums, TBD flights) and what must never be shown (rate ids, market inventory counts, "hourly fallback" warnings). The scripts apply most of it, but DOCX and XLSX are assembled by hand and it's easy to leak an internal field.

The terms block is fixed text in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/terms.md`. Every rendered document includes it verbatim. The last bullet ("This is a quoting tool…") is not optional — it's what keeps a quote from becoming a promise.

## Stage 5 — Verify before delivering

Every rendered deliverable goes through the checker first — it has caught dropped legs, missing dates, unlabeled stops and terms/fuel mismatches:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/verify_document.py quote.json --pdf out.pdf [--email draft.txt] --capture-slug "<client>-<event>" --capture-client "<Client>"
```

Exit codes: **0 PASS** → deliver. **1 FAIL** → fix, re-render, verify again; never deliver a failing document and never describe the failure as the user's problem. **2 PARTIAL** → deliver, but say in one line that it couldn't be fully verified on this machine and why. Warnings are judgement calls; read them and decide.

The checker reconciles totals against `quote.json`, confirms every leg's reference and line total actually appear in the PDF (page overflow silently drops legs), requires the terms block, keeps the fuel bullet and the fuel line in sync, flags TBD flights that aren't disclosed, and refuses internal vocabulary.

## Stage 5b — Confirm before send (R72)

After verification passes and before you present the files, list what the user must confirm:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/confirm_items.py "$OUT/quote.json" --json
```

Ask **one `ask_user_input_v0` question per item** with `Right` / `Wrong` options, one per message. The service-area placeholders arrive grouped as one item. It is a gate only: nothing from the answer is written into the document. On `Wrong`, stop, ask for the corrected value, fix it at the source (intake or the adjustment script), and re-render. An empty list means skip this stage. Do not present the files to the user until every item is answered `Right`.

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

## Setup check

Someone asking *"is this working?"*, *"why isn't my stuff saving?"*, or *"check my quoting
setup"* gets this, and so does anyone whose name isn't recorded yet, once:
**`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/setup-check.md`**.

It matters more than it looks. A CSM could finish setup, believe they were done, and quote
for weeks while nothing reached the shared folder — because every way the capture has of
reporting a problem happens *after* the capture runs. The check calls the connectors
instead of assuming them, including writing a small test entry to the folder, because a
Drive connector that is switched on but lacks Editor on the folder looks identical to one
that works.

## Capture — once, at the end

Twice, and the first one is not optional (R63: the user never has to ask for it):

1. **At verification, before delivery** — `verify_document.py … --capture-slug …` writes the snapshot (`capture_session.py --auto`) on a pass and leaves a `.pending-upload` marker. Upload **both** files it lists, then run `capture_session.py --mark-uploaded <slug> --file-id <id>`, and only then present the files. Add `--workaround "…"` (re-run `capture_session.py … --auto --workaround`) if you did anything outside the documented path. Silent; say nothing to the user.

   **The delivery reply, in this order:** verify with `--capture-slug` → upload both capture files → `--mark-uploaded` → present the PDF and both emails → end with "Anything you'd like changed?". **First rule of every later turn:** if any `.pending-upload` marker exists (`setup_check.py` counts them), upload it before anything else. A marker in a cloud container is lost when the container is reclaimed, so do not defer the upload. A session that ends right here is then still on record, which is the only reason we ever hear about a document that went out wrong.

**Capture hardest when the session went worst.** If you patched a renderer in a working copy, rebuilt a line by hand, or worked around anything, that session is the single most valuable one of the week — and it is the one most likely to skip this step while firefighting. Run it anyway, put what you did in `--workaround`, and upload. A bug you only mention in chat reaches nobody: the user is not the maintainer, and the chat is not a channel.

**The plugin being read-only does not mean feedback is.** `${CLAUDE_PLUGIN_ROOT}` is a build artifact and you must never edit it — that is true and unrelated. The capture writes to `~/.savoya-quoting/captures/` and uploads to a shared Drive folder, neither of which is the plugin. Never conclude from "I can't edit the skill" that there is nowhere to report.

**It is built so it cannot fail on you.** `--request` is optional, a missing handoff is recorded rather than fatal, and an unexpected error still writes a failure record and exits 0. So there is no input bad enough to justify skipping it.
2. **After the feedback exchange** — re-run for the same slug with `--worked` / `--change` / `--fixed`.

**Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`** for the flags, the size rule, and the ask → fix → log sequence. `--change` is the user's words; your own notes go in `--workaround`.

## Hard-won rules

All in `RULES.md` — read it before rendering; it's short. The dated history is in `feedback-archive.md` (weekly pass only).


## Questions about how this works, and "log this session" (R87, R90)

**"How does this work?", "what can't it do?", "why did it ask that?"** Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/help.md` and answer from it, in your own words, for the user's question only. If its frontmatter has a `page_url`, give that link when they want the whole picture. If the file does not answer the question, say so; do not answer from memory. Never state a price in an answer.

**"Log this session"** (or "report a problem", "save this session"), at any point in the conversation: the user is asking for the session record, with or without a document. Follow the capture consent rules in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`. If a document has been delivered, run the normal capture with `--change "<their words>"`. If not, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py --blocked "user-requested: <their words>" --slug <slug> --client "<Client>" --request handoff/request.md`, upload the file it lists, then `--mark-uploaded`. Reply in one line that it is saved, and tell them to post a short note in the core-ideas Slack channel so someone picks it up. A user asking for this is asking for the record; do not talk them out of it.
