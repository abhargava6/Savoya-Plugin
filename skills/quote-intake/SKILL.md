---
name: quote-intake
description: Turn a client's ground-transportation request into an exact Savoya quote, fast. Use whenever a Savoya ops, sales, or CSM user pastes or forwards a client request — an RFP, an itinerary, "can I get a quote for…", transfers, shuttles, hourly, multi-day, multi-city — or asks "how much for X in Y". This skill resolves the client and stops, asks two short questions, quotes on the exact pricing path (the same numbers the web app shows), presents scenarios, lets the user refine, and writes a handoff the quote-document skill consumes. It does not produce client-facing documents; when the user wants the PDF or email, quote-document takes over.
compatibility: Requires the Savoya MCP connector. Python 3 for the bundled handoff script.
---

# Savoya Quote Intake

Get from a pasted request to a number the user can act on in as few turns as possible, on the **exact** pricing path so the quote matches what the client would see in the web app. `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md` is the authority; this is the walkthrough.

## Where these files live
Every `scripts/`, `references/` and `assets/` path below is written out in full. **Run and read them exactly as written** — a shortened, bare path looks in the user's own folder, not this skill's, and always fails.

`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake` **is this skill's own folder** — the same path as the *Base directory* printed at the top of this skill. If a path errors *No such file or directory*, the prefix didn't expand in this runtime: substitute that Base directory verbatim and carry on. Do it silently; it's plumbing.

**Never guess a path.** `/mnt/skills/plugins/savoya-quoting:quote-intake` and anything else built from the skill's display name does not exist; constructing one wastes a turn and then leaves you improvising. The Base directory header is the only path you need.

Never work around a missing reference by improvising the flow from memory — that is how the rate-sheet step, the display-mode rate table and the final `calculate_quote_units` all get skipped at once. The **Questions** section below is inline precisely so the flow still holds if a reference fails to load.

## Context budget
- One `tool_search` at the start for all five tools: `resolve_client resolve_passengers resolve_itinerary_stops generate_quote_options calculate_quote_units`. Never search per tool.
- Never open a raw engine response to read it — `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize` does that. Save it to a file and summarize.
- Never call `resolve_vehicle_types` unless the user names a type missing from `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/vehicle-types.md`.
- Never call `calculate_quote_options` — it prices a single vehicle only and ignores headcount.
- `plan_approximate_quote_units` is a **fallback only** (see Step 5); its discounts differ from the exact path.

## Step 1 — Parse (no tool call)
Extract a scratch table from the request: client · per-date legs (date, time, pickup, drop, intermediate stops with wait) · headcount per leg · asks (PA, signage, luggage, on-site staff) · anything phrased as two scenarios · anything missing (year, flight time, exact address).

Decide unit structure **here**, with a one-line rationale per unit (it goes in the handoff):
- **Per date when the client thinks per date.** Four origins across three dates → one unit per date, not per origin.
- **Out-and-back: does the vehicle stay, or is it released?** That's the question, not the shape of the words.
  - **Gap ≲ 3 hours → one hourly unit**, three stops, `duration` on the middle stop. The vehicle waits; two transfers would double the minimum. (Boston: 5:45pm out, 8:00pm back — 2.25h wait, one block.)
  - **Gap ≳ 3 hours → two separate transfer units.** The vehicle is released and re-dispatched; nobody waits six hours, and hourly billing across the gap would cost far more. (Irvine: 7:40am out, 2:15pm back — 6.5h apart, two transfers.)
  - **Close to the line?** Price it both ways and show the cheaper, noting the other. The threshold is a heuristic; the rate sheet decides.
- **Continuous shuttle / waves → one hourly block per vehicle**, waves in the label.
- **"Scenario 2" / "or" / "vs" → a separate option** in `generate_quote_options`, never a note.
- **"However many are needed" → omit `quantity`, pass `passenger_count`.** A fixed count ("two coaches") → `quantity`.
- **Anything that would change the quote is a blocking question** — missing year or ambiguous date, headcount given as a range, a location that won't resolve, an unsettled service shape. Ask the user in Step 3 before quoting; never guess a placeholder and never push it into the client document. See `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/client-questions.md`.
- **Every airport stop needs a `flight` object — pickup or drop-off, no exceptions.** The engine rejects the unit otherwise (`flight is required for airport stops`). An arrival leg has the airport as **stops[0]**, and that one is missed most often.

  | The airport is… | `flight_type` | `scheduled_time` |
  |---|---|---|
  | the **pickup** (client landing) | `"arrival"` | the landing time |
  | the **drop-off** (client departing) | `"departure"` | the flight's departure time |

  ```json
  {"stop_type": "airport", "stop_ref": "…",
   "flight": {"flight_type": "arrival", "commercial_tbd": true,
              "scheduled_time": "2027-07-01T08:40:00+01:00"}}
  ```
  Always `commercial_tbd: true` — never an airline or flight number (see below). A missing flight *time* is fine: use a placeholder, record it, disclose it as "flight details to be confirmed". It doesn't change the price.
- **Departure leg with a flight time but no pickup time → compute it and confirm.** Assume **2 hours before departure for domestic, 3 for international**, then ask (one picker, Step 3): the computed domestic time, the international time, or another time. Never quote a guessed pickup silently — it changes billable hours and therefore the price.
- **Flight numbers are not usable yet.** Always send `commercial_tbd: true` with the flight time, even when the client gave an airline and flight number. The engine requires a resolved airline object with an id and there's no tool to resolve one, so a flight number makes the call fail. Keep the number as a client-facing line note ("AA 1234, departing 2:30pm") and tell the user once that it's recorded on the quote but not yet linked to flight tracking.
- **The client's own questions that don't change pricing** (tax, gratuity, cancellation, on-site staff, signage) never block anything — record them with `--client-question` and let the document stage answer them.
- Write the client's message verbatim to `request.md` now.

## Steps 2–8 — the flow

`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md` is the **single source** for what to call, skip and ask at every node (A–J here, K–Q in the document skill). Read it once at the start of a quote; don't re-read it mid-flow. The shape in one paragraph so you know what you're reading:

resolve client + stops in one turn (passenger too, first result, cached) → ambiguities and blocking gaps in one picker → *rate sheet?* → *best / options / define?* → **one** quote call → scripted summary → *which detailed quote?* → refine loop → handoff → *PDF or email?*

## Questions — inline, and not negotiable

**Every question goes out through `ask_user_input_v0` with tappable options, one question per message, and you wait for the answer before the next.** The two failure modes both look fine as you write them: asking in prose, and folding two questions into one sentence ("Which option, and do you want a PDF?"). Both lose the answer. If an answer genuinely can't be enumerated — a client name, an email, a dollar amount — prose is correct; everything below can be enumerated.

| # | When | Question |
|---|---|---|
| 0 | Only if something is genuinely ambiguous | Blocking gaps **and** stop ambiguities, batched into **one** message — missing year, headcount range, a location that didn't resolve, unsettled service shape |
| 1 | **Every quote, no exceptions** | Rate sheet first, or straight to the quote? |
| 2 | **Every quote, no exceptions** | Best value, a few options side by side, or you name the vehicles? |
| 3 | After the scenarios are presented | Which one do you want in detail? |
| 4 | After that | PDF, email copy, or nothing yet? |

1 and 2 are asked on every quote however self-evident the request looks — skipping them is the single most common regression. Client questions that don't change pricing (tax, gratuity, cancellation, on-site staff) are **never** asked and never block: record them with `--client-question` and let the document stage answer them. "go" means no rate sheet, best value.

Three things the tree assumes you already did in Step 1, and won't repeat:
- the unit structure and its rationale,
- `request.md` written verbatim,
- blocking gaps identified (they become the first picker).

Commands, in order:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py client "<name>"        # cached profile id, or nothing
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py passenger <profile_id> # cached passenger, or nothing
# … resolve, ask, quote …
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize scenarios.json --select value
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write --dir handoff … --final
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py capture --dir handoff   # only if they decline a document
```

## What intake never does
Discounts beyond the client's contracted rate, fuel surcharge, covers, personalization, maps, formats, mail. Those are document-flow questions. The number presented is the client's contracted pricing, and the summary says so.
