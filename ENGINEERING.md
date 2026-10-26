# Open items for Savoya engineering

Items found while building and testing the `savoya-quoting` plugin that need a change, a decision or a data fix **on the Savoya side**. Plugin bugs are not here. They go in `skills/quote-document/RULES.md`, with dated history in `feedback-archive.md`.

**Order of the file:** Open, then Deferred, then Resolved. Every Open and Deferred item uses one template so it pastes into a Jira ticket under `GREEN` (Epic `GREEN-243`). Pipe tables are dropped by Jira's markdown conversion, so items use lists and code blocks. Ids `H1`–`H4` were raised 2026-10-11. Ids `I1`–`I3` were raised 2026-10-24; they are with Ethan Ward and none blocks the plugin.

**Item template**

```
### <ID> — <title>
Type · Priority · Status · Jira · PRD
Problem statement
Impact            (includes what the plugin does meanwhile)
Steps to reproduce (real tool responses and numbers, verbatim)
Reference
Acceptance criteria
```

**Type:** Defect · Feature · Decision · Data fix
**Status:** `open` · `deferred` · `answered` · `done` · `wontfix`
**Owner:** Savoya engineering unless noted. Triage contact: **Ethan Ward**.

**Rules**
- Ayush adds items and resolves them. Nothing moves to Resolved without his say-so, and a resolved item carries the answer and the date.
- Evidence is never paraphrased. Numbers and tool responses stay as observed.
- Canonical copy is the plugin repo (`~/Documents/Savoya MCP/savoya-quoting/ENGINEERING.md`). The vault copy is a byte-identical mirror. Edit the repo copy, then mirror it.
- Retired and merged ids are listed at the bottom. Ids `G1`–`G6` are referenced from `RULES.md`, `CHANGELOG.md` and the G6 spec, so they stay.

---

## Index

| Section | ID | Item | Type | Priority | Jira |
|---|---|---|---|---|---|
| Open | **G6** | Compact response mode for multi-unit packages | Feature | **High** | GREEN-380 |
| Open | **B7** | No airline resolver, so known commercial flights are unquotable | Feature | **High** | — |
| Open | **F4** | No-client / rack-only quoting unbuilt on every path | Feature | **High** | GREEN-381 |
| Open | **A4** | Rate sheet ignores "Waive All Incidentals" | Defect | **High** | GREEN-382 |
| Open | **H4** | Quote tools can't price a vehicle sourced from a nearby market (Seattle → Whistler) | Defect | **High** | GREEN-388 |
| Open | **H5** | Allow quoting a quantity above Savoya's inventory when the CSM has vendor confirmation | Feature | **High** | — |
| Open | **H6** | `display: show \| internal` on `calculate_quote_units` | Feature | **High** | — |
| Open | **B7b** | No FBO resolver, so private flights are unreachable | Feature | Medium | — |
| Open | **G4** | Quote response lacks the no-local-provider warning | Feature | Medium | GREEN-383 |
| Open | **G1** | `greeter_fee` fields exist but no tool sets them | Decision | Medium | — |
| Open | **G2** | `client_can_book` missing from rate-preview `presentation` rows | Defect | Medium | — |
| Open | **G3** | `temporary_rate_used` is `false` at aggregate level | Defect | Medium | — |
| Open | **B9** | `quote_units_unavailable` returns empty `issues[]` | Defect | Medium | — |
| Open | **F8** | Greeters silently missing from the rate sheet | Feature | Medium | GREEN-384 |
| Open | **H1** | Austin rate sheet shows Mini Bus quantity 1, service area lists 4 | Defect | Medium | GREEN-385 |
| Open | **H2** | Hide action buttons on quote and quote-option cards in the chat UI | Feature (UI) | Medium | GREEN-386 |
| Open | **H3** | Hide the "No passenger was selected" warning in the chat UI | Task (UI) | Medium | GREEN-387 |
| Open | **C1** | `as_directed` city lookup fails on state abbreviations | Defect | Low | — |
| Open | **I1** | Structured record when a CSM overrides inventory | Feature | Medium | — |
| Open | **I2** | A `greeter` flag on quote view units | Feature | Low | — |
| Open | **I3** | A street-only address on quote view stops | Feature | Low | — |
| Open | **I4** | The server tells the model to pick a location itself when Core asks for confirmation | Defect | Medium | — |
| Open | **J1** | Town and area points come back as selectable stop candidates that Core cannot price | Defect | **High** | — |
| Deferred | **F1** | What Auth0 adds over today's per-CSM OAuth | Decision | **High** | GREEN-354 |
| Deferred | **F2** | MCP tool surface vs. `QuoteBuilder`: replacement or parallel | Decision | **High** | GREEN-354 |
| Deferred | **F3** | Does `QuoteBuilder`'s exact path require a passenger? | Decision | Medium | GREEN-354 |
| Deferred | **F10** | NFR-2 permission granularity, never tested | Decision | Medium | GREEN-354 |
| Deferred | **F11** | Plugin cutover plan once `QuoteBuilder` ships | Decision | Medium | GREEN-354 |
| Deferred | **D1** | Yerdle Sedan transfer rate $990 against rack $99 | Data fix | Medium | — |
| Deferred | **D3** | Chicago Mini Buses have no rates | Data fix | Medium | — |
| Deferred | **D4** | Executive Van unrated in most markets | Data fix | Medium | — |
| Deferred | **F6** | Mixed-fleet quoting within one movement | Decision | Medium | — |
| Deferred | **F9** | International stop-resolution policy | Decision (Ayush) | Medium | — |
| Deferred | **B2** | Passenger pool scope | Decision | Low | — |
| Deferred | **B4** | `scenario_comparison` hides data the payload carries | Feature | Low | — |
| Deferred | **C2** | Stop-ref TTL undocumented | Feature | Low | — |
| Deferred | **E1** | Host quote documents at a Savoya URL | Feature | P3 | — |
| Resolved | A1, A2, A3, B1, B3, B5, B8, B10 | See *Resolved* | — | — | B10: GREEN-371 |

Each Deferred item states why. Move one back to Open by changing its section and status.

---

# Open

## G6 — Compact response mode for multi-unit packages
**Type:** Feature · **Priority:** High · **Status:** open · **Jira:** GREEN-380 · **PRD:** —

**Problem statement**
Quote tool responses for multi-unit packages are too large. Each vehicle option is returned up to three times (`value_option`, `elevated_option`, `vehicle_options[]`), plus a `presentation` block. When a response is this large, the Claude chat starts compacting the conversation because of the response size, and the session then re-types the engine response by hand. There is no compact mode.

**Impact**
- In five separate sessions the engine response was re-typed by hand into `raw_quote.json`. Each time it was recorded in the capture's `--workaround` field.
- The document's fail-closed check compares its own reconstruction of the total against the engine's `aggregate_total` and refuses to render on any gap. With a hand-typed response both sides come from the same typing, so a transcription slip in a line total propagates to the aggregate and the check cannot see it.
- Plugin workaround: none that works. The plugin's capture slimming drops `vehicle_options` and `elevated_option` and gets about 3× smaller, but only after the response has been received.

**Steps to reproduce**
Observed 2026-10-10 on a live 16-unit World Cup shuttle quote (`yerdle-world-cup-2027`: 4 origins × 4 match dates, one Mercedes Sprinter each, out-and-back hourly with a 4.5-hour wait).
1. In a Claude chat with the Savoya MCP connected, request the 16-unit package above.
2. Run the four tools below. Each response is too large to read directly and had to be written to disk and pulled apart with `jq`.

```
preview_rate_batch                 ~230 KB
generate_quote_options             ~190 KB
calculate_temporary_quote_units    ~124 KB
calculate_quote_units              ~108 KB
```

3. Observe that the chat starts compacting the conversation because of the response size.
4. Observe that the session then re-types the engine response by hand into `raw_quote.json`. Compaction is what leads to the hand-written response.

A 43-vehicle request would be several times larger.

**Reference**
- Full spec with measured tier sizes: `G6_Compact_Response_Spec_for_Ethan.md`
- Filed earlier as **B6** (Low, "compact response mode"; payload cut roughly 70%). Merged here. Re-rated High because of the money-check failure above.

**Acceptance criteria**
1. `generate_quote_options`, `calculate_quote_units`, `calculate_temporary_quote_units` and `preview_rate_batch` accept a compact mode.
2. Compact mode returns only the chosen option per unit and omits `presentation` and duplicated vehicle options.
3. The 16-unit `yerdle-world-cup-2027` package is readable in one call per tool, within the size tier set in the spec, without the chat compacting the conversation.
4. `aggregate_total` in compact mode equals `aggregate_total` in full mode for the same input.
5. A priced result reaches the plugin as a file with the exact bytes Core returned (saved by the connector, a `result_path` in the response, or a fetch by id). The plugin never retypes a response.

**Added 2026-10-18 (Yerdle Dallas, plugin 0.27.5):** a 7-unit response was retyped into `raw_response.json` and then edited with `str.replace` to move a pickup from 15:06 to 15:07. The money check passed because both sides came from the edited text. Comment posted on GREEN-380.

---

## B7 — No airline resolver, so known commercial flights are unquotable
**Type:** Feature · **Priority:** High · **Status:** open · **Jira:** — · **PRD:** R14

**Problem statement**
An airport stop with a real flight requires `flight.airline` as a resolved object with an id. No tool in the MCP resolves an airline.

**Impact**
- Any request that names an airline and flight number fails to quote with it. That is common in RFPs. Longest-standing functional gap in the product.
- Plugin workaround: always send `commercial_tbd: true` with the flight time, keep the flight number as a client-facing note, and disclose it to the client as "to be confirmed". The quote is correct. The reservation is not linked to flight tracking.
- The seam is written in `mcp-contract.md` so the next person knows the shape was understood and deferred, not missed.

**Steps to reproduce**
Send a real flight on an airport stop:

```
stops: [{ stop_type: "airport", stop_ref: "…",
          flight: { flight_type: "departure", airline_code: "AA", flight_number: "1234",
                    commercial_tbd: false, scheduled_time: "2026-09-25T14:30:00-04:00" } }]
```

Result:

```
MCP error -32602: flight.airline must be a resolved airline object with id.
Use commercial_tbd=true if the airline id has not been resolved.
```

**Reference**
- PRD R14; `mcp-contract.md`
- Folded in from **F5** (review of Ethan's change inventory, 2026-09-20): none of the new `StopResolution::*` services resolve an airline, and the inventory's coverage table says "No dedicated airline lookup" under R14. `flight_builder.rb`'s change is scoped to commercial-TBD normalization. The `commercial_tbd: true` workaround stays necessary after `QuoteBuilder` ships.
- Sibling: B7b (FBO)

**Acceptance criteria**
- [ ] Either a `resolve_airlines` tool (name or IATA code → id) exists, or `flight.airline_code` is accepted directly.
- [ ] The request above, with `commercial_tbd: false`, returns a quote with the airline linked.
- [ ] An unknown airline code returns an error that names the code, not the generic `-32602`.

---

## F4 — No-client / rack-only quoting is unbuilt on every path
**Type:** Feature · **Priority:** High · **Status:** open · **Jira:** GREEN-381 · **PRD:** R9, R4

**Problem statement**
Every pricing path requires a travel coordination (TC) profile. There is no way to price a request for a client with no profile.

**Impact**
- A first-contact RFP with no TC profile cannot be quoted.
- Blocks PRD **R9** (price without a named client) and, behind it, **R4** (a standalone client-facing rate-sheet document), which cannot exist until R9 does.
- Plugin behavior: decision tree node A, no client match, asks for a name, email or profile id. It never guesses.

**Steps to reproduce**
Request a quote for a client with no matching profile. Node A has no route forward. Confirmed independently from four angles:
- The inventory's limitations list for `ApproximateQuotePlanner`: "a travel coordination profile is still required; the no-client path is not implemented".
- The inventory's requirement-coverage table.
- This document's B-series.
- The plugin's own decision tree, node A (re-confirmed 2026-10-10).

**Reference**
PRD R9, R4. Related: F8 (rate preview inherits the same requirement).

**Interim option (Ayush, 2026-10-11)**
If the full no-client path is complex, add a default TC profile per environment that carries no rates, discounts or similar, and use it for quoting for now.

**Acceptance criteria**
- [ ] A written answer: scheduled (with target) or explicitly deferred past pilot.
- [ ] If built: a pricing call with no TC profile returns a quote or rate preview at rack rates, with no client attached.
- [ ] Or, as the interim: each environment has a default TC profile with no rates, discounts or similar, and quoting uses it when no client matches.

---

## A4 — Rate sheet ignores "Waive All Incidentals"
**Type:** Defect (pending confirmation) · **Priority:** High · **Status:** open · **Jira:** GREEN-382 · **PRD:** R4

**Problem statement**
A company profile's Billing tab has a **Waive All Incidentals** flag. When on, the client's fuel surcharge is waived. The exact-pricing tools honor it. `preview_rate_batch` does not.

**Impact**
- For a client with the flag set, the rate sheet shows a fuel surcharge the client's actual quote will not carry.
- `preview_rate_batch` feeds the internal preview at decision-tree node F and is the data source for the standalone rate-sheet document still wanted under the PRD.
- Plugin workaround: none. It has no way to know the two will disagree.

**Steps to reproduce**
1. Pick a company profile with **Waive All Incidentals** on.
2. Run `calculate_quote_units` for a trip. `effective_rate_amount` reflects the waiver and no surcharge line appears.
3. Run `preview_rate_batch` for the same trip. The fuel surcharge is shown as applied.

The original filing carries no captured numbers. Attach the profile id and both responses when reproducing.

**Reference**
Decision-tree node F; PRD rate-sheet requirement (R4).

**Acceptance criteria**
- [ ] Engineering confirms bug or intentional.
- [ ] If bug: `preview_rate_batch` reads `waive_all_incidentals` the same way the quote tools do, and the two agree for the profile above.
- [ ] If intentional: the response carries a field that states the surcharge is not waived in the preview, so the plugin can caveat the rate sheet.

---

## H4 — Quote tools can't price a vehicle sourced from a nearby market (Seattle → Whistler)
**Type:** Defect · **Priority:** High · **Status:** open · **Jira:** GREEN-388 · **PRD:** R48–R51

**Problem statement**
The reservation UI prices a vehicle sourced from a nearby market with that market's rates. The quote tools do not. For a Coach Bus sourced from Seattle into Whistler (primary market Vancouver), every path fails:
- Stored rates, `calculate_sourced_quote_units` → `rate_unavailable`.
- Sourced + temporary rate, `calculate_temporary_quote_units` with `source_market_ref` → `core_contract_violation` with empty `issues`.
- Temporary rate without sourcing → `market_inventory_shortfall`.

**Impact**
- A CSM cannot quote any vehicle that exists only in a nearby market. Motorcoaches for Whistler are the live case.
- The same booking can be made by hand: book a placeholder reservation, then override the service area. A quote built that way never reaches the quote-document workflow.
- Plugin workaround: none. The plugin reports the block and asks the CSM for another vehicle or market.

**Steps to reproduce**
Raised 2026-10-11 by Ayush, from an acceptance test. Client "Ayush TC" (Yerdle), travel_coordination_profile_id 201890. Also reproduced earlier on profile 181639 (Julie Fiol, Ericsson). Primary market Vancouver, Canada (service area id 11146); Whistler stops are served from Vancouver. Source market Seattle (id appears to be 11171, decoded from the signed `market_ref`).

Request: Jun 9, Whistler BC, 50–75 passengers, guided area tour, PA system. Two scenarios: one motorcoach all day, or two motorcoaches for 4 hours each. Jun 10: continuous shuttle between The Westin and the Fairmont golf course. Assumed to proceed (not given): year 2027, 9:00 AM starts, 8h all-day and 4h shifts, Jun 10 shuttle 9–5, passenger split 50 + 25.

Issue 1, stored rates:
1. `resolve_itinerary_stops`: The Westin Resort & Spa Whistler (`loc_a8daa56fe50286a4c465d769`), Fairmont Chateau Whistler Golf Club (`loc_4a019f6b44d088415e5bcf5b`).
2. `resolve_vehicle_types` (passenger_count 50): Coach Bus id 6 (capacity 50, limited_availability true, client_can_book false) plus greeters. Mini Bus is id 7 (capacity 41).
3. `preview_rate_batch` on the Whistler stops, profile 201890: the Vancouver sheet has Sedan, Premium Sedan, SUV and Sprinter only. No Coach Bus, no Mini Bus.
4. `lookup_nearby_markets` (reference_service_area_id 11146, inventory_date 2027-06-09): Seattle is the only nearby market with coaches (1 Coach Bus, 1 Mini Bus, inventory unconfirmed), about 146 min by road.
5. `preview_rates` on Seattle stops (The Westin Seattle → Space Needle, hourly) shows Seattle's stored rates:

```
Seattle, hourly, profile 201890 (listed amounts; sheet also shows 30% company discount and 10% fuel surcharge)
Sedan          3 seats   $136.29  min 2h   cancel 2h
Premium Sedan  3 seats   $209.44  min 2h   cancel 2h
SUV            6 seats   $186.34  min 2h   cancel 2h
Sprinter Van   13 seats  $249.48  min 2h   cancel 2h
Mini Bus       41 seats  $394.24  min 4h   cancel 72h
Coach Bus      50 seats  $463.54  min 4h   cancel 72h

Vancouver, hourly, profile 201890: Sedan $109.34, Premium Sedan $157.85, SUV $130.90, Sprinter $201.74 (2h min, same adjustments). No coach or mini bus.
```

6. `calculate_sourced_quote_units` with `vehicle_type_id` 6 (and 7), `source_market_ref` = Seattle's `market_ref`, 3 stops, hourly with duration. HTTP 422 on all three quotes (Jun 9 all day, Jun 9 4h, Jun 10 shuttle), for both the Coach Bus and the Mini Bus:

```json
{"status":"blocked","error_type":"quote_units_unavailable","core_status":422,
 "request_id":"c9ae6aad-9fe8-4e8a-942b-ed5c46e72561",
 "client_error":{"code":"quote_units_unavailable","category":"availability",
  "recovery":{"code":"review_rates","message":"Please choose another vehicle, provide a temporary rate, or remove the unavailable option."},
  "issues":[{"path":"quote_units[0].vehicle_type_id","code":"rate_unavailable"},
            {"path":"quote_units[1].vehicle_type_id","code":"rate_unavailable"}]}}
```

Other request ids, same error: `07e0e972-3966-4047-9c0b-113e4b414b47` (Jun 9 4h), `e7a3bb09-9c5e-4bba-8699-18f95c973e53` (Jun 10).

Issue 2, temporary rate:
- 2a. `calculate_temporary_quote_units` with `source_market_ref` (Seattle), vehicle 6 at `amount` 46354, then 46352 (cents, hourly, minimum 4, cancellation_hours 72), and vehicle 7 at 39424. Result: `core_contract_violation`, "Savoya could not complete this quote because the returned information was incomplete.", `issues: []`. Request ids: `fa0e4f6e-dd33-4763-92f6-38d0fca47645` (Jun 9 all day, 46354), `a2d4d0aa-5a69-416b-8a51-736e0c6cb677` (Jun 9 4h, 46354), `949f176c-1eea-456c-9aa4-36b72357e7b1` (Jun 10, 46354), `b737cbb0-9ee9-48de-a568-334899ceb3d4` (Jun 9 all day, 46352), `af6e50a7-83b3-4970-a47d-34c492684bf8` (Jun 9 4h, 46352), `f2221af8-304c-45b2-8f07-58891f992d74` (Jun 10, 46352).
- 2b. Same call, vehicle 6, no `source_market_ref`. Result: `market_inventory_shortfall`, "Vancouver, Canada has 0 inventoried Coach Bus vehicles; 1 requested." Request id `2368dfc7-ec75-45c4-89b6-45ee46b87e0c`.
- The tool description says to send the same allocations and `source_market_ref` values used by `calculate_sourced_quote_units`. That call fails in Issue 1, so the two may be coupled.

Issue 3, resolver gaps (minor):
- `resolve_itinerary_stops` with `stop_type: as_directed`, query "Whistler, BC" and "Whistler, British Columbia, Canada" → `location_resolution_failed`, `needs_confirmation`, no candidates. Address stops resolve, so the hourly tour was modeled Westin → Westin.
- Whistler address stops return the warning "No local providers" (served from Vancouver). Possibly expected.
- `resolve_vehicle_types` with query "motorcoach" returns `[]`. Only a call with no query and `passenger_count` returned Coach Bus.

**Reference**
- The reservation UI bills the sourcing market's rate (reporter's observation, acceptance):
  1. https://acceptance.savoya.net/savoya/reservations/62500735 — created in Whistler with a Sedan sourced from Vancouver, service area overridden to Seattle, vehicle type changed to Coach Bus. The audit trail shows a quote using the Seattle rate.
  2. https://acceptance.savoya.net/savoya/reservations/43167612 — booked with a Sedan, then only the service area overridden to Seattle. The rate changed from the Vancouver base of 142 to the Seattle base of 177.
- Hypothesis, unverified: the reservation builder resolves rates from the effective (overridden or sourced) service area. The quote path resolves them from the anchor market only, and fails to assemble the response for a temporary rate when a source market is attached.
- **Conflicts with B10.** B10 recorded the opposite on a live quote: an Austin Mini Bus sourced into Dallas billed Dallas's $314.92/hr, not Austin's $244.09/hr, so the primary market supplies the rate. Here the primary market (Vancouver) has no Coach Bus rate, which would explain `rate_unavailable`. Which market's rate a sourced vehicle bills needs an engineering answer (acceptance criterion 3).
- Related: B10 and `GREEN-371` (sourcing), B9 (empty `issues[]`), G4 (no-local-provider warning), PRD R48–R51.

**Acceptance criteria**
1. `calculate_sourced_quote_units` returns a priced total for the Seattle Coach Bus into Whistler on profile 201890, consistent with the reservation UI.
2. `calculate_temporary_quote_units` with `source_market_ref` returns a priced quote, or an error that names the cause. `core_contract_violation` with empty `issues` no longer occurs.
3. Engineering states in writing which market's rate a sourced vehicle bills, and reconciles it with B10.
4. Minor: `as_directed` "Whistler, BC" resolves to a stop, and `resolve_vehicle_types` with query "motorcoach" returns Coach Bus (id 6).

---

## H5 — Allow quoting a quantity above Savoya's inventory
**Type:** Feature · **Priority:** High · **Status:** open · **Jira:** — · **PRD:** R95

**Problem statement**
Core returns `market_inventory_shortfall` when the requested quantity of a vehicle type exceeds the inventoried count. CSMs often confirm availability with vendors and can provide more than Savoya's inventory shows. Today they cannot get a priced quote for that quantity.

**Impact**
- A quote for more vehicles than the inventory shows cannot be produced from Core.
- Plugin workaround, in place until this ships: the plugin prices the largest quantity Core accepts, checks that the line total equals Core's `per_vehicle_total_amount` times the quantity, and extends the quantity only. The CSM's approval, the vendor statement and the shortfall message are recorded. The extended figure is not a Core-returned figure.
- Residual risk: Core might price the larger quantity differently from a straight multiple (a volume rule, for example). The plugin cannot see that.

**Steps to reproduce**
Yerdle Irvine, session `yerdle-irvine-mar20` on plugin 0.27.4, 2026-10-17. Pickup 2027-03-20 7:40am, 18000 Von Karman Ave to 6001 Oak Canyon, primary market Orange County, CA (service area id 11554). 80 passengers. Requested 7 x Mercedes Sprinter Van (vehicle type id 26, capacity 13). Core returned `market_inventory_shortfall` with 3 inventoried (as recorded in the session's workaround note; the verbatim response is not in the readable part of the capture).

One Sprinter, priced by Core:

```
unit_total 77154 (cents) · pricing_method hourly · billable_hours 2 · minimum_hours 2
base_rate_amount 50100 · effective_rate_amount 38577
discount_basis_points 3000 · fuel_surcharge_basis_points 1000
temporary_rate_used true · limited_availability true
```

The session multiplied that unit by 7 by hand (line total 540078 cents) and the CSM approved it in chat.

**Reference**
- Related: H4 and B10 (sourcing), G6 (large responses), PRD R48–R50, R54, R78, R92, R95.
- The CSM states the quantity, the vendor and who confirmed it; the plugin records that statement with the extension.

**Acceptance criteria**
1. Core accepts a requested quantity above inventory when the caller asserts vendor confirmation, and returns a priced quote.
2. The response carries `inventory_override` with `requested` and `inventoried`, at unit level and in the aggregate.
3. Core writes an audit record of the override: who asserted it, the vendor statement, the time.
4. Pricing at the larger quantity is Core's own calculation, so any quantity-dependent rule is applied.
5. The plugin workaround is removed when this ships.

---

## H6 — `display: show | internal` on `calculate_quote_units`
**Type:** Feature · **Priority:** High · **Status:** open · **Jira:** — · **PRD:** R105, R106

**Triage (2026-10-24):** with Ethan Ward. Does not block the plugin.

**Problem statement**
`preview_rate_batch` accepts `display`; `calculate_quote_units` does not and always renders the "Exact quote" card.

**Impact**
- A re-price is sometimes required: the pickup time depends on the drive time Core returns (PRD R18, R34). Yerdle Dallas leg 4 was priced at 15:40, 15:06, 15:08 and 15:07. Five cards rendered for one finished quote.
- Plugin meanwhile: accept an arrival window on the pickup rule (R105). Re-pricing only the units that depend on the time (R106) is deferred until engineering answers G6 and H6. One card still renders per re-price.

**Steps to reproduce**
Call `calculate_quote_units` with any quote unit. The tool schema has no `display` argument and the card renders.

**Reference**
- G6 (compact mode), H2 and H3 (card UI). The Savoya connector instruction already says to use `display=internal` for checks.
- Evidence: `Yerdle Dallas Noise Analysis 2026-10-18` in the vault project folder.

**Acceptance criteria**
1. `calculate_quote_units` accepts `display: show | internal`; default `show`.
2. With `internal`, no card renders and the response body is unchanged.

---

## B7b — No FBO resolver, so private flights are unreachable
**Type:** Feature · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R52

**Problem statement**
The flight object documents a private form that requires `private: true` plus `fbo` as a resolved object with an id. No tool resolves an FBO the user names.

**Impact**
- Private flights are specified and unreachable, as B7 describes for commercial ones.
- Taking the FBO out of a `nearby_airport` block would mean guessing that the FBO nearest the pickup is the one the client flies into. The quote integrity contract forbids that inference.

**Steps to reproduce**
Observed 2026-10-07. FBO ids exist and come back incidentally. `resolve_itinerary_stops` on an address near an airport returns them under `nearby_airport`:

```json
"nearby_airport": {
  "airport": {"id": 4655980, "iata_code": "SNA", "display_name": "SNA - John Wayne Arpt Orange Co"},
  "fbo": {"id": 111845, "name": "ACI Jet South", "airport_id": 4655980}
}
```

The ids are real. What is missing is a way to resolve an FBO by name. B7's original framing said private-flight FBO ids "are obtainable". That holds for the ids, not for resolution.

**Reference**
PRD R52. Sibling of B7. `QuoteBuilder` does not close it (see F5 note under B7).

**Acceptance criteria**
- [ ] Either an FBO resolver exists (name → id), or engineering confirms in writing that private flights stay out of scope. If out of scope, close as `wontfix`.
- [ ] If built: a quote with `private: true` and a named FBO succeeds.

---

## G4 — Quote response lacks the no-local-provider warning
**Type:** Feature · **Priority:** Medium · **Status:** open · **Jira:** GREEN-383 · **PRD:** R57

**Problem statement**
`resolve_itinerary_stops` returns the sourcing warning. The quote response does not. The quote response sets `excess_drive_time: true` instead. Both facts are needed.

**Impact**
- `excess_drive_time` says that extra drive time is billed. The warning says where the vehicle comes from. `excess_drive_time` alone cannot name the market, so a document built from the quote response can only say "a neighbouring market". A CSM looking at a 12-hour bill against an 8-hour request has nothing to tell the client.
- Plugin workaround: the disclosure fires from either signal and falls back to generic wording when the market is unnamed. The precise name is carried through the handoff from stop resolution. It is the only field the plugin carries across its own skill seam purely to cover a Core gap. It works only when intake and document run in the same conversation.
- Closing this retires that plugin state.

**Steps to reproduce**
Observed 2026-10-08. Resolve The Westin Whistler. The response has `service_area_source: "nearest"` and:

```json
"warnings": ["No local providers are available for this reservation. Availability will be
confirmed from our local providers in Vancouver, Canada. Additional drive time will be
incurred on the reservation."]
```

Run `calculate_temporary_quote_units` for the same stops. No such warning is returned and the stop's `service_area` is `null`. The only quote-side signal is `excess_drive_time: true`. `duration: 8` on the as-directed stop billed **12 hours**, 4 of them positioning, at $327.25/hr effective.

**Reference**
PRD R57. Sourcing work: `GREEN-371`.

**Acceptance criteria**
- [ ] The quote response carries the no-local-provider warning with the sourcing market named.
- [ ] Engineering confirms the signals co-occur: no local provider → sourced from another market → excess drive time applies.

---

## G1 — `greeter_fee` fields exist but no tool can set them
**Type:** Decision · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R36

**Problem statement**
Every vehicle's `quote` object carries four greeter-fee fields. They are always empty, and no pricing tool has an argument that sets them. Core may hold a second greeter model: a fee on an ordinary vehicle's quote, beside the separate greeter unit the plugin builds.

**Impact**
- Nothing is blocked. The plugin prices greeters as their own quote units on vehicle types 12 (Hourly Greeter/Coordinator) and 13 (Single Greet). Shipped in 0.23.0.
- If the fee route is the intended one, a greeter priced as its own unit may be invisible to whatever downstream reads `greeter_fee`, and the two models would disagree about what a booking with a greeter costs.

**Steps to reproduce**
Observed 2026-10-07, confirmed 2026-10-08. Read any vehicle's `quote`:

```json
"quote": {
  "greeter_fee": null,
  "adjusted_greeter_fee": null,
  "greeter_fee_in_vendor_currency": 0,
  "adjusted_greeter_fee_in_vendor_currency": 0
}
```

The same shape appears on all five document fixtures, including `boston-offsite/raw_quote.json`, an ordinary Mini Bus unit with no greeter. `calculate_quote_units`, `generate_quote_options` and `calculate_temporary_quote_units` accept no greeter fee argument.

Greeter-as-unit pricing for comparison: Core priced id 12 in Orange County at rate 55549, $100.00/hr rack → **$76.99/hr** effective with a 2-hour minimum. An Irvine request came to **$404.20**.

**Reference**
- Folded in: **G5** (same observation filed twice) and **F7**. F7 noted that `VehicleTypeSearch` returns greeter metadata but the inventory prices no greeter service (R36 listed "Not implemented … greeter rates and add-on pricing are excluded"). Answered in part 2026-10-10: greeters price as Core quote units, so they are not a manual line item.
- Unanswered from B8: what `greeter_required` on the airport object drives (informational, pricing or dispatch). Ask alongside this item.

**Acceptance criteria**
- [ ] Engineering states which model is intended: a separate greeter quote unit, or a fee on the vehicle's quote.
- [ ] If the fee: which tool sets it.
- [ ] If the unit: the fee fields are documented as unused.

---

## G2 — `client_can_book` missing from rate-preview `presentation` rows
**Type:** Defect · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R70

**Problem statement**
In one `preview_rate_batch` response, `client_can_book` appears in `previews[].result.vehicle_rate_evaluations[].vehicle_type` but not in `presentation.data.groups[].rows[]`.

**Impact**
The rate sheet a CSM reads does not say a Mini Bus cannot be booked by the client, though Core has it in the same payload.
Plugin workaround: read it from `resolve_vehicle_types` at the vehicle-selection step. The plugin does not enrich Core's presentation block from the evaluations, because mixing sources into that block is how a rendered view drifts from what Core sent.

**Steps to reproduce**
Observed 2026-10-08. Same response, same vehicle. In the evaluation:

```json
"vehicle_type": {"id": 7, "name": "Mini Bus", "capacity": 41,
                 "limited_availability": true, "client_can_book": false,
                 "classification": "other", "bus": true, "greeter": false}
```

In the presentation row:

```json
{"vehicle_type_id": "7", "vehicle_name": "Mini Bus", "vehicle_capacity": 41,
 "market_vehicle_count": 10, "limited_availability": true,
 "availability": "available", "minimum_hours": 5, "cancellation_hours": 72, …}
```

`limited_availability` made it across. `client_can_book` did not.

**Reference**
PRD R70. See also F8.

**Acceptance criteria**
- [ ] `client_can_book` appears in `presentation.data.groups[].rows[]`, or engineering confirms the omission is deliberate.
- [ ] Mini Bus (id 7) shows `client_can_book: false` in the presentation row for the response above.

---

## G3 — `temporary_rate_used` is `false` at aggregate level while the unit says `true`
**Type:** Defect · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** —

**Triage (2026-10-24):** with Ethan Ward. Does not block the plugin.

**Problem statement**
A `calculate_temporary_quote_units` call with an explicit temporary rate returns contradictory flags in one response.

**Impact**
A consumer that reads the aggregate flag to decide whether a quote contains unsaved pricing gets the wrong answer. The document layer checks that flag before printing "temporary rate, not saved" on a client-facing page.
Plugin workaround: read the unit-level flag, never the aggregate.

**Steps to reproduce**
Observed 2026-10-08. Call `calculate_temporary_quote_units` with an explicit temporary rate. Unit level, correct:

```json
"adjustments": {"discount_basis_points": 3000, "fuel_surcharge_basis_points": 1000,
                "temporary_rate_used": true}
```

Presentation aggregate, same response:

```json
"presentation": {"data": {"pricing": {"adjustments": {"temporary_rate_used": false}}}}
```

The per-unit presentation entry also carries `"temporary_rate_used": true`. Only the top-level aggregate is wrong.

**Reference**
Temporary rate: PRD R34.

**Acceptance criteria**
- [ ] The aggregate `temporary_rate_used` is `true` when any unit used a temporary rate, or engineering documents what it means instead.
- [ ] The call above returns matching flags at unit and aggregate level.

---

## B9 — `quote_units_unavailable` returns an empty `issues[]`
**Type:** Defect · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R34

**Problem statement**
A unit that cannot be priced returns `quote_units_unavailable` with no detail on which unit or vehicle failed.

**Impact**
- With one unit, the recovery is to re-quote another vehicle. With sixteen (a World Cup shuttle programme) there is no way to tell which unit or vehicle caused it. The only recovery is to bisect the payload.
- A vehicle that fails inside a priced unit is reported precisely: `vehicle_options[].failure.code = "rate_unavailable"` with a per-vehicle message. The whole-unit path loses that detail.
- Plugin workaround: say the market has no stored rate for that vehicle, and offer a different vehicle or a user-supplied temporary base rate (PRD R34). Adequate for the no-rate case. For every other cause the plugin cannot tell them apart.

**Steps to reproduce**
Quote a unit that cannot be priced. Response:

```json
{"error_type": "quote_units_unavailable", "core_status": 422,
 "client_error": {"code": "quote_units_unavailable", "category": "availability"},
 "presentation": {"data": {"issues": []}}}
```

**Update 2026-10-25:** a second session shows the cost. An Actian World Cup request (32 units, one SUV type, 13 passengers) returned `quote_units_unavailable`, `core_status` 422, `issues: []` twice (request ids `cefbd6c9-b9a7-4ef1-886a-4321c836ced1` and `004c421a-fe93-4cd6-8e9e-5a789ac324a9`). The cause was the four origin stops, which were town and area points (see J1); nothing in the response said so, and it took a second session to find it by re-pricing with street addresses (all 32 units priced, $65,056.50). A populated `issues[]` naming the unit and the stop would have shown it at once.

**Reference**
PRD R34, R123. Related: G6 (16-unit packages), J1.

**Acceptance criteria**
- [ ] `issues[]` is populated with the unit key and the per-vehicle failure reasons the priced path already produces.
- [ ] A 16-unit request with one unpriceable unit identifies that unit in the response.
- [ ] When the cause is a stop Core cannot price, `issues[]` names the stop (`stop_ref`) as well as the unit.

---

## F8 — Greeters are silently missing from the rate sheet
**Type:** Feature · **Priority:** Medium · **Status:** open · **Jira:** GREEN-384 · **PRD:** R24

**Problem statement**
Greeter vehicle types (ids 12 and 13) do not appear in `vehicle_rate_evaluations` and are not listed in `missing_vehicle_type_ids`. The rate sheet is silently incomplete instead of reporting a gap.

**Impact**
- The rate sheet cannot answer the greeter question at all. A CSM reading it cannot tell whether a greeter is unrated or simply not shown.
- Plugin workaround: attempt a price and read the answer.

**Steps to reproduce**
Run `preview_rate_batch` for a market where greeter types 12 and 13 are priceable (Orange County, see G1). Neither id appears in `vehicle_rate_evaluations` or `missing_vehicle_type_ids`.

**Reference**
- PRD R24 (rate-sheet completeness). Origin: `RateDiscoveryBuilder`'s limitations list and the R23–R25 coverage row.
- Narrowed 2026-10-11 by Ayush: the explicit discount indicator was dropped. The rate line already shows the discount and fuel surcharge when they apply.
- Already resolved by observation: `market_vehicle_count` is present in presentation rate rows (static count, not date-specific availability). Closes PRD R25.
- No-client rates: see F4. `client_can_book` omission: see G2.

**Acceptance criteria**
1. Greeter vehicle types appear in `vehicle_rate_evaluations`, or are listed in `missing_vehicle_type_ids` when unrated.
2. A greeter type with no inventory returns a short status without rendering a quote card. A greeter attempt in a market with zero inventory (`market_inventory_shortfall`, DFW 2026-11-12, `available_vehicle_count` 0) currently renders a card for each attempt; the plugin makes two (type 13, then 12). Added 2026-10-18.

---

## H1 — Austin rate sheet shows Mini Bus quantity 1 where the service area lists 4
**Type:** Defect · **Priority:** Medium · **Status:** open · **Jira:** GREEN-385 · **PRD:** R25

**Problem statement**
The rate sheet for the Austin market shows a Mini Bus quantity of 1. The Austin service area's own vehicle tab lists 4 Mini Buses.

**Impact**
- The market vehicle count in the rate sheet understates inventory.
- The plugin checks primary-market inventory before an exact quote and sends the CSM to nearby-market sourcing when inventory is short. If that check reads the same count, a short count sends the CSM to sourcing the request does not need. Unconfirmed: which field the check reads.
- Plugin workaround: none.

**Steps to reproduce**
Raised 2026-10-11 by Ayush.
1. In Savoya, go to Locations, then the Austin service area, then the Vehicle tab.
2. Search for "Mini Bus". 4 are listed.
3. Check the rate sheet for Austin. Mini Bus is listed with quantity 1.

**Reference**
`market_vehicle_count` in the presentation rate rows (PRD R25, noted as a static count) is probably the field. Unconfirmed.

**Acceptance criteria**
1. The Austin rate sheet shows the same Mini Bus quantity as the service area's vehicle tab (4), or engineering documents which filter makes the two differ.
2. Engineering says whether other vehicle types and markets show the same difference.

---

## H2 — Hide the action buttons on quote and quote-option cards in the chat UI
**Type:** Feature (UI) · **Priority:** Medium · **Status:** open · **Jira:** GREEN-386 · **PRD:** —

**Problem statement**
The Savoya embed shows buttons in the chat UI whenever quote options and/or a quote are presented, for example "Refine this quote".

**Impact**
- The plugin workflow already asks the user the right questions, in order. The buttons offer a second path that can confuse the user.
- Plugin workaround: none.
- The buttons may come back later, so they are to be hidden, not removed.

**Steps to reproduce**
Raised 2026-10-11 by Ayush.
1. In a Claude chat with the Savoya MCP connected, request a quote.
2. Look at the quote card and at the quote-options card. Buttons appear on both (the quote card shows "Refine this quote").

**Reference**
Screenshot of the quote card (Mineola to MetLife, 10 travelers, tooltip "savoya embed"). Attach to the ticket.

**Acceptance criteria**
1. No buttons are displayed on the quote card or the quote-options card in the chat UI.
2. The buttons are hidden, not deleted, so they can be shown again without rebuilding them.
3. Quote data and the plugin workflow are unaffected.

---

## H3 — Hide the "No passenger was selected" warning in the chat UI
**Type:** Task (UI) · **Priority:** Medium · **Status:** open · **Jira:** GREEN-387 · **PRD:** —

**Problem statement**
Almost every quote option and quote shows this warning under "Important details": "No passenger was selected. Savoya attached an eligible passenger only to calculate this unsaved quote; the passenger selection was not saved".

**Impact**
- A quote does not depend on the passenger, so the warning is immaterial. It appears on nearly every quote and adds noise.
- Plugin workaround: none. The plugin no longer picks a passenger and removed its own disclosure (B1, resolved).

**Steps to reproduce**
Raised 2026-10-11 by Ayush.
1. In a Claude chat with the Savoya MCP connected, request a quote without naming a passenger.
2. Look at the "Important details" block on the quote card. The warning is the first bullet.

**Reference**
- Screenshot of the quote card. Attach to the ticket.
- B1 (resolved): `passenger_id` is optional and Core attaches an eligible passenger and says so in a warning.
- The second bullet in the screenshot, "Temporary user-supplied discount was used for this quote and was not saved in Savoya", stays.

**Acceptance criteria**
1. The "No passenger was selected" warning is not displayed.
2. Other "Important details" warnings still display, including the temporary-discount warning.
3. The warning is hidden, not deleted, so it can be shown again.

---

## C1 — `as_directed` city lookup fails on state abbreviations
**Type:** Defect · **Priority:** Low · **Status:** open · **Jira:** — · **PRD:** —

**Problem statement**
`"Dallas, TX"` returns no candidates. `"Dallas, Texas"` works. Results also include nearby cities (Lake Dallas, Cedar Hill) with no obvious ranking.

**Impact**
Plugin workaround: always query `"<City>, <State spelled out>"` and pick the candidate whose id matches the pickup's city id. Deterministic, asks only if none matches. Written into the decision tree. Cost is low.

**Steps to reproduce**
Run an `as_directed` city lookup for `"Dallas, TX"`, then `"Dallas, Texas"`.

**Reference**
Decision tree.

**Acceptance criteria**
- [ ] Standard state abbreviations are accepted, or the expected format is documented.

## I1 — Structured record when a CSM overrides inventory
**Type:** Feature · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R95

**Triage (2026-10-24):** with Ethan Ward. Does not block the plugin.

**Problem statement**
`inventory_override` (H5) prices a quantity above inventory. The response says so only in warning text: the counts sit inside a sentence, and nothing says who overrode or when.

**Impact**
- A consumer that needs the counts has to parse the sentence, which breaks when the sentence changes.
- Whether Core keeps an audit of overrides is not known.
- Plugin meanwhile: no reason is asked (R95) and the warning reaches the CSM as Core wrote it.

**Steps to reproduce**
Observed 2026-10-24, Yerdle, Orange County, 7 Mercedes Sprinter Vans on 2027-03-20, with `inventory_override`. In `presentation.warnings`:

```json
{"severity": "warning", "message": "Inventory override: Orange County, CA has 3 inventoried Mercedes Sprinter Van vehicles; 7 requested."}
```

The unit carries `"quantity": 7`, `"requested_quantity": 1`, `"required_quantity": 7`. No field names the market, the inventoried count or the override.

**Reference**
H5 (GREEN-389), PRD R95. Capture `yerdle-irvine-transfers` in the shared Drive folder, 2026-10-24.

**Acceptance criteria**
- [ ] A unit that used an override carries a structured field with the service area, vehicle type, inventoried count and requested count.
- [ ] Engineering states whether Core records who overrode and when.

---

## I2 — A `greeter` flag on quote view units
**Type:** Feature · **Priority:** Low · **Status:** open · **Jira:** — · **PRD:** —

**Triage (2026-10-24):** with Ethan Ward. Does not block the plugin.

**Problem statement**
A quote view unit carries the vehicle's id, name and capacity, and no flag for a greeter. A greeter drives nowhere, so no drive time may print for it (D1). The plugin tells a greeter from a vehicle by looking for "greet" in the vehicle name.

**Impact**
- A greeter vehicle renamed in Savoya without that word would print a drive time.
- Plugin meanwhile: the name match. It works for "Hourly Greeter/Coordinator".

**Steps to reproduce**
Observed 2026-10-24. Fields on a unit in `presentation.data.quote_units`:

```json
"vehicle_type_id": "26", "vehicle_name": "Mercedes Sprinter Van", "vehicle_capacity": 13
```

Nothing on the unit says whether the vehicle is a greeter.

**Reference**
PRD D1 (greeter leg). Capture `yerdle-irvine-transfers`.

**Acceptance criteria**
- [ ] Each unit carries a boolean that is true for a greeter and false otherwise.

---

## I3 — A street-only address on quote view stops
**Type:** Feature · **Priority:** Low · **Status:** open · **Jira:** — · **PRD:** —

**Triage (2026-10-24):** with Ethan Ward. Does not block the plugin.

**Problem statement**
A stop's `address` in the quote view is Core's full display name, with city, state and country. The street is already in `label` when the user typed an address, so the client document repeats it.

**Impact**
- A stop line in the client document reads `18000 Von Karman Ave · 18000 Von Karman Avenue, Irvine, California, US`.
- Plugin meanwhile: prints both. Nothing is wrong, the street is repeated.

**Steps to reproduce**
Observed 2026-10-24, stop 1 of Transfer 1:

```json
"label": "18000 Von Karman Ave", "address": "18000 Von Karman Avenue, Irvine, California, US"
```

**Reference**
Capture `yerdle-irvine-transfers`.

**Acceptance criteria**
- [ ] Each stop carries a street-only field beside `address`, and engineering states which of the two is meant for a client document.

## I4 — The server tells the model to pick a location itself when Core asks for confirmation
**Type:** Defect · **Priority:** Medium · **Status:** open · **Jira:** — · **PRD:** R83

**Triage (2026-10-25):** with Ethan Ward. Does not block the plugin, which now stops and asks the CSM whichever way the server words it.

**Problem statement**
`resolve_itinerary_stops` can return `status: "blocked"`, `error_type: "location_confirmation_required"` with every stop `needs_confirmation`. The text that comes with it tells the model to choose a candidate and mention it afterwards, so a model that follows the tool text picks the stops for the CSM.

**Impact**
- A CSM can receive a quote priced at points the model chose, including a candidate in another market, without being asked. Reported 2026-10-25 on a Yerdle World Cup request: all five stops came back `needs_confirmation`, the session chose among the candidates and wrote "The stops resolved" to the user. One candidate for White Plains was `New York State Thruway, Waterloo`, in the Rochester market, with the warnings "No local providers" and "City inferred from nearest same-country city… confirm this location before quoting".
- Plugin meanwhile: stop and ask the CSM before any pricing call (R83 amendment). Plugin instructions cannot change what the tool text says.

**Steps to reproduce**
Wording as shipped in `src/domains/quotes/locationGuidance.ts` (branch `main`, read 2026-10-25):

```
LOCATION_SELECTION_GUIDANCE: "…Multiple candidates alone do not require confirmation; use the user's stated city and other trip details to identify the intended match. Ask only about unresolved locations and wait for their choice…"
LOCATION_RECOVERY_GUIDANCE:  "Keep valid tickets and trip facts. Select an obvious equivalent returned candidate and disclose the assumption, or ask about material differences. Use its unchanged stop_ref and stop_type…"
```

and in `presentation.ts`, for `location_confirmation_required`: message "We found more than one possible match for a required location.", next action "Please confirm the intended location before continuing."

The two texts disagree: Core required confirmation, the recovery text says to select.

**Update 2026-10-25:** the same recovery text appeared again in an Actian World Cup session: `next_action` "Select an obvious equivalent returned candidate and disclose the assumption, or ask about material differences." came back with `location_confirmation_required` for the MetLife stop (two candidates, one `id`, one address) and again for four town-named origins. The Actian session did ask the user; the picks it offered were town and area points that Core then could not price (J1).

**Reference**
Report: Yerdle World Cup session, 2026-10-25, plugin 0.27.6. The five queries and their candidates are in the brief `Savoya-Plugin-Fixes-Brief-Stops-Capture-Discount.md`.

**Acceptance criteria**
- [ ] When a stop is `needs_confirmation`, the text returned with it tells the model to ask the user to choose and to wait, and no longer says to select a candidate.
- [ ] Candidates in a different service area from the rest of the itinerary are flagged in the response itself.

## J1 — Town and area points come back as selectable stop candidates that Core cannot price
**Type:** Defect · **Priority:** High · **Status:** open · **Jira:** — · **PRD:** R122, R123

**Problem statement**
`resolve_itinerary_stops` returns town-level and area-level points ("White Plains town point", "Midtown Manhattan area point", "Newark town point", "Garden City town point") as ordinary candidates for an `address` stop. Pricing a unit with one of those points as a stop fails with `quote_units_unavailable` (Core 422, empty `issues`, see B9). Nothing in the candidate says it is town-level: it carries a `loc_` reference and a service area like any other.

**Impact**
- A CSM who has no final address, which is the normal case for a pickup "in White Plains, to be confirmed", is offered a point that cannot be quoted. The Actian World Cup session (32 units) priced twice on four such points and got no quote.
- The same unit, vehicle, client, rate and destination priced once the four origins were street addresses: hourly rack rate 52354, $237/hr base plus 20% fuel, 2-hour minimum, $65,056.50 for all 32 units.
- Plugin meanwhile (R122, R123): offer a civic-building street address per town, never price a candidate with no street number, retry with different references. The street-number test is a stand-in; the plugin cannot see whether a point is town-level.

**Steps to reproduce**
Sent through `resolve_itinerary_stops`, stop type `address`: "White Plains, New York", "Midtown Manhattan, New York, New York", "Newark, New Jersey", "Garden City, New York". All four came back `needs_confirmation` with a town or area point first (`loc_246a9a4895b4ff9c6fbbcb81`, `loc_0dcfe0c4b40596f916acdd38`, `loc_c0414aef6471d354fe21e830`, `loc_4688edd5e0f04f7dadeeedc0`), all in the New York City, NY service area (id 11198). Priced as stops in `calculate_quote_units` with SUV (type 8), `passenger_count` 13, profile 201932: `quote_units_unavailable`, `issues: []`.

Street addresses for the same four towns (255 Main Street, White Plains, NY 10601; 20 West 34th Street, New York, NY 10001; 920 Broad Street, Newark, NJ 07102; 351 Stewart Avenue, Garden City, NY 11530) each resolved with one candidate and priced.

**Reference**
Report: Actian World Cup session, 2026-10-25, plugin 0.27.6, feedback document "Savoya Quoting Plugin: Location Confirmation Feedback". Related: B9, I4.

**Open questions for Ethan**
- Does Core price town-level or area-level points for transfers at all? If not, the lookup should not offer them for pricing.
- Can the lookup return a street-address placeholder for a town on request?

**Acceptance criteria**
- [ ] Each candidate says whether it is a street address, a venue, or a town or area point, in a field the plugin can read.
- [ ] A town or area point is either not returned as a candidate for an `address` stop, or is marked as not priceable.
- [ ] `quote_units_unavailable` for a stop of that kind names the stop (B9).

---

---

---

# Deferred

Deferred means a workaround ships, the item waits on a product decision, or Ayush has parked it. Nothing here blocks the pilot.

## F1 — What does Auth0 add over today's per-CSM OAuth?
**Type:** Decision · **Priority:** High · **Status:** deferred · **Jira:** GREEN-354 · **PRD:** NFR-2
**Deferred because:** Ayush, 2026-10-11: the Auth0 flow will be built later.

**Problem statement**
The plugin already authenticates each CSM individually: `README.md` says "OAuth via `dev.auth.savoya.net`, scope `access:savoya_mcp` … sign in with your Savoya account". It is a public PKCE client shared by all installations, not a single shared identity. `Api::V1::QuoteBuilderController` "uses the authenticated Savoya user, limits access to internal roles", so it is also per-user. The change Auth0 brings is not stated.

**Impact**
Auth design for the plugin waits on the answer. F10 depends on it.

**Steps to reproduce**
N/A, decision item. Source: `quote-builder-core-change-inventory.md` (Ethan Ward), cross-checked 2026-09-20 against the shipped plugin. Not from a live session.

**Reference**
F10 (same question from the authorization side). Umbrella ticket `GREEN-354`.

**Acceptance criteria**
- [ ] A written answer, in this item, naming which applies: (a) a different kind of end user, such as the client-side recipient; (b) an infrastructure migration off `dev.auth.savoya.net`; (c) something else.
- [ ] The answer states what changes for the plugin's sign-in flow, or that nothing does.

---

## F2 — MCP tool surface vs. `QuoteBuilder`: replacement or parallel?
**Type:** Decision · **Priority:** High · **Status:** deferred · **Jira:** GREEN-354 · **PRD:** —
**Deferred because:** Ayush, 2026-10-11: the `QuoteBuilder` service is abandoned for now. Savoya enhanced the existing services instead.

**Problem statement**
The inventory is explicit that it covers "Core changes only; MCP and connector code are excluded". It does not say whether `Api::V1::QuoteBuilderController` becomes what the MCP server calls internally (invisible to the plugin) or whether the plugin and MCP would be rewritten to call it directly.

**Impact**
- Sets how much of the shipped plugin survives unchanged. The unit-structuring rules, the decision tree, `handoff.py` and the F3 and B7 workarounds are all written against today's MCP tool surface.
- Evidence added 2026-10-10:
  1. Cross-market sourcing landed on the MCP tool surface, not in `QuoteBuilder`. Three tools were added (`lookup_nearby_markets`, `calculate_sourced_quote_units`, `resolve_service_areas`) and two removed (`plan_approximate_quote_units`, `calculate_quote_options`), with no `QuoteBuilder` involvement and no mention in the inventory. That points to "parallel", but it was never stated as a decision.
  2. The approximate path diverged. The plugin removed it entirely: the tool is gone from the contract and a guard fails the build if any file names it. The inventory is still building `QuoteBuilder::ApproximateQuotePlanner`. If the plugin is `QuoteBuilder`'s consumer, that service has no consumer. If it is not, the two layers are being built to different pricing philosophies.

**Steps to reproduce**
N/A, decision item. Source as F1.

**Reference**
F3, F11 and F1 follow from the answer. Umbrella ticket `GREEN-354`.

**Acceptance criteria**
- [ ] A stated decision: `QuoteBuilder` replaces the MCP surface, or runs parallel to it.
- [ ] A stated answer to: who is `ApproximateQuotePlanner` for?

---

## F3 — Does `QuoteBuilder`'s exact path require a resolved passenger?
**Type:** Decision · **Priority:** Medium · **Status:** deferred · **Jira:** GREEN-354 · **PRD:** —
**Deferred because:** Ayush, 2026-10-11: `QuoteBuilder` is abandoned for now (see F2).

**Problem statement**
On the MCP side `passenger_id` is now optional on every pricing tool, and Core attaches an eligible passenger to the unsaved calculation (see B1, resolved). `QuoteBuilder::PassengerSearch` is new, but the inventory does not say whether `EstimateOptionsBuilder` / `QuoteUnitsEstimator` still require selecting one.

**Impact**
If the `QuoteBuilder` exact path still requires a passenger, the workaround B1 retired (take the first passenger on the profile) comes back on migration.

**Steps to reproduce**
N/A, decision item. Source as F1.

**Reference**
B1 (resolved). Depends on F2.

**Acceptance criteria**
- [ ] Engineering confirms whether the `QuoteBuilder` exact path requires a passenger.
- [ ] If yes: the requirement is recorded as intentional so it is not re-flagged as a bug in each review.

---

## F10 — NFR-2 permission granularity, never tested
**Type:** Decision · **Priority:** Medium · **Status:** deferred · **Jira:** GREEN-354 · **PRD:** NFR-2
**Deferred because:** Ayush, 2026-10-11: deferred with F1, whose answer settles it.

**Problem statement**
The inventory lists NFR-2 as open: "Confirm whether a more specific existing permission is required". `QuoteBuilderController` allows any internal role. PRD NFR-2 ("a user only sees and prices what their role allows") has not been tested on any path. It is the only PRD requirement with no evidence in either direction.

**Impact**
The plugin inherits whatever the connector grants and cannot check it from inside.

**Steps to reproduce**
N/A, decision item. A restricted-role test account would settle it.

**Reference**
Same underlying question as F1, from the authorization side. The answer to F1 probably settles this.

**Acceptance criteria**
- [ ] Engineering states whether a permission narrower than "any internal role" is required.
- [ ] A restricted-role test account exists, NFR-2 is tested on the MCP path with it, and the result is recorded here.

---

## F11 — Plugin cutover plan once `QuoteBuilder` ships
**Type:** Decision · **Priority:** Medium · **Status:** deferred · **Jira:** GREEN-354 · **PRD:** —
**Deferred because:** Ayush, 2026-10-11: concerns cutover to `QuoteBuilder`, which is abandoned for now (see F2).

**Problem statement**
The inventory lists regression-test priorities (reservation creation, stop validation, `/airports/nearby` parity, rate precedence, exact-quote parity) and nothing about how the plugin cuts over: dual-support period, per-CSM feature flag, or a hard swap when `enable_quote_builder_api` flips on.

**Impact**
The TDD's architecture is treated as a moving target until a shape is known. The handoff contract between the two skills is at v3 and rejects an older handoff. If a migration changes the response shape, the contract versions again, and a CSM mid-quote at cutover gets "re-run the quote". That is correct behavior and worth planning for.

**Steps to reproduce**
N/A, decision item.

**Reference**
Depends on F2.

**Acceptance criteria**
- [ ] A rough cutover shape is written here, even "not decided, will decide by <date>".
- [ ] The handoff-contract version impact is stated.

---

## D1 — Yerdle Sedan transfer rate $990 against rack $99
**Type:** Data fix · **Priority:** Medium · **Status:** deferred · **Jira:** — · **PRD:** R34
**Deferred because:** Ayush, 2026-10-11: seen in the test environment. The check will be done in production.

**Problem statement**
On the Yerdle profile, the Sedan `CompanyTransferRate` is **$990** against a rack rate of **$99** for the same Irvine→Irvine transfer. It looks like a decimal slip.

**Impact**
A quote for that transfer prices 10× rack. Rate-data issues surface to the user as "no stored rate" or a wrong rate. For missing rates, a CSM supplies a temporary base rate and Core prices from it (PRD R34). That conversation carries its own risk: a CSM who enters a partner's cost instead of a quoting rate goes out about 23% low (the original cites A2/A3 for this figure and neither contains it).

**Steps to reproduce**
Quote a Sedan Irvine→Irvine transfer on the Yerdle profile. Compare `CompanyTransferRate` with rack.

**Reference**
D3, D4 (same class of problem).

**Acceptance criteria**
- [ ] The rate is corrected, or confirmed intentional in writing.
- [ ] A sweep for other company rates at a similar multiple of rack is run and the hits are listed here.

---

## D3 — Chicago Mini Buses have no rates
**Type:** Data fix · **Priority:** Medium · **Status:** deferred · **Jira:** — · **PRD:** R34
**Deferred because:** Ayush, 2026-10-11: seen in the test environment. The check will be done in production.

**Problem statement**
Chicago has 8 Mini Buses in market inventory and no rates at all, hourly or transfer.

**Impact**
Mini Bus quotes in Chicago are unquotable without a user-supplied temporary base rate.

**Steps to reproduce**
Run `preview_rate_batch` for Chicago with the Mini Bus vehicle type. Neither hourly nor transfer rates return.

**Reference**
D1, D4.

**Acceptance criteria**
- [ ] Hourly and transfer Mini Bus rates exist for Chicago, or the Mini Bus is removed from Chicago inventory.

---

## D4 — Executive Van unrated in most markets
**Type:** Data fix · **Priority:** Medium · **Status:** deferred · **Jira:** — · **PRD:** R34
**Deferred because:** Ayush, 2026-10-11: seen in the test environment. The check will be done in production.

**Problem statement**
Executive Van is unrated in most markets touched so far: Orange County, NYC (before a rate was added) and Boston.

**Impact**
Executive Van quotes in those markets need a user-supplied temporary base rate.

**Steps to reproduce**
Run `preview_rate_batch` for Orange County or Boston with the Executive Van type. It returns no stored rate.

**Reference**
D1, D3.

**Acceptance criteria**
- [ ] Executive Van rates are added per market, or engineering confirms in writing which markets are intentionally unrated.
- [ ] A list of markets without an Executive Van rate is attached.

---

## F6 — Mixed-fleet quoting within one movement
**Type:** Decision · **Priority:** Medium · **Status:** deferred · **Jira:** — · **PRD:** R19, R21
**Deferred because:** a product decision. The engine already covers mixing across legs.

**Problem statement**
`QuoteUnitsEstimator` "compares homogeneous options only … does not generate mixed fleets" and `ApproximateQuotePlanner` "does not generate mixed-vehicle combinations". A mixed fleet **within one movement** (2 SUVs plus 1 Sprinter on a single leg) is absent. That is what PRD R21 asks for at full strength.

**Impact**
- Multi-vehicle programs cannot be represented with mixed vehicles inside one leg.
- Softened on the MCP side: `generate_quote_options` accepts 2–5 named options, and Core sizes and picks the cheapest candidate per unit, so a value option may mix vehicle types across legs. R21 is otherwise unblocked.

**Steps to reproduce**
N/A, decision item. Source: change inventory, 2026-09-20.

**Reference**
PRD R19 (manifest grouping), R21.

**Acceptance criteria**
- [ ] Engineering confirms within-leg mixed fleets are a later phase or permanently out of scope for the chosen API shape.

---

## F9 — International stop-resolution policy
**Type:** Decision (Ayush, not engineering) · **Priority:** Medium · **Status:** deferred · **Jira:** — · **PRD:** R15, R57
**Deferred because:** a product decision sitting in an engineering document. Found in Ethan's inventory and not his to answer.

**Problem statement**
The inventory says: `StopResolution::Resolver` "Product still needs to define when an inferred international service area is acceptable", and `GooglePlacesClient`'s international city matching "need[s] production fixtures".

**Impact**
- The real boundary is covered / nearest-market / nothing at all. Only the first two were in the policy question.
- Observed 2026-10-10: a London/Sicily/Milan itinerary resolved with **Sicily in no Savoya service area at all**. Core reported one market as both source and primary for those stops and priced them from Naples, billing **14.75 hrs** against a shorter request. The plugin handles and discloses it (PRD R57). It is not a defect.

**Steps to reproduce**
Resolve a London/Sicily/Milan itinerary with `resolve_itinerary_stops` and quote it.

**Reference**
PRD R15, R57.

**Acceptance criteria**
- [ ] Ayush records a policy for when an inferred international service area is acceptable.
- [ ] The policy states how far a nearest-market fallback reaches before a request is refused rather than priced.

---

## B2 — Passenger pool scope
**Type:** Decision · **Priority:** Low · **Status:** deferred · **Jira:** — · **PRD:** —
**Deferred because:** downgraded Medium → Low on 2026-10-10. The plugin no longer picks a passenger.

**Problem statement**
`resolve_passengers` takes only `travel_coordination_profile_id`. Unknown: (a) whether the pool is per TC profile or per company (the Yerdle company has four Ayush profiles), and (b) what happens on a new profile with no passengers.

**Impact**
Both halves of the original concern are obsolete. `passenger_id` is optional (B1, resolved) and there is no approximate path to drop to (A1, resolved). `QuoteBuilder::PassengerSearch` removes the 10-passenger cap. The question survives only when a user names a passenger.

**Steps to reproduce**
Call `resolve_passengers` for each of the four Yerdle Ayush profiles and compare the pools.

**Reference**
B1, A1 (resolved).

**Acceptance criteria**
- [ ] Engineering states whether the pool is per TC profile or per company.
- [ ] Engineering states the behavior for a profile with zero passengers.

---

## B4 — `scenario_comparison` hides data the payload carries
**Type:** Feature · **Priority:** Low · **Status:** deferred · **Jira:** — · **PRD:** —
**Deferred because:** a workaround shipped. Downgraded Medium → Low on 2026-10-10.

**Problem statement**
The `scenario_comparison` widget renders a condensed card. The `quote_result` widget renders base rate, effective rate, discount %, billable time and cancellation as tiles. `generate_quote_options`' payload already contains all of those fields, plus `minimum_hours`, which `calculate_quote_units` does not return.

**Impact**
`render_presentation.py` prints Core's own `presentation` block, so every CSM sees the same view of the same quote with Core's figures, and falls back to the plugin's summarizer when a response has no presentation block. The widget's omissions are no longer load-bearing. A second `calculate_quote_units` call is still made (node G2) purely to render the detailed card. That saving is still available.

**Steps to reproduce**
Run `generate_quote_options` and compare the `scenario_comparison` widget with the payload.

**Reference**
Decision-tree node G2.

**Acceptance criteria**
- [ ] The comparison view shows the payload's base rate, effective rate, discount %, billable time, cancellation and `minimum_hours`, or each scenario is expandable to them.

---

## C2 — Stop-ref TTL undocumented
**Type:** Feature (documentation) · **Priority:** Low · **Status:** deferred · **Jira:** — · **PRD:** —
**Deferred because:** partly answered by observation, 2026-10-10.

**Problem statement**
The stop-ref lifetime is observed at about 24 hours and not documented.

**Impact**
The plugin re-resolves after 24 hours and relies on "stop refs live ~24h" when a user asks for a rate sheet later in a conversation. A measured number stands in for a specified one. A sourcing `market_ref` has its own expiry and a documented recovery path (`sourcing_reference_expired` → look up again from the same reference market and swap each ref). The stop ref should be as clear.

**Steps to reproduce**
Resolve a stop, wait past 24 hours, reuse the ref in a pricing call.

**Reference**
`sourcing_reference_expired` recovery path.

**Acceptance criteria**
- [ ] The official TTL is documented.
- [ ] The expiry error and recovery path for a stop ref are documented.

---

## E1 — Host quote documents at a Savoya URL
**Type:** Feature · **Priority:** P3 · **Status:** deferred · **Jira:** — · **PRD:** —
**Deferred because:** a feature request, not a defect. The access model must be settled before any code, because it drives the data model. B7 comes first.

**Problem statement**
The plugin produces a complete self-contained HTML quote document (single file, images inlined, prints to a byte-identical PDF). A CSM can only attach it. There is nowhere to point a link.

**Impact**
- Corporate mail filters routinely strip or warn on `.html` attachments. BCD, ExxonMobil and Ritz-Carlton are recipients whose IT does that. A link to `savoya.com` arrives clean.
- A branded URL reads as Savoya. An unknown attachment reads as risk.
- A link can show the current version after a re-quote. A PDF in an inbox goes stale.
- Savoya would know when the quote was opened.
- Both audiences use the same document. Internal users (CSM, manager, whoever inherits the account) need to find it later. The client, often a travel agency, opens it without an account. Any design serving only one is wrong.

**Steps to reproduce**
N/A, feature request. The place probably exists: every Julia and Robyn signature points clients at `core.savoya.net`, and clients already view reservations there. Something like `core.savoya.net/quotes/<id>` fits.

**Reference**
Design questions still to settle, not decisions yet requested:
- **Public-but-unguessable or login-gated?** The recipient is frequently BCD or a Ritz concierge, not a portal user. A login gate kills the use case. An unguessable URL is how Docusign and Stripe invoices work, but anyone with the link can read pricing.
- **Filed under the client profile or under quotes?** Under the profile it accumulates into account history. Under quotes it is a flat object that does not presume a profile (a first-contact RFP may have none). Possibly both: stored as a quote, linked from the profile.
- **How long does it live?** Documents carry a 7-day validity window today. The URL could expire with it, show "expired — contact us", or live forever as history.
- **What happens on a re-quote?** The same URL updated means the client cannot work from a superseded price, but a link sent yesterday silently shows different numbers today. A new URL avoids that.
- **Who can see it internally?** Anyone at Savoya, or the owning CSM and their team? Pricing and discounts are on the page.

**Acceptance criteria**
- [ ] A way to POST a self-contained HTML document and get back a URL.
- [ ] The five design questions above are answered in writing before the data model is built.

---

# Resolved

Items move here with the answer and the date, only on Ayush's say-so. Condensed 2026-10-11. The full original wording and evidence for each item is in git history at commit `f1a8b36`.

## B10 — Cross-market sourcing · closed 2026-10-10, largely delivered
**Jira:** `GREEN-371` · **PRD:** R48–R51 (*Built — in validation*)

**Problem:** no way to source vehicles from a nearby market when the primary market is short.
**Resolution:** Five of six acceptance criteria landed. The plugin shipped against them within four days of filing (2026-10-06). Four live client quotes have exercised the path.
- `lookup_nearby_markets`: the three nearest markets by road distance, each with the vehicle types and quantities it adds, and a signed `market_ref`. Core's existing override-service-area feature sorted by linear distance, so this was fixed, not reused.
- `resolve_service_areas`: anchors the lookup to any market the CSM names.
- `calculate_sourced_quote_units`: a mixed-market package priced in one call through the exact path, primary-market allocations included.

**Findings from live use:**
- A sourced vehicle bills the primary market's rates, not its home market's. An Austin Mini Bus sourced into Dallas billed Dallas's **$314.92/hr**, not Austin's **$244.09/hr**. *Contradicted 2026-10-11 by the reservation UI, which bills the source market's rate. See H4 (`GREEN-388`).*
- Returned counts are additional, not totals. Vehicles whose vendors already serve the reference market are excluded. The counts are unconfirmed and promise nothing about fulfilment.
- A `market_ref` is scoped to the market it was looked up from. Nearby is not the same as sourceable: Dallas returned only Shreveport, Austin and Oklahoma City, while Houston sits in Austin's list.

**Carried forward, not closed.** Whether these become their own items or ride on a `GREEN-371` follow-up is Ayush's call:
1. **AC #2, a rate sheet for an arbitrary service area.** Obtainable only by resolving locations in that market and previewing there. There is no "rates for market X" call. Showing a nearby market's own rates is hazardous, per the first finding above.
2. **AC #6, the excess drive-time cost as its own visible line.** Each market's vehicles carry their own line item with a named source market, but the positioning cost sits inside the billed hours and is disclosed in words, not as a money line.

## B8 — Does the engine already model greeters? · closed 2026-10-10, yes
**PRD:** R36

**Problem:** `resolve_itinerary_stops` returns `greeter_required: false` on the airport object, which suggested greeters exist in Core.
**Resolution:** Greeters are priceable vehicle types: id 12 "Hourly Greeter/Coordinator" and id 13 "Single Greet", both `greeter: true`, `capacity: null`. Core priced id 12 in Orange County at rate 55549: $100.00/hr rack, **$76.99/hr** effective, 2-hour minimum. An Irvine on-site coordinator request came to **$404.20**. The plugin prices greeters as their own quote units and asks a human for a cost only where the market has no greeter rate.
**Why it mattered:** a hand-entered "On-site coordinator — 4 hrs at $235/hr = $940" reached a client against Core's $404.20, **2.3× over**. Rule produced: never ask a human for a number Core has.
**Carried forward:** the rate sheet cannot answer the greeter question (see F8). A second greeter model may exist (see G1). What `greeter_required` drives was never answered (see G1).

## B1 — `passenger_id` required for quoting · closed 2026-10-10, answered by the contract
**Problem:** the exact-pricing tools required a `passenger_id`, so the plugin borrowed the first passenger on the profile before any real passenger was known.
**Resolution:** `passenger_id` is optional on every pricing tool. When omitted, Core attaches an eligible passenger to the unsaved calculation and says so in a warning. Node B (`resolve_passengers`) is skipped unless the user names a passenger. The per-profile passenger cache was removed, because caching would only keep alive a disclosure the CSM no longer needs. PRD Business Rule 2 (a quote never requires knowing which traveler it is for) holds by omission.
**Previous verification, for the record:** pricing is passenger-independent. The same itinerary quoted against two passenger ids gave byte-identical output (same rate id, same totals), with the name nowhere in the payload or widget.
**Carried forward:** F3.

## A1 — `plan_approximate_quote_units` priced differently from the web app · closed 2026-10-10, moot
Same Boston job, same Mini Bus, same date:

```
Path                              Rate                                      Job total
plan_approximate_quote_units      $311.84/hr (base $405 less ~23%)          $9,355.20
calculate_quote_units             $283.50/hr (base $405 less 30%)           $7,945.00
                                  discount_basis_points: 3000
```

The profile's contracted discount is 30%. The approximate path applied something else: a **$1,410.20 difference** on one job.
**Resolution:** the tool was removed from the MCP contract. `mcp-contract.md` records the removal and a guard fails the build if any file in either skill names it. The plugin prices normally, or asks the user for a temporary base rate where a market has no stored rate.
**Carried forward:** `QuoteBuilder::ApproximateQuotePlanner` is still being built with no consumer on the MCP side. Tracked under F2.

## B3 — `calculate_quote_options` ignored vehicle capacity · closed 2026-10-10, moot
80 passengers against a 41-seat Mini Bus returned `required_quantity: 1`, `quantity: 1`. `calculate_quote_units` and `generate_quote_options` both size from `passenger_count`.
**Resolution:** the tool was removed from the MCP contract and is guarded against, as with A1. The plugin had already stopped calling it.

## B5 — `plan_approximate` had no option grouping · closed 2026-10-10, moot
Two mutually exclusive scenarios sent in one call were summed. The widget showed **$4,712.40** for a $693 option and a $4,019.40 option.
**Resolution:** closed with A1; the tool is gone. `generate_quote_options` handles alternatives with separate per-option totals, which is the path the plugin uses.

## A2 — Are effective rates inclusive of the fuel surcharge? · answered 2026-09-20, by observation
**Resolution:** yes. `effective_rate_amount` folds in the contracted discount and the fuel surcharge. Verified on a London LGW arrival (profile 201890):

```
base_rate_amount              200.00
discount_basis_points         3000   → × 0.70 = 140.00
fuel_surcharge_basis_points   1000   → × 1.10 = 154.00
effective_rate_amount         153.99   (per-vehicle rounding)
```

A document must not add a fuel surcharge on top of the effective rate. The plugin reconstructs from `base_rate_amount`, shows discount and fuel as separate lines, and reconciles the total to `aggregate_total`.
**Update 2026-10-10:** engine line amounts are pinned per leg at Core's own granularity with fuel as the remainder, so the total matches by construction and a mismatch refuses to render. The earlier approach absorbed the residual into the last line, which made that line misstate its percentage and put a 5-vehicle Boston job 30 cents above Savoya's quote. Discounts are additive in basis points: 30% plus 10% more is 40%, not 37%. An extra discount is therefore a Core re-quote, not local arithmetic.
**Open question left on the record:** is the order always discount then fuel, or can a market apply them the other way round? The plugin assumes discount then fuel.

## A3 — A profile with a non-zero fuel surcharge · answered 2026-09-20
**Resolution:** London on profile 201890 returns `fuel_surcharge_basis_points: 1000` (10%). The same profile returns 0 in US markets. The surcharge is market-scoped, not profile-scoped. The finding caught a plugin bug: the terms bullet was hardcoded to "5%". It is now read from the engine. No engineering action required.

---

## Retired and merged ids

| Old id | Now |
|---|---|
| **F5** | Folded into **B7** |
| **F7** | Folded into **G1** |
| **G5** | Folded into **G1** (same observation filed twice) |
| **B6** | Merged into **G6** (same request, re-rated as a correctness item) |
| Old vault **G1–G7** block | Retired 2026-10-10. Mirrored PRD gaps, and the ids collided with the repo's G-block. The PRD owns them. Pointers below. |

Pointers from the retired block:

| Old id | Gap | Now |
|---|---|---|
| G1 | Standalone client-facing rack-rate-sheet document | **PRD R4**, blocked behind R9 / F4 |
| G2 | No-client / rack-only route | **PRD R9**; engineering side is **F4** |
| G3 | Multiple named vehicle-mix combinations | **PRD R21**, unblocked: the engine accepts 2–5 named options. Within-leg mixing is **F6** |
| G4 | Rate-sheet completeness (buses / greeters / fleet count) | **PRD R24, R25**. Buses and fleet count are present. Greeters are not (see F8) |
| G5 | International location and rate coverage unconfirmed | **PRD R15**; engineering side is **F9** |
| G6 | NFR-2 auth/permissions never tested | **PRD NFR-2**; engineering side is **F10** |
| G7 | Luggage-capacity default (~1 bag/pax) | **PRD R22**, a product decision with no engineering dependency |
