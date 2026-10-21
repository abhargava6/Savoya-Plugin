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


Never work around a missing reference by improvising the flow from memory — that is how the rate-sheet step, the display-mode rate table and the final `calculate_quote_units` all get skipped at once. The **Questions** section below is inline precisely so the flow still holds if a reference fails to load.

## Context budget
- One `tool_search` at the start for the five tools a quote actually uses: `resolve_client resolve_itinerary_stops resolve_vehicle_types generate_quote_options calculate_quote_units`. Never search per tool.
- **Cross-market sourcing adds three more**, searched only when node F2 fires: `resolve_service_areas lookup_nearby_markets calculate_sourced_quote_units`. Most quotes never need them, so they stay out of the opening search.
- **After every `lookup_nearby_markets` call, ask ONE `ask_user_input_v0` call with two questions**, so the follow-up choices page in the picker with no second turn. **Page 1:** one ready-made split per **newly listed** market that covers the gap alone, nearest first, at most three (`3 Orange County + 2 Los Angeles`), then `None of these`; with no vehicle count, or a primary market that is not short, name the new markets instead; leave page 1 out when no new market covers the gap alone. **Page 2:** `Use my choice above` (only with page 1) · `Show 3 more markets` (while fewer than twelve have been shown) · `Split differently` · `Override <primary> inventory` (only when the primary market is short). A page-2 answer other than `Use my choice above` wins. Never offer a market from an earlier lookup as its own option, never put more than four options on a page, and never mark one as recommended.
- `resolve_passengers` is **not** in that set — load it only when the user named a passenger, which is the only time we call it.
- Never open a raw engine response to read it. Save it to a file, then run `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/render_presentation.py` — it renders Core's own `presentation` block, which is what a CSM should see. Exit 3 means there was no such block; fall back to `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize`. Post the output as-is; rewording it is the drift this replaced.
- **Call `resolve_vehicle_types` once per quote.** Core owns ids, capacity, `greeter`, `bus`,
  `limited_availability` and `client_can_book`. The old rule skipped the call to save
  context; the static table it relied on turned out to be wrong, not just stale (Exec Van
  14, not "~10", and seven types missing). `vehicle-types.md` now holds only physical
  dimensions and our candidate policy.
- `calculate_temporary_quote_units` is **not** in the opening search — load it only when the
  user actually supplies a temporary rate or an extra discount, which is rare. It is the
  only tool that accepts them, and the result is never persisted.

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
- **Spell out the state or province in every stop lookup, and record each one (R83).** An as-directed stop is queried as `"Whistler, British Columbia"`, never `"Whistler, BC"` (abbreviations return nothing) and pick the candidate whose `id` matches the pickup's city. Pass every lookup to `handoff.py write` as `--stop-note "<stop>|<query sent>|resolved"` or `…|unresolved`. **If a stop is unresolved, stop and ask the user for an address.** Never substitute another stop (a Westin round trip for an as-directed tour), never delete a travel time or stop to get past verify. `write` refuses an unresolved note.
- **A headcount range is never priced on a default (R84).** "50–75 passengers" means ask which number to quote, *before* pricing, as question 0. Then price each vehicle group with its own share of that number — 75 as 50 on the coach and 25 on the vans — and pass `--headcount 75` to `handoff.py write`. It refuses a ranged request without it, refuses a unit with no `passenger_count`, and refuses groups serving one trip whose counts do not add up to the headcount (R91). Never put the full headcount on every group: Core sizes the number of vehicles from each group's count, so 75 on a coach and 75 on two vans prices extra vehicles. Capacity must follow the headcount, never one vehicle's seats.
- **When a write is refused, stop (R92).** `handoff.py write` prints the gate, the reason and the fix, and leaves `handoff/blocked.json`. Fix the cause and write again, or tell the user why you cannot go on. Never build `intake.json`, keep decisions by hand, or call the scripts' internals to get past it; `decide.py` and `normalize_quote.py` refuse to run while `blocked.json` exists. If you cannot fix it, run the blocked capture (`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`) so the session is reported.
- **State your reading of every scenario and get a yes before pricing (R81).** One line per scenario: vehicles and counts, hours, headcount, and any leg the client left open (a shuttle with no stated hours, "all day" with no end time). Ask it as question 0 with the reading in the message and "Yes, that reading" first. A request that names scenarios without vehicles or hours is never priced on a silent guess: the same Yerdle request was priced as one coach with a 6-hour shuttle in one session and as coach plus mini bus for 8 hours in another, $7,000 apart. After the yes, record each reading with `--reading "<scenario: vehicles, hours, headcount>"` so it travels into the document's assumptions.
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
- **Read every client time as one of three things (R18/R34).** A flight number or "departs at" is a **flight departure**. "Pick us up at" is a **pickup**. "Drop off at", "be there by" or "arrive at the airport" is an **airport arrival target**. Infer from the wording and ask the user to confirm only when the wording does not settle it (one picker, Step 3). Never price a flight departure as if it were the pickup.
  - **Flight departure** → target = departure minus the lead time (**2 hours domestic, 3 international**, or the client's own). Pickup = target minus Core's drive time.
  - **Airport arrival target** → pickup = target minus Core's drive time.
  - **Pickup** → the pickup, as given.
  - Drive time comes from the stops' `drive_minutes`, never from a guess. Price the unit at the target to read the drive time, then re-price once at the target minus that drive time. The write accepts a pickup that puts the car at the airport at or before the target and no more than 10 minutes before it (R105), using the drive time Core returned for the pickup you priced, so a minute of drift needs no further pricing. If the write still refuses after that one re-price, ask the user to confirm the pickup and record it with `--time-reading KEY|pickup|HH:MM`. If Core returns no travel time, ask the user for the pickup.
  - Record the reading with `write --time-reading KEY|flight_departure|HH:MM|lead_hours` (or `airport_arrival_target`, `pickup`). The write refuses when the priced pickup is outside the arrival window. The quote prints both times: "Pickup 11:55 AM · airport arrival 12:50 PM". Never quote a guessed pickup silently; it changes billable hours.
- **An hourly block that runs across an airport transfer is put to the user (R97).** After you split the legs, compare each hourly or full-day block with the airport transfers on the same date. If a transfer starts inside the block, ask one question in the pickup picker: *start the block after the transfer*, *start it at the client's time*, or *another time*. Nothing is priced on the overlap until they answer. Two units on the same date, at the same time, over the same stops (a Sprinter and an SUV carrying one split group) are one trip in parallel and are not an overlap (R107): do not ask about them. Record it with `write --overlap "BLOCK|TRANSFER|start_after_transfer"` (or `client_time`, `other:HH:MM`). `write` refuses an unanswered overlap and refuses `start_after_transfer` while the block is still priced before the transfer ends.
- **A stop the user is holding open gets a neutral label (R98).** When the client has not given an address yet (a pickup "in White Plains, to be confirmed"), price with the resolved location and record `write --placeholder-stop "UNIT|stop name|White Plains, NY (pickup address to be confirmed)"`. The PDF, the email and the map print that label and never the resolved name or address.
- **A fact Core does not return is asked for, never inferred (R35).** Core returns no vehicle length, width or clearance. When a client's constraint hinges on one (an 18 ft parking pass, a low garage), **ask the user** for the figure; do not take it from the class, the name or `vehicle-types.md`, and do not tell the user a vehicle fits or does not fit. Record the answer with `write --fact "KEY|the question you asked|their answer"`. Only a recorded fact may appear in a document, and it prints labelled as supplied.
- **What the client supplied prints as given; only what they did not supply is "to be confirmed" (R74, R62).** When the client gives a flight number or time, record it with `write --flight "UNIT|BA2612 departing 2:50 PM"`. The document prints it and drops "Flight details to be confirmed" for that leg. Never log a supplied flight as a placeholder; `write` refuses that. When the client names a venue ("the Hyatt Regency"), keep that name: `write --venue "UNIT|the stop name Core returned|Hyatt Regency Boston Harbor"`. The fuel surcharge is the system's and belongs to the whole quote: it appears in the header and the terms only, never beside a leg, market or region, in the PDF or the email.
- **Flight numbers are not usable yet.** Always send `commercial_tbd: true` with the flight time, even when the client gave an airline and flight number. The engine requires a resolved airline object with an id and there's no tool to resolve one, so a flight number makes the call fail. Keep the number as a client-facing line note ("AA 1234, departing 2:30pm") and tell the user once that it's recorded on the quote but not yet linked to flight tracking.
- **The client's own questions that don't change pricing** (tax, gratuity, cancellation, on-site staff, signage) never block anything — record them with `--client-question` and let the document stage answer them.
- Write the client's message verbatim to `request.md` now.

## Steps 2–8 — the flow

`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md` is the **single source** for what to call, skip and ask at every node (A–J here, K–Q in the document skill). Read it once at the start of a quote; don't re-read it mid-flow. The shape in one paragraph so you know what you're reading:

resolve client + stops + vehicle types in one turn (no passenger unless the user named one) → ambiguities and blocking gaps in one picker → *rate sheet?* → *best / options / define?* → **one** quote call → scripted summary → refine loop → **one** question: *customize it, go on to the client document, or just the quote?* With two or more options the same question also settles which go to the document, **both options** first (R93) → handoff

**When a unit has no stored rate in the market**, that is not a dead end. Core's recovery
is the flow: ask the user for a temporary rate or another vehicle, then re-quote through
`calculate_temporary_quote_units`. A leg with an intermediate stop can only take an
**hourly** temporary rate — a transfer rate needs exactly two stops and Core rejects it
otherwise. Say the number came from a rate they supplied, and that it is not stored in Savoya: the booking prices differently unless the custom rate is added there (R103).

**A client Savoya does not have (R102).** When `resolve_client` finds nothing after the user's name, email or id, offer a stand-in: an existing client with no discount at the company and none on its profile. The user names it. Quote under it, then `handoff.py write --client-source stand-in --prospect "<real client's name>"`; the write refuses if the quote carries any contracted discount. Tell the user once: quoted under the stand-in, book under the real client.

**One tip when you ask about a client or a stop (R101).** In that same message add: "Next time, start with 'Use savoya plugin to quote' and put the client ID and full street addresses in the request." Once per session.

## Questions — inline, and not negotiable

**Every question goes out through `ask_user_input_v0` with tappable options, one question per message, and you wait for the answer before the next.** The two failure modes both look fine as you write them: asking in prose, and folding two questions into one sentence ("Which option, and do you want a PDF?"). Both lose the answer. If an answer genuinely can't be enumerated — a client name, an email, a dollar amount — prose is correct; everything below can be enumerated.

| # | When | Question |
|---|---|---|
| 0 | Only if something is genuinely ambiguous | Blocking gaps **and** stop ambiguities, batched into **one** message — missing year, headcount range, a location that didn't resolve, unsettled service shape |
| 1 | **Every quote, no exceptions** | Rate sheet first, or straight to the quote? |
| 2 | **Every quote, no exceptions** | Best value, a few options side by side, or you name the vehicles? |
| 3 | After the quote (the only question after it) | Customize it, go on to the client document, or just the quote? (One question; if they go on, quote-document asks the format.) **With two or more options on screen the same picker leads with `Both options → client document` (all N when there are more than two), then `Option A only → client document` and one entry per other option, then `Customize first`, then `Just the quote`.** With more than four options: `All options`, `Choose which`, `Customize first`, `Just the quote`, and the user names them. "Both" writes every option with `--package`; one option writes only that option's saved package, and needs no new pricing call. |

**Never ask the user about the product's own working (R93):** how a file is written, how the handoff is saved, which of the scenarios you just showed to keep. A CSM cannot answer these and every one is a chance to answer wrongly.

1 and 2 are asked on every quote however self-evident the request looks — skipping them is the single most common regression. Client questions that don't change pricing (tax, gratuity, cancellation, on-site staff) are **never** asked and never block: record them with `--client-question` and let the document stage answer them. "go" means no rate sheet, best value.

Three things the tree assumes you already did in Step 1, and won't repeat:
- the unit structure and its rationale,
- `request.md` written verbatim,
- blocking gaps identified (they become the first picker).

Commands, in order:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py client "<name>"        # cached profile id, or nothing
# … resolve, ask, quote …
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize scenarios.json --select value
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write --dir handoff … --final
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py capture --dir handoff   # only if they decline a document
```

## Saving a pricing response (R78) — never retype one
A pricing tool's result arrives in the conversation as text. The document step needs it as a file **exactly as returned**. **Never hand-type, rebuild or "tidy" a `raw_quote.json`** — retyping is how a figure drifts, and two sessions on 16 Oct 2026 either did it or stopped because of it. Instead pass the whole response, untouched, to the checked step:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py ingest --name A --dir handoff <<'JSON'
<the complete tool result, pasted as returned>
JSON
```
It prints `SAVED … units add up to the response's own total`, or `REJECTED` with the reason (not JSON, no priced units, totals do not add up — the paste was cut or changed). On `REJECTED`, paste the response again, whole; never patch it to pass. One `ingest` per priced package; `--name` is any short label (`A`, `B`).

**A `generate_quote_options` response (2–5 options) goes through the same `ingest`, whole and untouched.** It checks each option as a package and saves each one as `<name>_<option key>` (for example `A_value`, `A_elevated`); one failed option saves none. It prints the `--package` flags to pass to `write`. Never save it by hand or re-run `ingest` per option. A re-price that follows (for example a time reading) is a new `calculate_quote_units` call for that unit, ingested again under the same name.

**Two or more separately priced packages become options in one document (R79).** When scenarios are separate packages (sourced vehicles are quoted one package at a time), ingest each, then:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write --dir handoff … \
  --package A --package B [--shared B_unit=A_unit] [--alt-of B_unit=A_unit] --reading "…" --final
```
The first `--package` is Option A; the others' units become alternatives. A unit priced identically in both (the same Jun 10 shuttle) is declared with `--shared` and counted once. Each option keeps the pricing system's own total; nothing is summed. A single document with both scenarios is possible and is the default; never tell the user it is not.

If the data cannot be saved or the document flow stops for any reason, intake still leaves a record: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py --blocked "<what stopped it>" --slug <slug> --client "<Client>" --request handoff/request.md` (R80).

## A quantity above Core's inventory (R95)
Core returns `market_inventory_shortfall` when more vehicles of a type are requested than its unconfirmed inventory shows. The CSM may know better: a vendor confirmed the vehicles by phone, which Savoya's data does not reflect. Core prices that case itself once the CSM overrides the shortfall. **Never scale a unit by hand, and never price a smaller quantity in its place.**

1. **No price on a shortfall.** State, per returned market or market group, the vehicle type, the requested count and the available count.
2. **Ask what they want**, with `ask_user_input_v0`: `Split differently` · `Show 3 more markets` (node F2) · `Override inventory`, because they have the vehicles. Ask no reason and no vendor details; the decision is theirs. After a nearby lookup the same override is on page 2 of the market choice.
3. **On "override"**, send the same package to the same tool again with `"inventory_override": true` on every unit in each shortfall they overrode. Only after Core reported the shortfall and the CSM chose it; never preemptively, never on your own.
4. **Core prices it** and puts an `Inventory override: …` warning on each affected unit. `ingest` and `write` as usual; the warning stays internal. Say it in the summary ("7 Sprinters: 3 in Savoya's inventory, inventory overridden"), never in a client document.

## What intake never does
Discounts beyond the client's contracted rate, fuel surcharge, covers, personalization, maps, formats, mail. Those are document-flow questions. The number presented is the client's contracted pricing, and the summary says so.


## Questions about how this works, and "log this session" (R87, R90)

**"How does this work?", "what can't it do?", "why did it ask that?"** Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/help.md` and answer from it, in your own words, for the user's question only. If its frontmatter has a `page_url`, give that link when they want the whole picture. If the file does not answer the question, say so; do not answer from memory. Never state a price in an answer.

**"Log this session"** (or "report a problem", "save this session"), at any point in the conversation: the user is asking for the session record, with or without a document. Follow the capture consent rules in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`. If a document has been delivered, run the normal capture with `--change "<their words>"`. If not, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py --blocked "user-requested: <their words>" --slug <slug> --client "<Client>" --request handoff/request.md`, upload the file it lists, then `--mark-uploaded`. Reply in one line that it is saved, and tell them to post a short note in the core-ideas Slack channel so someone picks it up. A user asking for this is asking for the record; do not talk them out of it.
