# Decision tree — the whole flow

Tool names, required arguments and limits live in **`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/mcp-contract.md`**, which is the contract the regression suite enforces. This file says *when* to call; that file says *what* the call takes.

Every node resolves to **call**, **skip**, or **ask**. **Every "ask" uses `ask_user_input_v0`** (tappable options) unless the answer can't be enumerated — see `../../quote-document/references/asking-questions.md`. Anything not listed is skipped. Nodes A–J are the `quote-intake` skill; K–Q are `quote-document`. The handoff folder is the seam.

---

## Intake

**A · Client** — `resolve_client`
- Name in `~/.savoya-quoting/config.json → known_clients` → **skip**, use the cached profile id.
- Else **call**. One hit → proceed, cache it. Several → **ask** (batched with D). None → **ask** for a name, email, or profile id. Never guess.

**B · Passenger** — `resolve_passengers`
- **Skip unless the user named a passenger.** That is the whole rule. `passenger_id` is optional on every pricing tool, and when it is omitted Core deterministically attaches an eligible passenger to the unsaved calculation.
- User named one → **call**, match the name, send that id. Several matches → **ask** (batched with A and D).
- A profile with no eligible passengers is **not** a case to pre-empt. We don't look, so we can't know in advance; Core raises it and the plugin surfaces it. No estimate fallback, no pre-flight check.
- **No cache.** The old rule — take the first result, cache it per profile — was correct against the previous contract and verified at the time (two passenger ids, byte-identical quotes). Caching now would only keep alive a disclosure the CSM no longer needs to see.

**C · Vehicle types** — **call** `resolve_vehicle_types` once per quote. Core owns `id`, `capacity`, `classification`, `greeter`, `bus`, `limited_availability` and `client_can_book`.
- This reverses an earlier context-budget decision. The static table existed to avoid a per-quote call, and the trade stopped being worth it the moment the table was found **wrong**, not merely stale: it said Exec Van "~10" where Core says **14**, and omitted seven types including both greeters. One call against a wrong answer is not a saving.
- `vehicle-types.md` stays for what Core has no concept of: **physical dimensions** and terminology. Dimensions are what rule a coach out of a venue with a 9×18 ft parking cap.
- `client_can_book: false` (Mini Bus, Coach Bus) is now a field to read rather than a rule to remember.

**D · Stops** — `resolve_itinerary_stops`, always **one call**, every stop from every leg, deduplicated. Decide `stop_type` first: hotel/venue/street → `address`; airport code or flight intent → `airport`; "around the city" → `as_directed` (never as pickup).
- One candidate, or several that are the same place (**same `id` and address**) → proceed, note it. **Both halves matter:** querying "Anaheim Convention Center" returned three candidates all under `id: 4645260` — the venue at 800 W Katella, a Residence Inn at 640, and a Hampton Inn at 100. Matching on `id` alone would have quoted a hotel instead of the venue.
- **Airports: use the IATA code.** "John Wayne Airport, Santa Ana, California" resolved to *nothing* as an airport stop; `"SNA"` resolved first time. Colloquial airport names fail.
- **As-directed city:** query `"<City>, <State spelled out>"` — abbreviations return nothing. Pick the candidate whose `id` matches the pickup's city id. Deterministic, not a guess; ask only if none matches.
- Genuinely different places, or none → **ask**.
- **Every airport stop carries a `flight` object, pickup or drop-off.** Airport as pickup → `flight_type: "arrival"`; as drop-off → `"departure"`. Always `commercial_tbd: true`. Missing flight *time* → placeholder, recorded and disclosed. **Don't ask** — it doesn't change the price. Omitting the object fails the call (`flight is required for airport stops`), and stops[0] on an arrival leg is where it's missed.
- **TBD is the only shape we send, deliberately.** The contract also describes known-commercial flights (needs `airline` as a resolved object with an id) and private ones (needs `fbo` likewise), and **neither resolver exists among the nine tools**. So those two forms are specified and unreachable. Even when the client gives a flight number, keep it as a client-facing note and still send `commercial_tbd: true`. The seam is written down in `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/mcp-contract.md` so that when a resolver lands the next person knows the shape was understood and consciously deferred, not missed.
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
| best or options | `generate_quote_options` | an `options` array, **2–5**, each with its own `key`, `label` and a **complete** `quote_units` list. Usually two: **value** (candidate `vehicle_type_ids`, Core prices each and takes the lowest per unit) and **elevated** (a fixed premium `vehicle_type_id`) |
| you define | `calculate_quote_units` | **one** `vehicle_type_id` per unit — candidate lists are not accepted here |
| user supplied a temporary rate or an extra discount | `calculate_temporary_quote_units` | one `vehicle_type_id` per unit, plus `temporary_rate` (`rate_type`: `hourly` \| `transfer`, `amount` in **cents**) and/or `temporary_discount` (`basis_points`; 500 = 5%). At least one of the two is required. **Never persisted — say so.** |

- **No stored rate in the market** is not a dead end and never an estimate. Core's own
  recovery wording is the flow: **ask the user for a temporary rate, or pick another
  vehicle.** Then re-quote through `calculate_temporary_quote_units`. Say plainly that the
  number came from a rate they supplied, not from Savoya's rate sheet.
- **▲ A temporary rate is a BASE rate — the client's discount comes off it.** Verified
  8 Oct: $250.00/hr supplied became **$192.50/hr** effective after the 30% contracted
  discount and 10% fuel. So when asking, say so: *"this is a base rate before the client's
  contracted discount — give me the rate you want to quote from, not the cost you were
  quoted."* A CSM who enters the partner's cost quotes the client **23% below it**. This is
  the one place that can be caught, because afterwards it just looks like a price.
- **A waiting leg can only take an *hourly* temporary rate.** A `transfer` rate needs
  exactly two stops; sent against a leg with an intermediate stop Core returns
  `quote_units_unavailable` (verified 7 Oct 2026). Our ≲3h out-and-back rule produces that
  shape routinely, so never offer a transfer rate for one.
- **Every option must contain every trip.** Core enforces this: a duplicate option is rejected outright — *"labels alone do not create an alternative."* An option that drops a leg is a cheaper total for a different job.
- **`strategy` is a label, not a lever.** The enum is `value` · `elevated` · `cost_saving` · `quality_focused` · `custom`, and it changes nothing in Core's maths — verified 7 Oct by running the same two options twice with only the strategy strings swapped: identical totals, vehicles, quantities and rate ids. Use it to describe honestly what an option *is*. Never pick a strategy hoping for a different answer; the vehicle argument is the only thing that selects.
- **Send `requested_stop_count` on every unit** — the user's total stop count including pickup, dropoff and every intermediate. It exists so Core can tell it was handed fewer stops than were asked for. Silently dropping a stop is the bug class that produced 0-minute drive times in 0.20.0; this is the server offering to catch it.
- Unit structure was decided at parse time, not here: per-date units; waves as one block; out-and-back as **one hourly unit only when the vehicle waits** (gap ≲ 3h) and as **two transfer units when it's released** (gap ≳ 3h) — price both ways when it's close.
- Core sizes the fleet from `passenger_count` and picks the cheapest candidate **per unit**, so a value option may mix vehicles across legs. That's correct — don't override it. Prefer `passenger_count` and omit `quantity` unless the user fixed a vehicle count.
- **Hours are Core's too.** `duration` is the lever, not the answer: an as-directed stop sent `duration: 2` billed **3.25** hours and `duration: 4` billed **5.25** — a constant +1.25h of positioning. Send what the user asked for, show what Core billed, and say which is which. Never back-solve the duration.

**G2 · Detail card** — after the user picks an option (or accepts the recommendation in best mode), **call** `calculate_quote_units` with that option's chosen vehicle per unit. Identical numbers; it renders the full detail card that `scenario_comparison` shows condensed. **Skip** in define mode — already that shape.

**H · Read the result** — **`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/render_presentation.py <file>`** renders Core's own `presentation` block, which is the CSM-facing view: same layout for every CSM looking at the same quote, and Core's figures printed rather than restated. Exit **3** means the response carried no `presentation` block — fall back to `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize <file> [--select <key>]`, which is still the right tool for the comparison summary and the handoff. Never open the response yourself, and never reword either script's output.
- **It is internal.** The render carries rate ids, rack-versus-effective rates and `limited_availability`. None of that goes in front of a client — `quote.json` and the whole document flow stay ours.
- **If Core's presentation total and its own quote units disagree**, the render says so and prints both. Don't pick one. Re-quote, and if it persists that is a Savoya-side report.
- `presentation.actions` carries intents (`select_scenario`, `refine_quote`). The render names them; **the refine loop at node I is still ours** — the intents are undocumented beyond their names and node I is tested.
- A unit came back `rate_unavailable` for every candidate → **re-quote** that unit with the next class from the table and say what you swapped; if nothing prices, report it as the rate sheet would have.
- **Warnings: the summarizer shows them all, translating the shapes it knows and printing the rest verbatim.** It used to print only the two shapes it recognised and drop the others silently, which hides a real warning as effectively as filtering would. One warning is suppressed — Core's "no passenger was selected" note, and only when the unit priced, because omitting `passenger_id` is now the normal path. A distinct warning is said once per quote, not once per unit per option.
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
