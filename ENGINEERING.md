# Open items for Savoya engineering

Observations from building and testing the `savoya-quoting` plugin that need a decision or
a change on the Savoya side. Each item records **what was observed**, the **evidence** (real
tool responses and real numbers, never paraphrase), **what the plugin does meanwhile**, and
a one-line **Need**.

**Nothing is marked done.** A resolved item moves to *Answered / closed* with the answer
and the date, and only when Ayush says it is resolved.

> **Reconciled 2026-10-10.** This file now holds **one** list. It previously existed as two
> — a vault copy carrying A1–A4, B1–B10, C1–C2, D1/D3/D4, E1 and F1–F11, and a repo copy
> started 8 Oct carrying B7b and G1–G6 whose ids **collided** with the vault's own G-block.
> The merge: the repo's G1–G6 keep their ids (they are referenced from `RULES.md`,
> `CHANGELOG.md` and the G6 spec), and the vault's old G1–G7 block is **retired** — those
> rows mirrored PRD gaps rather than engineering findings, and the PRD is now the base
> document that owns them. Each is cross-referenced from §*Product gaps* below.
>
> Also merged in this pass: **G5 into G1** (the same observation written twice, same
> evidence, same Need) and **B6 into G6** (the same request — a compact response mode —
> filed once as a convenience at Low and once as a size observation; it is now a
> correctness item, for the reason G6 gives).

## What to pick up first

Ordered by what it unblocks, not by filing date:

1. **G6 — a compact response mode.** The only item on this list that currently defeats a
   client-facing safety check. Five sessions hand-transcribed a quote response because it
   was too large to save, and a hand-typed response makes the plugin's fail-closed total
   check unable to catch a transcription error. Filed at Low as B6 when it looked like a
   convenience; it is not.
2. **B7 / B7b — airline and FBO resolvers.** Blocks quoting a request that names a real
   commercial flight or a specific FBO outright. Longest-standing functional gap; PRD R14
   and R52.
3. **F4 — the no-client / rack-only route.** The oldest unaddressed product gap, unbuilt on
   every path checked: current plugin, MCP, and the new Core work alike. Blocks PRD R9 and,
   behind it, R4.
4. **F1 / F2 / F11 — the architecture answer.** Whether `QuoteBuilder` replaces or parallels
   the MCP tool surface, what Auth0 adds over today's already-per-CSM OAuth, and what the
   plugin's migration looks like. Everything else on this list is scoped differently
   depending on the answer. `GREEN-354` is the ticket.
5. **G4 — the no-local-provider warning on the quote response.** Small, and it retires the
   one piece of state the plugin carries across skills purely to cover a Core gap.
6. Then the data-quality and field-completeness items: A4, G1, G2, G3, B9, D1/D3/D4, C1, C2.

---

## Index

| # | Item | Priority | Raised | Status |
|---|---|---|---|---|
| **G6** | Tool responses exceed output limits on multi-unit packages — and a hand-transcribed response defeats the document's fail-closed total check | **High** | 2026-10-10 (as B6, Low, earlier) | Open |
| **B7** | No airline resolver, so known commercial flights are unquotable | **High** | before 2026-10-08 | Open |
| **B7b** | No FBO resolver either, so private flights are specified but unreachable | Medium | 2026-10-07 | Open |
| **A4** | Rate sheet ignores "Waive All Incidentals" — shows a fuel surcharge the quote tools correctly waive | **High** | 2026-09-20 | Open |
| **F1** | Auth0 vs. today's per-CSM OAuth — what does per-end-user identity actually add? | **High** | 2026-09-20 | Open |
| **F2** | MCP tool surface vs. `QuoteBuilder` — replacement or parallel path? | **High** | 2026-09-20 | Open — **new evidence**, see below |
| **F4** | No-client / rack-only quoting unbuilt on every path | **High** | 2026-09-20 | Open |
| **F5** | Airline resolver confirmed still unaddressed by `QuoteBuilder` | High | 2026-09-20 | Open — see B7 |
| **G4** | The quote response carries `excess_drive_time` but not the no-local-provider warning — both are needed | Medium | 2026-10-08 | Open |
| **G1** | `greeter_fee` / `adjusted_greeter_fee` exist on the quote object but no tool can set them | Medium | 2026-10-07 | Open — G5 merged in |
| **G2** | `client_can_book` is missing from `presentation` rate-preview rows | Medium | 2026-10-08 | Open |
| **G3** | `temporary_rate_used` is `false` at aggregate level while the unit says `true` | Medium | 2026-10-08 | Open |
| **B9** | `quote_units_unavailable` returns an empty `issues[]` | Medium | — | Open |
| **B2** | Passenger pool scope (per TC profile vs. per company); zero-passenger profile behaviour | Low | — | Open — **downgraded**, see below |
| **B4** | `scenario_comparison` widget hides data the payload already carries | Low | — | Open — **downgraded**, workaround shipped |
| **F3** | Does `QuoteBuilder`'s exact path still require a resolved passenger? | Medium | 2026-09-20 | Open — narrowed |
| **F6** | Mixed-fleet quoting within one option — on any roadmap? | Medium | 2026-09-20 | Open |
| **F7** | Greeter pricing — a priced service in `QuoteBuilder`? | Medium | 2026-09-20 | Open — see G1 |
| **F8** | Rate preview gaps: no-client rates, explicit discount indicator | Medium | 2026-09-20 | Open — narrowed, fleet count resolved |
| **F9** | International stop-resolution policy — product decision, not engineering | Medium | 2026-09-20 | Open — **sharper**, see below |
| **F10** | NFR-2 permission granularity beyond "internal roles" | Medium | 2026-09-20 | Open |
| **F11** | Plugin migration / rollout plan once `QuoteBuilder` ships | Medium | 2026-09-20 | Open |
| **D1, D3, D4** | Rate-configuration data issues (Yerdle decimal slip; Chicago Mini Bus unrated; Executive Van unrated in most markets) | Medium | — | Open |
| **C1** | `as_directed` city lookup fails on state abbreviations | Low | — | Open — workaround shipped |
| **C2** | Stop-ref TTL undocumented | Low | — | Open — partially answered by observation |
| **E1** | Host quote documents at a Savoya URL (shareable link) — design questions unresolved | P3 | — | Open — Phase 2 |

**Closed in the 2026-10-10 pass:** A1, A2, A3, B1, B3, B5, B8, B10, and the retired G1–G7
product-gap mirror. See *Answered / closed*.

---

## G6 — Compact response mode, and why it is now a correctness item

*(Filed earlier as **B6**, "compact response mode", Low. B6 is merged here. The request is
the same; the justification changed.)*

**Observed (2026-10-10)** On a live 16-unit World Cup shuttle quote, four tool responses
were too large to read directly and had to be written to disk and pulled apart with `jq`
before the flow could continue.

**Evidence** From the session capture for `yerdle-world-cup-2027` (16 units: 4 origins ×
4 match dates, one Mercedes Sprinter each, out-and-back hourly with a 4.5-hour wait):

| Tool | Response size |
|---|---|
| `preview_rate_batch` | ~230 KB |
| `generate_quote_options` | ~190 KB |
| `calculate_temporary_quote_units` | ~124 KB |
| `calculate_quote_units` | ~108 KB |

Sixteen units is not an unusual job — it is four shuttles on four dates, and the request
that produced it was two sentences long. A 43-vehicle request would be several times larger
again.

**Why this is not a convenience request.** Each response has to be read before the next
step can be chosen, so when one cannot be read the session improvises. In five separate
sessions the improvisation was the same: **the engine response was re-typed by hand** into
`raw_quote.json`, recorded each time in the capture's `--workaround` field.

That defeats the plugin's strongest money protection. The document's fail-closed check (C4)
compares its own reconstruction of the total against the engine's `aggregate_total` and
refuses to render on any gap. But when the response is hand-typed, **both sides of that
comparison come from the same typing** — `aggregate_total` is read from the same file — so a
transcription slip in a line total propagates to the aggregate and the check cannot see it.
Nothing in the plugin can verify a hand-typed number against a source it does not have.

Most of the volume is repetition. Every unit carries the full `presentation` block, and
`generate_quote_options` repeats near-identical vehicle options per unit — the plugin's own
capture slimming drops `vehicle_options` and `elevated_option` as duplicates of
`value_option` and gets about **3× smaller** doing it, with nothing it needs lost. But that
slimming only helps *after* the response has been received; it cannot help a response that
cannot be received.

**What we do meanwhile** Nothing that works. The workaround is the problem.

**Need:** a compact or summary response mode for multi-unit packages — ideally one that
omits `presentation` and collapses duplicated vehicle options, so a 16-unit quote can be
read in one call. A full written spec, including the measured tier sizes, is in
`G6_Compact_Response_Spec_for_Ethan.md`.

---

## B7 — No airline resolver

**Observed** The flight object documents a known-commercial form requiring `airline` as a
resolved object with an id, and nothing in the tool contract resolves an airline.

**Evidence** Omitting the flight object fails the call outright (`flight is required for
airport stops`), so every airport stop must carry one, and the only shape the plugin can
construct is `commercial_tbd: true`.

**What we do meanwhile** Send `commercial_tbd: true` on every airport stop, even when the
client supplied a flight number, and keep the number as a client-facing note disclosed as
"to be confirmed". The seam is written down in `mcp-contract.md` so that when a resolver
lands, the next person knows the shape was understood and consciously deferred.

**Need:** confirm whether an airline resolver is coming, or that TBD stays the only
supported shape. PRD R14. **This is the highest-priority functional gap in the product.**

## B7b — No FBO resolver either

**Observed (2026-10-07)** The flight object also documents a private form requiring
`private: true` plus `fbo` as a resolved object with an id. There is no FBO resolver, so
private flights are specified and unreachable, exactly as B7 describes for commercial ones.

**Evidence** FBO ids do exist and do come back incidentally —
`resolve_itinerary_stops` on an address near an airport returns them under
`nearby_airport`:

```json
"nearby_airport": {
  "airport": {"id": 4655980, "iata_code": "SNA", "display_name": "SNA - John Wayne Arpt Orange Co"},
  "fbo": {"id": 111845, "name": "ACI Jet South", "airport_id": 4655980}
}
```

So the ids are real; what's missing is a way to resolve an FBO the user *names*. Scraping
one out of a `nearby_airport` block would mean guessing that the FBO nearest the pickup is
the one the client is flying into, which is exactly the kind of inference the quote
integrity contract forbids.

**Need:** an FBO resolver, or confirmation that private flights stay out of scope. PRD R52.

---

## A4 — The rate sheet disagrees with the quote for an affected client

**Observed (2026-09-20)** `preview_rate_batch` ignores the company profile's "Waive All
Incidentals" flag and shows a fuel surcharge that the exact-quote tools correctly waive.

**Why it matters** For a client with that flag set, the rate sheet a CSM reads and the
quote the client receives disagree about the surcharge — and the rate sheet is the artifact
the CSM trusts when explaining the number. The plugin cannot reconcile the two, because
only one of them is wrong and it has no way to know which flag applies.

**Need:** apply the waiver in the rate preview, or confirm the rate sheet is deliberately
pre-waiver and should be labelled as such.

---

## F1 — What does Auth0 add over today's per-CSM OAuth?

**Observed (2026-09-20)** Today's model is **not** a single shared identity, which is how it
is sometimes described: each CSM authenticates individually against `dev.auth.savoya.net`
with their own Savoya account (PKCE, scope `access:savoya_mcp`). What is shared across
installations is the OAuth *client id* — a public registration — not the user's identity.
`Api::V1::QuoteBuilderController` is the same shape today: per the Core change inventory it
"uses the authenticated Savoya user, limits access to internal roles", which is already
per-user.

**Need:** state what per-end-user identity via Auth0 adds that today's per-CSM OAuth does
not. If the answer is audit, or token lifetime, or revocation, that is a good answer — it
just isn't recorded anywhere source-grounded, so the plugin cannot plan for it.

## F2 — Replacement or parallel path? *(new evidence 2026-10-10)*

**Observed (2026-09-20, sharpened 2026-10-10)** It remains undetermined whether the
`QuoteBuilder::*` services replace the MCP tool surface or run alongside it. Two things that
happened since make the question more pressing, not less:

1. **The cross-market sourcing work landed on the MCP tool surface, not in `QuoteBuilder`.**
   Three new tools (`lookup_nearby_markets`, `calculate_sourced_quote_units`,
   `resolve_service_areas`) and two removals (`plan_approximate_quote_units`,
   `calculate_quote_options`) all happened on the MCP side, with no `QuoteBuilder`
   involvement. That is evidence toward "parallel", but it was never stated as a decision.
2. **The approximate path has diverged between the two layers.** The plugin removed its
   approximate path entirely — the tool is gone from the contract and forbidden anywhere in
   the tree — while the Core inventory is still building
   `QuoteBuilder::ApproximateQuotePlanner`. If the plugin is `QuoteBuilder`'s consumer,
   that service currently has no consumer at all; if it is not, the two layers are being
   built to different pricing philosophies.

**Need:** a stated decision — replacement, parallel, or staged — plus, specifically, who
`ApproximateQuotePlanner` is for. `GREEN-354` is the ticket.

## F3 — Does `QuoteBuilder`'s exact path still require a resolved passenger? *(narrowed)*

**Narrowed 2026-10-10.** The MCP side answered this: `passenger_id` is now optional on every
pricing tool and Core attaches an eligible passenger to the unsaved calculation itself (see
B1, closed). The question survives only for `QuoteBuilder`: if its exact path still requires
one, the workaround B1 just retired comes back on migration.

**Need:** confirm `QuoteBuilder::QuoteUnitsEstimator` matches the MCP contract here.

## F4 — No-client / rack-only quoting is unbuilt on every path

**Observed (2026-09-20, re-confirmed 2026-10-10)** Quoting requires a resolved client on
every path checked: the current plugin (no match → ask for a name, email or profile id;
never guess), the MCP tool surface, and the new Core work alike —
`ApproximateQuotePlanner`'s own documentation says a travel-coordination profile is still
required.

**Why it matters** This is the oldest unaddressed gap in the product and it blocks two PRD
requirements rather than one: R9 (price without a named client) and R4 (a standalone
client-facing rate-sheet document), which cannot exist until R9 does.

**Need:** a build decision on the no-client / rack-rate route, on whichever layer will own
it.

## F5 — Airline resolver unaddressed by `QuoteBuilder`

Confirmed by reading the Core change inventory against B7: none of the new
`StopResolution::*` services resolve an airline object, and `flight_builder.rb`'s change
normalizes `commercial_tbd` handling rather than resolving a real flight number. So B7's
workaround survives `QuoteBuilder` shipping. Tracked here so the architecture answer
doesn't read as closing B7. **Need:** see B7.

## F6 — Mixed-fleet quoting within one option

**Observed (2026-09-20)** The Core inventory states that `EstimateOptionsBuilder` "compares
homogeneous vehicle options only — does not generate mixed fleets."

**Current state 2026-10-10.** Partially softened on the MCP side: `generate_quote_options`
accepts 2–5 named options, and Core sizes and picks the cheapest candidate **per unit**, so
a value option may legitimately mix vehicle types *across legs*. What is still absent is a
mixed fleet **within one movement** — 2 SUVs plus 1 Sprinter for a single leg — which is
what PRD R21 asks for at its full strength.

**Need:** confirm whether within-leg mixed fleets are on any roadmap.

## F7 — Greeter pricing in `QuoteBuilder`

See **G1**. The MCP side works (greeters price as quote units on vehicle types 12/13), so
nothing is blocked; the question is which of Core's two apparent greeter models is intended
before anything else is built on either. **Need:** see G1.

## F8 — Rate preview gaps *(narrowed)*

**Narrowed 2026-10-10.** Of the three gaps originally filed here, one is resolved by
observation: a **market fleet count** *is* present in the presentation rate rows
(`market_vehicle_count`), which also closes PRD R25. Two remain:

- **No-client rates** — see F4; the rate preview inherits the same requirement.
- **No explicit discount indicator** — the preview shows rack and effective rates, and the
  discount is inferable from the difference, but nothing states it as a field.

A third, `client_can_book`, is filed separately as G2 because it is an omission from one
block of a response that carries it in another.

**Need:** the discount indicator as a field, and no-client rates with F4.

## F9 — International stop-resolution policy *(sharper 2026-10-10)*

**Observed (2026-09-20)** The Core inventory describes a nearest-same-country fallback with
a warning, and says the international inference policy is undefined. Flagged then as a
product decision rather than an engineering one.

**What live use added.** A real London/Sicily/Milan itinerary resolved with **Sicily in no
Savoya service area at all**. Core reported one market as both source and primary for those
stops and priced them from Naples, billing 14.75 hrs against a shorter request. The plugin
handles and discloses this (PRD R57), and it is not a defect — but it means "international
coverage is inconsistent" understates the case: the real boundary is *covered / nearest-market
/ nothing*, and only the first two were in the policy question.

**Need:** a stated policy on the no-service-area case specifically — how far a nearest-market
fallback should reach before a request is refused rather than priced.

## F10 — NFR-2 permission granularity

**Observed (2026-09-20)** Per the Core inventory, authorization "still needs product
confirmation because all internal roles are currently allowed."

**What is worse than it looks.** PRD NFR-2 ("a user only sees and prices what their role
allows") has **never been tested on any path** — it is the only requirement in the PRD with
no evidence in either direction. The plugin inherits whatever the connector grants and has
no way to check it from inside.

**Need:** confirm the intended role granularity, and a restricted-role test account so the
inheritance can actually be verified.

## F11 — Plugin migration plan

**Need:** once F2 is answered, what the plugin's migration looks like — whether the MCP tool
surface keeps its shape, whether the handoff contract has to version again (it is at v3 and
rejects older handoffs rather than interpreting them), and what the rollout sequence is for
pilot users mid-quote.

---

## G4 — The quote response needs the no-local-provider warning *and* `excess_drive_time`

**Observed (2026-10-08)** `resolve_itinerary_stops` returns the sourcing warning; the quote
response does not. The quote response instead sets `excess_drive_time: true`.

**Evidence** Resolving The Westin Whistler returns, with `service_area_source: "nearest"`:

```json
"warnings": ["No local providers are available for this reservation. Availability will be
confirmed from our local providers in Vancouver, Canada. Additional drive time will be
incurred on the reservation."]
```

`calculate_temporary_quote_units` for the same stops returns **no such warning**, and the
stop's own `service_area` comes back `null`. The only quote-side signal is
`excess_drive_time: true`, and the billing consequence is substantial: `duration: 8` on the
as-directed stop billed **12 hours**, 4 of them positioning, at $327.25/hr effective.

**Why both are needed, not one.** They are different facts and a client needs both:

| Signal | What it tells the client |
|---|---|
| no-local-provider warning | **where** the vehicle is coming from — "sourced from our Vancouver partners" |
| `excess_drive_time` | **that** the extra drive time is billed, which is why the hours exceed the request |

`excess_drive_time` alone cannot name the market, so a document built from the quote
response can only say "a neighbouring market". A CSM looking at a 12-hour bill against an
8-hour request, with no named source, has nothing to tell the client.

**What we do meanwhile** The disclosure fires from either signal, and the wording falls back
to generic when the market is unnamed. The precise name is carried forward through the
handoff from stop resolution — **the only field the plugin carries across its own skill seam
purely to cover a Core gap.** It works only when intake and document run in the same
conversation, and it duplicates something Core already knows.

**Need:** carry the no-local-provider warning, with the sourcing market named, on the quote
response as well. Confirm the two are intended to co-occur: no local provider → sourced from
another market → excess drive time applies. **Closing this retires plugin state**, which is
why it is worth more than its size suggests.

## G1 — `greeter_fee` exists on the quote object but no tool can set it

*(**G5** was the same observation filed twice, with the same evidence and the same Need. It
is merged here and its id is retired.)*

**Observed (2026-10-07, confirmed 2026-10-08)** Every vehicle's `quote` object carries four
greeter-fee fields, always empty in our calls:

```json
"quote": {
  "greeter_fee": null,
  "adjusted_greeter_fee": null,
  "greeter_fee_in_vendor_currency": 0,
  "adjusted_greeter_fee_in_vendor_currency": 0
}
```

The same shape appears on all five document fixtures, including
`boston-offsite/raw_quote.json` — an ordinary Mini Bus unit with no greeter involved. No
argument on `calculate_quote_units`, `generate_quote_options` or
`calculate_temporary_quote_units` accepts a greeter fee, so from the plugin's side these
fields can only ever be read.

**Why it matters.** It suggests Core has a second, different model for greeters: a fee
attached to an ordinary vehicle's quote, rather than the separate greeter unit the plugin
builds. The plugin prices greeters as their own quote units on vehicle types 12 (Hourly
Greeter/Coordinator) and 13 (Single Greet), which works and shipped in 0.23.0 — Core priced
id 12 in Orange County at rate 55549, $100.00/hr rack → **$76.99/hr** effective with a
2-hour minimum, and an Irvine request came to **$404.20** against a hand-entered $940. So
nothing is blocked.

But if the fee route is the intended one, a greeter priced as its own unit may be invisible
to whatever downstream reads `greeter_fee`, and the two models would then disagree about
what a booking with a greeter actually costs.

**Need:** confirm which model is intended — a separate greeter quote unit, or a fee on the
vehicle's quote — and if it's the fee, which tool is meant to set it. Also F7.

## G2 — `client_can_book` is missing from the `presentation` rate-preview rows

**Observed (2026-10-08)** In one `preview_rate_batch` response, `client_can_book` appears in
`previews[].result.vehicle_rate_evaluations[].vehicle_type` but **not** in
`presentation.data.groups[].rows[]`.

**Evidence** Same response, same vehicle. In the evaluation:

```json
"vehicle_type": {"id": 7, "name": "Mini Bus", "capacity": 41,
                 "limited_availability": true, "client_can_book": false,
                 "classification": "other", "bus": true, "greeter": false}
```

In the presentation row Core builds for a CSM to read:

```json
{"vehicle_type_id": "7", "vehicle_name": "Mini Bus", "vehicle_capacity": 41,
 "market_vehicle_count": 10, "limited_availability": true,
 "availability": "available", "minimum_hours": 5, "cancellation_hours": 72, …}
```

`limited_availability` made it across; `client_can_book` did not. So the rate sheet a CSM
reads does not say a Mini Bus cannot be booked by the client, even though Core knows it in
the same payload.

**What we do meanwhile** Read it from `resolve_vehicle_types` at the vehicle-selection step
rather than enriching Core's presentation block from the evaluations, because mixing sources
into that block is how a rendered view starts drifting from what Core sent.

**Need:** add `client_can_book` to the presentation rate-preview rows, or confirm the
omission is deliberate. PRD R70.

## G3 — `temporary_rate_used` is `false` at aggregate level while the unit says `true`

**Observed (2026-10-08)** A `calculate_temporary_quote_units` call with an explicit
temporary rate returned contradictory flags within one response.

**Evidence** Unit level, correct:

```json
"adjustments": {"discount_basis_points": 3000, "fuel_surcharge_basis_points": 1000,
                "temporary_rate_used": true}
```

Presentation aggregate, in the same response:

```json
"presentation": {"data": {"pricing": {"adjustments": {"temporary_rate_used": false}}}}
```

The per-unit presentation entry also carries `"temporary_rate_used": true`, so only the
top-level aggregate is wrong. A consumer that reads the aggregate flag to decide whether a
quote contains unsaved pricing would get the wrong answer — and that flag is exactly the
kind of thing a document layer checks before printing "temporary rate, not saved" on a
client-facing page.

**What we do meanwhile** Read the unit-level flag, never the aggregate.

**Need:** fix the aggregate flag, or confirm it means something other than "any unit used a
temporary rate".

---

## B9 — `quote_units_unavailable` returns an empty `issues[]`

**Observed** When Core cannot price a unit it returns `status: "blocked"` with
`error_type: "quote_units_unavailable"` and an empty `issues[]`, so the plugin can tell the
user that something is unavailable but not what.

**What we do meanwhile** Say plainly that the market has no stored rate for that vehicle and
offer the two routes that work — a different vehicle, or a user-supplied temporary base rate
(PRD R34). This is adequate for the no-rate case and inadequate for every other cause,
because they are indistinguishable.

**Need:** populate `issues[]`, or document the distinguishable causes.

## B2 — Passenger pool scope and zero-passenger profiles *(downgraded)*

**Downgraded 2026-10-10** from Medium to Low. The question — whether the passenger pool is
scoped per TC profile or per company, and what a zero-passenger profile does — mattered
mainly because the plugin had to pick a passenger to quote at all. It no longer does
(B1, closed), and `QuoteBuilder::PassengerSearch` removes the 10-passenger cap. Still worth
an answer for the case where a user *names* a passenger, which is the only path that
resolves one now.

**Need:** confirm the scope, for the named-passenger path only.

## B4 — `scenario_comparison` hides data the payload carries *(downgraded)*

**Downgraded 2026-10-10** from Medium to Low — a workaround shipped and it is a good one.
`render_presentation.py` prints Core's own `presentation` block, which gives every CSM the
same view of the same quote with Core's figures rather than restated ones, and the
comparison summary falls back to the plugin's own summarizer when a response carries no
presentation block. The widget's omissions are no longer load-bearing.

**Need:** low-priority — confirm whether the widget is intended to remain lossier than the
payload.

## D1, D3, D4 — Rate-configuration data issues

Three data-hygiene items, unchanged: a Yerdle rate with a decimal slip; Chicago Mini Bus
unrated; Executive Van unrated in most markets. These surface to the user as "no stored
rate", which is now a recoverable path (PRD R34) rather than a dead end — so they cost the
CSM a temporary-rate conversation rather than blocking the quote.

**Need:** data correction, and ideally a sweep for the same shape elsewhere.

## C1 — `as_directed` city lookup fails on state abbreviations

**Observed** Querying an as-directed city with an abbreviated state returns nothing;
spelling the state out resolves first time.

**What we do meanwhile** Always query `"<City>, <State spelled out>"` and pick the candidate
whose id matches the pickup's city id — deterministic, not a guess, and it asks only if
none matches. Written into the decision tree.

**Need:** accept abbreviations, or document that they are unsupported.

## C2 — Stop-ref TTL undocumented *(partially answered by observation)*

**Observed** Stop refs expire, and the expiry is not documented. Observation puts it at
roughly 24 hours, which the plugin now relies on when a user asks for a rate sheet later in
a conversation.

**Need:** confirm the real TTL, since the plugin's "stop refs live ~24h" is measured rather
than specified. A sourcing `market_ref` has its own expiry and its own recovery path
(`sourcing_reference_expired` → look up again from the same reference market), which is
documented — the stop ref should be as clear.

## E1 — Host quote documents at a Savoya URL

Unchanged, P3, Phase 2. A shareable link for a quote document, with the design questions
still open: public vs. gated access, where it's filed (profile vs. quotes), expiry, what
happens on re-quote, and internal visibility. **Need:** a design decision before any work.

---

## Product gaps — owned by the PRD, not by this file

The old **G1–G7** block mirrored product-owned gaps from `Requirements_Quoting_Pilot.md` so
Ethan would see them alongside the engineering-discovered ones. That block is **retired** as
of 2026-10-10: its ids collided with the newer G-block above, and the PRD is now the base
document that owns these. They are listed here as pointers only.

| Old id | Gap | Now |
|---|---|---|
| G1 | Standalone client-facing rack-rate-sheet document | **PRD R4** — still a gap, blocked behind R9/F4 |
| G2 | No-client / rack-only route | **PRD R9** — still a gap; engineering side is **F4** |
| G3 | Multiple named vehicle-mix combinations, not just value/elevated | **PRD R21** — **unblocked**: the engine accepts 2–5 named options. A product decision now, except for within-leg mixed fleets (**F6**) |
| G4 | Rate-sheet completeness (buses / greeters / fleet count) | **PRD R24, R25** — **resolved by observation.** Buses and the market fleet count are present. **Greeters are not, and cannot be answered by the rate view at all** — they are absent from `vehicle_rate_evaluations` and are not reported in `missing_vehicle_type_ids` either, so the view is silently incomplete rather than wrong. The plugin attempts a price instead and reads the answer |
| G5 | International location & rate coverage unconfirmed | **PRD R15** — still open; engineering side is **F9**, now sharper |
| G6 | NFR-2 auth/permissions never tested | **PRD NFR-2** — still untested; engineering side is **F10** |
| G7 | Luggage-capacity default (~1 bag/pax) | **PRD R22** — a product decision, no engineering dependency |

---

## Answered / closed

*Items move here with the answer and the date, only on Ayush's say-so. Closed in the
2026-10-10 reconciliation pass, confirmed by Ayush.*

### A1 — `plan_approximate_quote_units` prices differently from the web app
**Closed 2026-10-10 — moot.** The tool was removed from the MCP contract. The plugin has no
approximate pricing path at all: `mcp-contract.md` records the removal and a guard fails the
build if any file in either skill names the tool. Where the approximate path used to be
used, the plugin now either prices normally (a profile with no passenger) or asks the user a
question (a market with no stored rate → a temporary base rate through
`calculate_temporary_quote_units`). The discrepancy this item described can no longer occur,
because the path that produced it is gone. *Note the open question this leaves on the Core
side: `QuoteBuilder::ApproximateQuotePlanner` is still being built and now has no consumer
on the MCP side — tracked under **F2**.*

### A2 — Are effective rates inclusive of the fuel surcharge?
**Answered** (pre-2026-09-20). Yes — `effective_rate_amount` folds in both the contracted
discount and the fuel surcharge. The document shows the standard rate and both appear as
their own lines. This is the basis of C5: the plugin copies Core's amounts rather than
rebuilding them.

### A3 — A profile with a non-zero fuel surcharge to test against
**Answered** (pre-2026-09-20). London returns 10%; most markets return 5%. The surcharge is
market-scoped and must never be hardcoded — two separate plugin bugs came from a literal
`5%`.

### B1 — `passenger_id` required for quoting
**Closed 2026-10-10 — answered by the contract.** `passenger_id` is now **optional** on
every pricing tool, and when omitted Core deterministically attaches an eligible passenger
to the unsaved calculation. The plugin's workaround is gone: node B (`resolve_passengers`)
is skipped unless the user names a passenger, and the per-profile passenger cache was
removed rather than kept, because caching would only keep alive a disclosure the CSM no
longer needs to see. PRD Business Rule 2 (a quote never requires knowing which traveler it
is for) is now enforced by omission rather than by a documented workaround.

*The previous workaround, for the record: take the first cached passenger on the profile,
verified passenger-independent at the time by pricing the same quote against two different
passenger ids and getting byte-identical results.*

*Carried forward:* **F3** — whether `QuoteBuilder`'s exact path matches, or brings the
requirement back on migration.

### B3 — `calculate_quote_options` ignores vehicle capacity
**Closed 2026-10-10 — moot.** The tool was removed from the MCP contract and is guarded
against, like A1. The plugin never called it even while it existed, precisely because it
ignored headcount.

### B5 — `plan_approximate_quote_units` has no option grouping, so mutually exclusive scenarios get summed
**Closed 2026-10-10 — moot.** Same removal as A1.

### B8 — Does the engine model greeters as a priced service?
**Closed 2026-10-10 — yes, and it ships.** Greeters are separately priceable vehicle types:
id 12 "Hourly Greeter/Coordinator" and id 13 "Single Greet", both `greeter: true`,
`capacity: null`. Core priced id 12 in Orange County at rate 55549 — $100.00/hr rack,
**$76.99/hr** effective, 2-hour minimum — and an Irvine on-site coordinator request came to
**$404.20**. The plugin now prices greeters as their own quote units (PRD R36), and asks a
human for a cost only where the market genuinely has no greeter rate.

**This one mattered more than its priority suggested.** A hand-entered *"On-site coordinator
— 4 hrs at $235/hr = $940"* reached a client against Core's $404.20 for the same request —
**2.3× over**. The rule it produced: never ask a human for a number Core has.

*Two consequences carried forward:* the rate sheet cannot answer the greeter question at all
(so the plugin attempts a price and reads the answer — see the Product gaps table, old G4),
and Core appears to have a *second* greeter model that nothing can set (**G1**).

### B10 — Cross-market sourcing
**Closed 2026-10-10 — largely delivered, within four days of being scoped.** Filed
2026-10-06 with six acceptance criteria as `GREEN-371`; five landed and the plugin shipped
against them. PRD R48–R51 are now *Built — in validation*, and four live client quotes have
exercised the path.

What landed: `lookup_nearby_markets` (three nearest markets by **road** distance — the one
part of the existing override-service-area feature that had to change rather than be reused
— each with the vehicle types and quantities it adds, plus a signed `market_ref`);
`resolve_service_areas` for anchoring the lookup to any named market; and
`calculate_sourced_quote_units` for a mixed-market package priced in one call through the
exact path, primary-market allocations included.

Three findings from live use worth keeping, because they are not obvious from the design:

- **A sourced vehicle bills the primary market's rates, not its home market's.** An Austin
  Mini Bus sourced into Dallas billed Dallas's **$314.92/hr**, not Austin's **$244.09/hr**.
  The nearby market supplies the vehicle, not the price.
- **The returned counts are "additional", not totals** — vehicles whose vendors already
  serve the reference market are excluded — and they are **unconfirmed**, promising nothing
  about fulfilment.
- **A `market_ref` is scoped to the market it was looked up from**, and nearby is not the
  same as sourceable: Dallas returned only Shreveport, Austin and Oklahoma City, while
  Houston sits in Austin's list.

*Two acceptance criteria carried forward rather than closed:*

1. **AC #2 — a rate sheet for an arbitrary service area.** Obtainable only by resolving
   locations in that market and previewing there; there is no "rates for market X" call. It
   is also hazardous to show naively, per the first finding above — a nearby market's own
   rates are not what gets charged when sourcing from it.
2. **AC #6 — the excess drive-time cost as its own visible line.** Each market's vehicles
   carry their own line item with their own named source market, but the positioning *cost*
   sits inside the billed hours and is disclosed in words rather than shown as a separate
   money line.

Whether these two become their own items, or ride on a `GREEN-371` follow-up, is Ayush's
call — they are recorded here rather than silently dropped.
