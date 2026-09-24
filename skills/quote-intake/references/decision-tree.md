# Decision tree — the whole flow

Every node resolves to **call**, **skip**, or **ask**. **Every "ask" uses `ask_user_input_v0`** (tappable options) unless the answer can't be enumerated — see `../../quote-document/references/asking-questions.md`. Anything not listed is skipped. Nodes A–J are the `quote-intake` skill; K–Q are `quote-document`. The handoff folder is the seam.

---

## Intake

**A · Client** — `resolve_client`
- Name in `~/.savoya-quoting/config.json → known_clients` → **skip**, use the cached profile id.
- Else **call**. One hit → proceed, cache it. Several → **ask** (batched with D). None → **ask** for a name, email, or profile id. Never guess.

**B · Passenger** — `resolve_passengers`
- Cached for this profile → **skip**.
- Else **call** and take the **first result without asking**; cache it. The exact tools require a passenger id for the reservation builder, but pricing is passenger-independent (verified: two different passengers, byte-identical quotes) and the name never appears in the response or the widget.
- Profile has no passengers → **fall back** to `plan_approximate_quote_units` at node G, labeled an estimate.

**C · Vehicle types** — static table in `vehicle-types.md`. **Call** `resolve_vehicle_types` only for a type the table lacks (MPV, electric, greeter, an international class).

**D · Stops** — `resolve_itinerary_stops`, always **one call**, every stop from every leg, deduplicated. Decide `stop_type` first: hotel/venue/street → `address`; airport code or flight intent → `airport`; "around the city" → `as_directed` (never as pickup).
- One candidate, or several that are the same place (**same `id` and address**) → proceed, note it.
- **As-directed city:** query `"<City>, <State spelled out>"` — abbreviations return nothing. Pick the candidate whose `id` matches the pickup's city id. Deterministic, not a guess; ask only if none matches.
- Genuinely different places, or none → **ask**.
- **Every airport stop carries a `flight` object, pickup or drop-off.** Airport as pickup → `flight_type: "arrival"`; as drop-off → `"departure"`. Always `commercial_tbd: true`. Missing flight *time* → placeholder, recorded and disclosed. **Don't ask** — it doesn't change the price. Omitting the object fails the call (`flight is required for airport stops`), and stops[0] on an arrival leg is where it's missed.
- All A + D questions go out in **one message**; none if nothing was ambiguous.

**E · Questions, one per message, wait after each** — 1 and 2 are asked on **every** quote, never skipped because the request looks self-evident.
0. **Blocking gaps** — anything that changes the quote: missing year/ambiguous date, headcount range, unresolvable location, unsettled service shape. **Ask** (batched with D's stop ambiguities). Never guess, never defer to the client document. See `client-questions.md`.
1. *Rate sheet first, or straight to the quote?*
2. *Best, options, or you define the vehicles?*

Client questions that don't change pricing (tax, gratuity, cancellation, on-site staff) → **don't ask, don't block**; record with `--client-question` for the document stage.

"go" = no rate sheet, best. Nothing about discount, fuel, or cover here — those are document-flow questions.

**F · Rate sheet** — `preview_rate_batch`, one call, all legs, `display: "show"`.
- E said yes → **call**. E said no → **skip** (node G's response carries every candidate priced, which is the same discovery).
- Later "show me the rate sheet" → call it then; stop refs live ~24h.

**G · Quote** — **one call**, all units

| Condition | Tool | Shape |
|---|---|---|
| best or options | `generate_quote_options` | two options: **value** (candidate `vehicle_type_ids`, Core picks lowest per unit) and **elevated** (premium `vehicle_type_id`) |
| you define | `calculate_quote_units` | one `vehicle_type_id` per unit |
| no passenger on profile · no rates in market · user supplied a temporary rate | `plan_approximate_quote_units` | only tool accepting `custom_rates` / `custom_discount_basis_points`; **say it's an estimate** |

- **Never** `calculate_quote_options` — prices one vehicle, ignores headcount.
- Unit structure was decided at parse time, not here: per-date units; waves as one block; out-and-back as **one hourly unit only when the vehicle waits** (gap ≲ 3h) and as **two transfer units when it's released** (gap ≳ 3h) — price both ways when it's close.
- Core sizes the fleet from `passenger_count` and picks the cheapest candidate **per unit**, so a value option may mix vehicles across legs. That's correct — don't override it.

**G2 · Detail card** — after the user picks an option (or accepts the recommendation in best mode), **call** `calculate_quote_units` with that option's chosen vehicle per unit. Identical numbers; it renders the full detail card that `scenario_comparison` shows condensed. **Skip** in define mode — already that shape.

**H · Read the result** — `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize <file> [--select <key>]` does it. Never open the response yourself.
- A unit came back `rate_unavailable` for every candidate → **re-quote** that unit with the next class from the table and say what you swapped; if nothing prices, report it as the rate sheet would have.
- `special_event`, "No local providers", temporary-rate warnings → say aloud (the summarizer translates them).
- Unquoteable candidates inside a priced unit → shown as `✗`, no action needed.

**I · Refine** — one question: *"Customize this — different vehicles, headcount, hours, another scenario — or is this the one?"*
- A change → back to **G** with the same stop refs. Loop until they say it's final.
- Stop refs older than ~24h → back to **D** first. Never retry a rejected stop ref.

**J · Hand off** — `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write … --final`, then **always ask explicitly** (never assume from context): *"Want the client-facing PDF or email?"*
- Explicit **no** → valid end state. `handoff.py capture` → upload once to the Drive folder. Done.
- **Yes** → document flow. Don't capture here; K–Q captures once at the end.
- No answer → leave it; the handoff stays on disk and "make the PDF" later costs nothing.

---

## Document

**K0 · Machine check** — `preflight.py`, once per conversation before the first render. Exit 1 = some formats unavailable; state it in one plain line when it first matters and carry on. **Never show install commands or Terminal instructions to the user** — CSMs aren't technical, setup is a one-time IT task (`SETUP.md`). The only instruction they get is Print → Save as PDF, worded for their OS.

**K · Read the handoff** — including `client_questions`, which come in three kinds: **boilerplate** (terms block already answers it), **operational** (client-facing line note: arranged separately, not in vehicle pricing), and **data-answered** (pickup times, drive times, vehicle counts — the quote holds the answer implicitly, so surface it as an explicit callout at the top of the PDF and the email). An internal gap must never appear as a client-facing "please confirm".

- `handoff/intake.json` exists and `final: true` → `normalize_quote.py --from-handoff handoff` and **ask nothing about the quote**.
- `final: false` → **stop**: "The quote isn't final yet."
- No handoff (quote from elsewhere) → fallback: save the response, ask which units are chosen, normalize with `--select` / `--alternative`.

**L · Six questions, one per message, driven by the script**
`decide.py --next` prints the next unanswered key and its exact question text; post that and nothing else; record the answer; repeat until `all answered`. Never batch, never skip, never reorder.

1. **discount_pct** — a document-level line. **Never re-quote through the engine.** If the client's contracted discount is already on the quote, the question says this one is additional.
2. **fuel** — quote carries one (`fuel_surcharge_basis_points` > 0) → *keep or take off*; `waive` records that the booking needs the waiver in Savoya. Carries none → *add the 5%?*
3. **cover** — catalog keys with audiences, recommendation first, or their own upload (`--cover-file`).
4. **personalization** — event name, intro note, contact card, logo URL, per-leg notes, closing line; defaults stand for anything unmentioned.
5. **map** — yes → `route_map.py` (drive times already come from the engine; this adds the map image).
6. **format** — PDF · email copy + PDF · HTML · DOCX · XLSX.

**M · Adjust** — `apply_adjustments.py`. Engine-sourced lines (contracted discount, fuel, special handling) are preserved by `--clear` and can't be `--remove`d — only `--waive`d. Document lines apply in order on the running total.

**N · Render** — everything the format needs **before replying**: PDF via `render_print.py`, email text via `draft_email.py`. Read only the one format reference you need.

**N2 · Verify** — `verify_document.py quote.json --pdf out.pdf [--email draft.txt]`, always, before replying.
- **0 PASS** → deliver.
- **1 FAIL** → fix, re-render, verify again. Never deliver a failing document; never hand the failure to the user.
- **2 PARTIAL** → deliver, and say in one line it couldn't be fully verified here and why.
- `render_print.py` exit **3** = no PDF engine on this machine; the HTML is written — deliver it and say so.
- Warnings → read and judge.

**O · Deliver** — one message: email as a copy-ready block, files via `present_files`. No mail connector, no attaching, no sending.

**P · Capture** — **once per conversation**, after the final deliverable. `capture_session.py` (it reads `handoff/intake.json` automatically) → one Drive upload. Load the Drive tool once.

**Q · Feedback — ask, fix, then log.** The reply carrying the first document ends with: *"Anything you'd like changed?"*
- They name something → **fix it first** (adjust → re-render → re-verify → deliver), then capture with `--change` *and* `--fixed`. Say "fixed and logged".
- No, or no answer → capture without them. Don't chase.
Never log a request without acting on it. P (capture) therefore runs **after** any fix, not before.
