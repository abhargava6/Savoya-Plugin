# Decision tree — the whole flow

Tool names, required arguments and limits live in **`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/mcp-contract.md`**, which is the contract the regression suite enforces. This file says *when* to call; that file says *what* the call takes.

Every node resolves to **call**, **skip**, or **ask**. **Every "ask" uses `ask_user_input_v0`** (tappable options) unless the answer can't be enumerated — see `../../quote-document/references/asking-questions.md`. Anything not listed is skipped. Nodes A–J are the `quote-intake` skill; K–Q are `quote-document`. The handoff folder is the seam.

---

## Intake

**A · Client** — `resolve_client`
- Name in `~/.savoya-quoting/config.json → known_clients` → **skip**, use the cached profile id.
- Else **call**. One hit → proceed, cache it. Several → **ask** (batched with D). None → **ask** for a name, email, or profile id. Never guess.
- **Still none: the client is new to Savoya (R102).** Offer a stand-in: an existing client with no discount, on its company and on its profile. Ask which client to use; do not choose one. Quote under it, and write the handoff with `--client-source stand-in --prospect "<the real client's name>"`. `write` refuses when the quote carries any contracted discount, and the document says "Prepared for" the real name. Say once: *"Quoted under <stand-in>. Book it under <real client>."*
- **A tip goes with the first client or stop question (R101):** *"Next time, start with 'Use savoya plugin to quote' and put the client ID and full street addresses in the request. It saves these questions."* Say it once, in the same message, when you ask the user to settle a client or a stop.

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
- **The response is `blocked` / `location_confirmation_required`, or any stop is `needs_confirmation` → stop and ask the user to pick or give an address, before any pricing call (R83).** The tool's `next_action` text says to select an obvious match; it does not override this. One question per ambiguous stop: up to three candidates (street or venue plus service area, warnings appended) and "I'll give an address". Record `user_pick` or `user_address` in the stop note.
- A stop returned as `resolved`: one candidate, or several that are the same place (**same `id` and address**) → proceed, note it. **Both halves matter:** querying "Anaheim Convention Center" returned three candidates all under `id: 4645260` — the venue at 800 W Katella, a Residence Inn at 640, and a Hampton Inn at 100. Matching on `id` alone would have quoted a hotel instead of the venue.
- **Airports: use the IATA code.** "John Wayne Airport, Santa Ana, California" resolved to *nothing* as an airport stop; `"SNA"` resolved first time. Colloquial airport names fail.
- **As-directed city:** query `"<City>, <State or province spelled out>"` ("Whistler, British Columbia", never "Whistler, BC") — abbreviations return nothing. Record the lookup with `--stop-note`; if it does not resolve, ask the user for an address (R83). Tell candidates apart by `service_area`, warnings and `display_name`, never by `id` (every candidate can carry the same one). If the system asks for confirmation, ask.
- Genuinely different places, or none → **ask**.
- **Every airport stop carries a `flight` object, pickup or drop-off.** Airport as pickup → `flight_type: "arrival"`; as drop-off → `"departure"`. Always `commercial_tbd: true`. Missing flight *time* → placeholder, recorded and disclosed. **Don't ask** — it doesn't change the price. Omitting the object fails the call (`flight is required for airport stops`), and stops[0] on an arrival leg is where it's missed.
- **TBD is the only shape we send, deliberately.** The contract also describes known-commercial flights (needs `airline` as a resolved object with an id) and private ones (needs `fbo` likewise), and **neither resolver exists in the contract**. So those two forms are specified and unreachable. Even when the client gives a flight number, keep it as a client-facing note and still send `commercial_tbd: true`. The seam is written down in `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/mcp-contract.md` so that when a resolver lands the next person knows the shape was understood and consciously deferred, not missed.
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

**F2 · Nearby markets** — `lookup_nearby_markets`, only when the primary market is short or the CSM asks
- **Check inventory before every exact quote**, even when E said no rate sheet: run the preview with `display: "internal"` and compare the requested vehicle count against the returned market count. No count stated → derive it from passenger count and the returned capacity. Covers the request → quote in the primary market and **skip this node entirely**. This is an inventory check, not a driver or vendor schedule check.
- **Skip unless short, or the CSM explicitly asks to explore other markets.** R48 is user-initiated this phase; the plugin does not go shopping on its own.
- Different starting market named by the CSM → `resolve_service_areas` first, and let them pick among ambiguous hits. Never infer a service-area id from a city name.
- **Call** with `reference_service_area_id` and `inventory_date`. Returns the three nearest markets **by road distance**, each with the vehicle types and quantities it *adds*, plus a signed `market_ref`.
- **More markets, three at a time.** When the CSM wants more choices, call again with the same reference market and date and `shown_service_area_ids` set to every service area returned so far. It returns the next three nearest (`newly_listed: true`) together with every market shown earlier (`newly_listed: false`), all in road-distance order, and the table shows them that way with the new ones badged. Page as often as they ask, up to twelve markets shown; never jump ahead on your own.
- **Any market the CSM names.** A market need not be among the nearest. `resolve_service_areas` for the name, then call with `service_area_ids` (up to three) and `shown_service_area_ids` for any already shown. It returns those markets at any distance, each with its `market_ref`.
- **The counts are "additional", not totals.** Vehicles whose vendors already serve the reference market are excluded, because they are already counted there. Say so when you present the table — a CSM reading "Market B · SUV 4" will otherwise promise a client four SUVs that may not be four *extra* SUVs. The counts are also **unconfirmed** and promise nothing about fulfilment; say that too.
- **Listed markets can share vehicles.** Each vehicle count names the other listed markets that have some of the same vehicles ("Mini Bus: 3 also in Hartford"), and the lookup returns how many distinct vehicles all listed markets add together. A market keeps its own count because it can still serve the trip alone, just not together with the one it shares with. Say so when the CSM weighs a split across markets that share vehicles.
- **Sourced vehicles bill at the primary market's rates.** Confirmed live: an Austin Mini Bus sourced into Dallas billed Dallas's $314.92/hr, not Austin's $244.09/hr. The nearby market supplies the vehicle, not the price.
- **A nearby market's rate sheet can be shown, but it must carry the warning.** It is obtainable — resolve two landmarks in that market and preview — and a CSM may legitimately want it. But those numbers are *not* what gets charged when sourcing, so lead with that, and when a sourced quote is in play name both: *"Austin's own Mini Bus rate is $244.09/hr, but sourced into Dallas it bills Dallas's $314.92/hr."* Never show a nearby rate sheet as if it were the sourcing price.
- **A `market_ref` is scoped to the trip's primary market.** Look up from the market you are sourcing *into*. A ref obtained from another market's lookup is rejected with a `source_market_ref_mismatch` issue; look the same market up again from the trip's primary market with `service_area_ids`.
- **Any service area can be a source market.** The nearby list is a display aid, not a limit. If the CSM's market is not on it, look it up by name as above rather than telling them it cannot be used.
- **"What's cheapest?" is a quote, not a sum.** Never answer it from the rate sheet. A session compared rate cards, said sourcing a Mini Bus from Austin would save about $80, and the exact quote came back **$707.18 more** — rate-sheet maths cannot see the positioning drive time, which is the whole cost of sourcing. Price the candidates through Core, or say a quote is needed first. Labelling it an estimate does not make it safe; the CSM still has a number to repeat.
- **Present, then stop.** A lookup is not a choice. **Ask** which market or mix the CSM wants, and the vehicle type and quantity for each. Never pick a source market for them, and never read a lookup or a preview as consent.
- **The choices after every lookup, the first included: one `ask_user_input_v0` call with two questions**, so the follow-up choices page in the picker with no second turn, and **never more than four options a page** (the rule is in `SKILL.md`, which is always loaded).
  - **Page 1:** one ready-made split per **newly listed** market that covers the gap alone, nearest first, at most three (`3 Orange County + 2 Los Angeles`), then *None of these*. Left out when no new market covers the gap alone. With no vehicle count, or a primary market that is not short, name the new markets instead.
  - **Page 2:** *Use my choice above* (only with page 1) · **Show 3 more markets** · **Split differently** · **Override {primary} inventory**. Leave out *Show 3 more markets* once twelve markets have been shown, and the override when the primary market is not short.
  - **Reading the answer:** a page-2 answer other than *Use my choice above* wins over page 1. *Split differently* asks which markets and how many of each in prose. *Override* follows R95 below.
  - **Never offer a market from an earlier lookup as its own option**, and **never mark an option as recommended**. The CSM picks the market; a recommendation is picking it for them.
- `market_ref` is valid **24 hours**. `sourcing_reference_expired` → look the expired markets up again from the same market and date with `service_area_ids`, swap in the new ref for the same service area, retry. Don't re-ask; they already chose.
- `market_inventory_shortfall` → **no price**. State, per returned market or market group, the vehicle type, the requested count and the available count. Markets returned together **share vendors**, so their combined distinct vehicles can fall short even when each looks sufficient alone. Then ask: a new split, more markets, or an **inventory override**.
- **The CSM overrides the inventory (R95).** They may have the vehicles confirmed with a vendor by phone, which Savoya's data does not show. On their explicit choice, resend the same package with `inventory_override: true` on each unit in the shortfalls they overrode. No reason is asked. Core prices it and returns an `Inventory override` warning on each affected unit; it is internal and never in a client document. Never override on your own initiative or before Core has reported the shortfall.

**G · Quote** — **one call**, all units

- **Overlap and held-open stops (R97, R98).** After the legs are split, compare each hourly block with the airport transfers on its date; units on the same date, time and stops are one trip in parallel and are skipped (R107); a transfer that starts inside the block is one question (start the block after the transfer, at the client's time, or another time) and is recorded with `--overlap`. A stop the user is holding open is priced at its resolved location and recorded with `--placeholder-stop`, so every document prints the neutral label.
- **What the client supplied (R74, R62, R35).** A supplied flight is recorded with `--flight` and prints as given; a venue the client named is kept with `--venue`; a dimension Core does not return is asked of the user and recorded with `--fact`. None of them is logged as a placeholder.
- **Time reading (R18/R34).** Before pricing an airport leg, classify the client's time: flight departure, pickup, or airport arrival target (wording decides; confirm with the user only if it does not). For a departure or a target, price at the target, read `travel_times`, set pickup = target minus drive time (a departure first loses the 2h domestic / 3h international lead), and re-price once at the pickup. Write it with `--time-reading`; the write accepts a priced pickup that puts the car at the airport 0 to 10 minutes before the target, using the drive time Core returned for that pickup (R105). Still outside after one re-price: ask the user to confirm the pickup.

- **Every price in a reply comes from a tool response.** No arithmetic of ours: no totals, no per-vehicle splits, no "roughly", no comparison between a priced option and an unpriced one. If a number is worth saying, it is worth a call.

| Condition | Tool | Shape |
|---|---|---|
| best or options | `generate_quote_options` | an `options` array, **2–5**, each with its own `key`, `label` and a **complete** `quote_units` list. Usually two: **value** (candidate `vehicle_type_ids`, Core prices each and takes the lowest per unit) and **elevated** (a fixed premium `vehicle_type_id`) |
| you define | `calculate_quote_units` | **one** `vehicle_type_id` per unit — candidate lists are not accepted here |
| vehicles sourced from a market the CSM chose at F2 | `calculate_sourced_quote_units` | one allocation per itinerary × vehicle type × source market, **all in one call** including the primary-market ones. `source_market_ref` is the signed ref from F2; omit it for primary-market allocations. `quantity` is **required** and means *vehicle count* — it does **not** mean what it means on `calculate_quote_units`, where it is a repeat count. Never quote the primary portion alone and present it as the full package |
| user supplied a temporary rate or an extra discount (**including on a sourced package** — resend every allocation, primary ones too, each carrying the temporary input and its `source_market_ref`) | `calculate_temporary_quote_units` | one `vehicle_type_id` per unit, plus `temporary_rate` (`rate_type`: `hourly` \| `transfer`, `amount` in **cents**) and/or `temporary_discount` (`basis_points`; 500 = 5%). At least one of the two is required. **Never persisted — say so.** |

- **No stored rate in the market** is not a dead end and never an estimate. Core's own
  recovery wording is the flow: **ask the user for a temporary rate, or pick another
  vehicle.** Then re-quote through `calculate_temporary_quote_units`. Say plainly that the
  number came from a rate they supplied, not from Savoya's rate sheet. **And say it exists only in this quote (R103):** *"This rate is not stored in Savoya. Add it there before booking, or the booking prices differently."*
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

**G2 · Detail card** — no longer a question (R93, 0.27.5): the choice of option is part of node I. **Call** `calculate_quote_units` with an option's chosen vehicle per unit only when the user asks to see that option's detail card while customizing. Identical numbers; it renders the full detail card that `scenario_comparison` shows condensed. **Skip** otherwise, and always in define mode — already that shape.

**G3 · Greeter / on-site staff** — a Core quote unit, never a number a human invents

Greeters are vehicle types: **12 Hourly Greeter/Coordinator**, **13 Single Greet**. Both come back `greeter: true`, `capacity: null`.

**Always check the rate first. Never ask a human for a number Core has.** An Irvine quote carried a hand-entered *"On-site coordinator — 4 hrs at $235/hr = $940"* against Core's **$404.20** for the same request — 2.3× over, in front of a client.

**The rate check is an attempted price, not a lookup.** Greeters do not appear in `preview_rate_batch`'s `vehicle_rate_evaluations`, and Core does not list them in `missing_vehicle_type_ids` either — the rate sheet simply cannot answer the question. So price one and read the answer: a priced unit means the market has a rate; `status: "blocked"` with `error_type: "quote_units_unavailable"` means it does not. That is not a wasted call — in three of the four rows below the priced unit is the thing you wanted anyway.

| Who raised it | Rate in that market? | Where it's handled |
|---|---|---|
| **Client asked** | Yes | **Intake** — a quote unit in the package they requested |
| **Client asked** | No | **Document flow** — ask the user for a cost, as a flat line |
| **User wants it**, client didn't | Yes | **Document flow**, using Core's rate |
| **User wants it**, client didn't | No | **Document flow**, ask the user to supply one |

The rate check is the constant; the *location* follows who raised it. Something the client asked for is part of the quote they requested, so it belongs in intake. Something the CSM adds is an add-on to a finished quote, so it belongs in the document flow.

**The unit shape is pickup + an `as_directed` stop carrying the hours.** A `duration` on the dropoff is **ignored** and the unit collapses to the 2-hour minimum. Do not model a greeter as hotel → venue: that reports a drive time for someone standing in a lobby.

**▲ Core adds positioning time, so say both numbers.** Verified: `duration: 2` billed **3.25** hours, `duration: 4` billed **5.25** — a constant **+1.25 h**. Send what the user asked for, show what Core billed, and name the difference: *"4 hours as directed; Savoya bills 5.25 including positioning — $404.20."* Never back-solve the duration to make the billed figure match the request; that is the arithmetic this release removed.

- Don't pass the group headcount to a greeter unit — capacity is `null`, so there is no fleet to size.
- `limited_availability: true` shows up on greeter types. Worth saying before a CSM promises one.
- The renderer suppresses drive time on an as-directed greeter leg; a greeter drives nowhere.

**H · Read the result** — **`${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/render_presentation.py <file>`** renders Core's own `presentation` block, which is the CSM-facing view: same layout for every CSM looking at the same quote, and Core's figures printed rather than restated. Exit **3** means the response carried no `presentation` block — fall back to `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize <file> [--select <key>]`, which is still the right tool for the comparison summary and the handoff. Never open the response yourself, and never reword either script's output.
- **It is internal.** The render carries rate ids, rack-versus-effective rates and `limited_availability`. None of that goes in front of a client — `quote.json` and the whole document flow stay ours.
- **If Core's presentation total and its own quote units disagree**, the render says so and prints both. Don't pick one. Re-quote, and if it persists that is a Savoya-side report.
- **The presentation carries no actions.** The MCP view offers no buttons; every decision, the refine loop at node I included, is asked by the plugin with `ask_user_input_v0`.
- A unit came back `rate_unavailable` for every candidate → **re-quote** that unit with the next class from the table and say what you swapped; if nothing prices, report it as the rate sheet would have.
- **Warnings: the summarizer shows them all, translating the shapes it knows and printing the rest verbatim.** It used to print only the two shapes it recognised and drop the others silently, which hides a real warning as effectively as filtering would. One warning is suppressed — Core's "no passenger was selected" note, and only when the unit priced, because omitting `passenger_id` is now the normal path. A distinct warning is said once per quote, not once per unit per option.
- Unquoteable candidates inside a priced unit → shown as `✗`, no action needed.

**I · Refine and hand off** — one question, the only one after the quote (R93): *"Customize this — different vehicles, headcount, hours, another scenario — go on to the client document, or is the quote all you need?"*
- **Two or more options on screen:** the same question leads with the choice of options. Picker, in order: `Both options → client document` (`All N options` when there are more than two; recommended), `Option A only → client document` and one entry per other option, `Customize first`, `Just the quote`. With more than four options: `All options`, `Choose which` (the user names them), `Customize first`, `Just the quote`. It replaces the old detail-card question (G2); there is no second question.
- **Both or all** → `ingest` the options response once (it saves each option as a package), then `write --package` for every option. **One option** → `write` with that option's package alone; no new pricing call.
- **Customize** → back to **G** with the same stop refs. Loop until they say it's final.
- Stop refs older than ~24h → back to **D** first. Never retry a rejected stop ref.

**J · Hand off** — first save each pricing response with `handoff.py ingest --name <A|B…>` (never retype one; R78), then `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write … [--package A --package B] --final`, which is done only after the answer to **I** (never assume from context; the format is asked by the document flow, not here).
- **Just the quote** → valid end state. `handoff.py capture` → upload once to the Drive folder. Done.
- **Go on to the client document** → document flow. Don't capture here; K–Q captures once at the end.
- No answer → leave it; the handoff stays on disk and "make the PDF" later costs nothing.

---

## Document

**K0 · Machine check** — `preflight.py`, once per conversation before the first render. Exit 1 = some formats unavailable; state it in one plain line when it first matters and carry on. **Never show install commands or Terminal instructions to the user** — CSMs aren't technical, setup is a one-time IT task (`SETUP.md`). The only instruction they get is Print → Save as PDF, worded for their OS.

**K · Read the handoff** — including `client_questions`, which come in three kinds: **boilerplate** (terms block already answers it), **operational** (carried to the document as one neutral "noted, will confirm" line; never claim it is included, excluded or arranged separately, R73), and **data-answered** (pickup times, drive times, vehicle counts — the quote holds the answer implicitly, so surface it as an explicit callout at the top of the PDF and the email). An internal gap must never appear as a client-facing "please confirm".

- `handoff/intake.json` exists and `final: true` → `normalize_quote.py --from-handoff handoff` and **ask nothing about the quote**.
- `final: false` → **stop**: "The quote isn't final yet."
- No handoff (quote from elsewhere) → fallback: save the response, ask which units are chosen, normalize with `--select` / `--alternative`.

**L · Six questions plus one conditional, one per message, driven by the script**
`decide.py --next` prints the next unanswered key and its exact question text; post that and nothing else; record the answer; repeat until `all answered`. Never batch, never skip, never reorder. The script also *drops* questions: `cover` and `map` are not asked for an email-only job (the format is asked first, so this holds even when the user never named one), because nothing but the PDF and printable document reads those answers.

1. **discount_pct** — **a Core re-quote, not a document line.** `calculate_temporary_quote_units` with `temporary_discount.basis_points` (500 = 5%), then re-normalize from the response. This node used to say *never re-quote through the engine*; that was right under the old contract and is **wrong now** — a discount applied here was our arithmetic on Core's number, and Core returns the whole standard → discount → net line with nothing left to compute. Discounts are **additive in basis points**: 30% contracted + 10% here = `4000`, not 37%. On a cross-market sourced quote, resend every allocation with its `quantity` and `source_market_ref`, primary-market units included, each carrying the discount — dropping the split re-prices every vehicle from the primary market, which usually ends in `market_inventory_shortfall`. Never persisted — say so. If the client's contracted discount is already on the quote, the question says this one is additional.
2. **greeter_cost** — *inserted only when a client question mentions a greeter or on-site staff, and only a market with no greeter rate gets this far.* Check Core first; never ask a human for a number Core has (see **G3**).
3. **commission_pct** — *"Does this client get a commission on this quote?"* No · 1% · 5% · something else. **Rate recorded, amount computed in code**: record it with `apply_adjustments.py --commission-pct <pct|none>` (that script owns the terms block, so the rate and its bullet land together, and it computes the amount per option — the subtotal after every discount, before fuel, times the rate). **No total changes** — it never enters `adjustments` and the total is identical either way. Never work an amount out yourself. The wording names no beneficiary, because the commission may be the client's or an agency's. On *No*, nothing is recorded and the word appears nowhere.
4. **format** — PDF · email copy + PDF · HTML · DOCX · XLSX. Asked before `cover` and `map` (R110) so those two can be dropped when the format does not use them.
5. **cover** — catalog keys with audiences, recommendation first, or their own upload (`--cover-file`).
6. **personalization** — event name, intro note, contact card, logo URL, per-leg notes, closing line; defaults stand for anything unmentioned.
7. **map** — yes → `route_map.py` (drive times already come from the engine; this adds the map image).

**There is no fuel question** (C3, 7 Oct). Fuel is market-scoped and engine-applied; nothing in the contract subtracts it, and `temporary_discount` is additive rather than a way to remove a surcharge. A CSM who needs it waived does that in Savoya. The `[if:fuel_surcharge]` terms bullet stays, because it reflects what Core applied.

**M · Adjust** — `apply_adjustments.py`. Engine-sourced lines (contracted discount, fuel, special handling) are preserved by `--clear` and can't be `--remove`d — only `--waive`d. **Flat** document lines apply in order on the running total; a document **percentage** line is refused outright (C2) — percentages are Savoya's to compute. And if the document total no longer equals Core's `aggregate_total`, the render **refuses** rather than absorbing the gap into the last engine line (C4); that absorption is what put a 5-vehicle Boston job 30 cents above Savoya's own quote.

**N · Render** — everything the format needs **before replying**: PDF via `render_print.py`, email text via `draft_email.py`. Read only the one format reference you need.

**N2 · Verify** — `verify_document.py quote.json --pdf out.pdf [--email draft.txt]`, always, before replying.
- **0 PASS** → deliver.
- **1 FAIL** → fix, re-render, verify again. Never deliver a failing document; never hand the failure to the user.
- **2 PARTIAL** → deliver, and say in one line it couldn't be fully verified here and why.
- `render_print.py` exit **3** = no PDF engine on this machine; the HTML is written — deliver it and say so.
- Warnings → read and judge.

**O · Deliver** — one message: email as a copy-ready block, files via `present_files`. No mail connector, no attaching, no sending.

**P · Capture** — **once per conversation**, after the final deliverable. `capture_session.py` (it reads `handoff/intake.json` automatically) → one Drive upload. Load the Drive tool once.
- **A session that improvised is the one that must capture.** Patched a script in a working copy, rebuilt a line by hand, worked around a defect? Put it in `--workaround` and upload. That session is the only evidence the defect exists.
- **It cannot fail on you.** `--request` is optional, a missing handoff is noted rather than fatal, and an unexpected error still writes a failure record and exits 0.
- **Read-only plugin ≠ nowhere to report.** The capture writes outside the plugin, to `~/.savoya-quoting/captures/` and Drive.

**Q · Feedback — ask, fix, then log.** The reply carrying the first document ends with: *"Anything you'd like changed?"*
- They name something → **fix it first** (adjust → re-render → re-verify → deliver), then capture with `--change` *and* `--fixed`. Say "fixed and logged".
- No, or no answer → capture without them. Don't chase.
Never log a request without acting on it. P (capture) therefore runs **after** any fix, not before.
