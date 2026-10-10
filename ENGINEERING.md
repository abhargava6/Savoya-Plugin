# Open items for Savoya engineering

Items found while building and testing the `savoya-quoting` plugin that need a change, a
decision, or data hygiene **on the Savoya side**. Nothing here is a plugin bug; those are
tracked in `skills/quote-document/RULES.md` inside the repo, with the dated history in
`feedback-archive.md`.

Each item records **what was observed**, the **evidence** (real tool responses and real
numbers, never paraphrase), **what the plugin does meanwhile**, and a one-line **Need**.

**Status key:** `open` · `answered` · `done` · `wontfix`
**Owner:** Savoya engineering unless noted. Point of contact for triage: **Ethan Ward**.

**Nothing is marked done.** A resolved item moves to *Answered / closed* with the answer
and the date, and only when Ayush says it is resolved.

**Canonical copy: the plugin repo** (`~/Documents/Savoya MCP/savoya-quoting/ENGINEERING.md`),
which is a connected folder. The copy in the vault is a byte-identical mirror kept so the file
is readable without the repo; edit the repo copy and mirror it, never the other way round.

> **Reconciled 2026-10-10.** This file existed as **two** files with **colliding item ids**:
> a vault copy carrying A1–A4, B1–B10, C1–C2, D1/D3/D4, E1 and F1–F11, and a repo copy
> started 8 Oct carrying B7b and G1–G6 — whose G-block meant something else entirely.
> Neither was a list of what engineering still owes, because neither was the whole list.
>
> The merge: the repo's **G1–G6 keep their ids** (they are referenced from `RULES.md`,
> `CHANGELOG.md` and the G6 spec), and the vault's old **G1–G7 block is retired** — those
> rows mirrored PRD gaps rather than engineering findings, and the PRD is now the base
> document that owns them. Each is cross-referenced from *Product gaps* below.
>
> Also merged in this pass: **G5 into G1** (the same observation written twice, with the
> same evidence and the same Need) and **B6 into G6** (the same request — a compact response
> mode — filed once as a convenience at Low and once as a size observation; it is now a
> correctness item, for the reason G6 gives).
>
> Every A–F item below carries its **original observation and evidence verbatim**. Where
> today's work changed an item's standing, that is added as a dated annotation rather than
> by rewriting what was observed.

## What to pick up first

Ordered by what it unblocks, not by filing date:

1. **G6 — a compact response mode.** The only item here that currently defeats a
   client-facing safety check. Five sessions hand-transcribed a quote response because it
   was too large to save, and a hand-typed response makes the document's fail-closed total
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
   plugin's migration looks like. Everything else is scoped differently depending on the
   answer. `GREEN-354` is the ticket.
5. **G4 — the no-local-provider warning on the quote response.** Small, and it retires the
   one piece of state the plugin carries across its own skill seam purely to cover a gap.
6. Then the data-quality and field-completeness items: A4, G1, G2, G3, B9, D1/D3/D4, C1, C2.

---

## Index

| # | Item | Priority | Status |
|---|---|---|---|
| **G6** | Tool responses exceed output limits on multi-unit packages — and a hand-transcribed response defeats the document's fail-closed total check | **High** | open · B6 merged in |
| **B7** | Known commercial flights are unquotable — no airline resolver | **High** | open |
| **B7b** | No FBO resolver either, so private flights are specified but unreachable | Medium | open |
| **F4** | No-client / rack-only quoting still unbuilt on every path | **High** | open |
| **F1** | Auth0 vs. today's per-CSM OAuth — what does per-end-user identity actually add? | **High** | open |
| **F2** | MCP tool surface vs. `QuoteBuilder` — replacement or parallel path? | **High** | open — **new evidence** |
| **F5** | Airline resolver (B7) confirmed still unaddressed by `QuoteBuilder` | High | open |
| **A4** | Rate sheet ignores "Waive All Incidentals" — shows a fuel surcharge the quote tools correctly waive | **High** | open |
| **G4** | The quote response carries `excess_drive_time` but not the no-local-provider warning — both are needed | Medium | open |
| **G1** | `greeter_fee` / `adjusted_greeter_fee` exist on the quote object but no tool can set them | Medium | open · G5 merged in |
| **G2** | `client_can_book` is missing from the `presentation` rate-preview rows | Medium | open |
| **G3** | `temporary_rate_used` is `false` at aggregate level while the unit says `true` | Medium | open |
| **B9** | `quote_units_unavailable` returns an empty `issues[]` — can't tell which unit failed | Medium | open |
| **F3** | Does `QuoteBuilder`'s exact path still require a resolved passenger? | Medium | open — **narrowed** |
| **F6** | Mixed-fleet quoting within one movement — on any roadmap? | Medium | open — **narrowed** |
| **F7** | Greeter pricing — a priced service in `QuoteBuilder`? | Medium | open — see G1 |
| **F8** | Rate preview gaps: no-client rates, explicit discount indicator | Medium | open — **narrowed**, fleet count resolved |
| **F9** | International stop-resolution policy — product decision, not engineering | Medium | open — **sharper** |
| **F10** | NFR-2 permission granularity beyond "internal roles" | Medium | open |
| **F11** | Plugin migration / rollout plan once `QuoteBuilder` ships | Medium | open |
| **D1, D3, D4** | Rate-configuration data issues | Medium | open |
| **B2** | Passenger pool scope, and profiles with zero passengers | Low | open — **downgraded** |
| **B4** | `scenario_comparison` hides data the payload already carries | Low | open — **downgraded**, workaround shipped |
| **C1** | `as_directed` city lookup fails on state abbreviations | Low | open — workaround shipped |
| **C2** | Stop-ref TTL undocumented | Low | open — partially answered by observation |
| **E1** | Host quote documents at a Savoya URL (shareable link instead of an attachment) | **P3** | open |

**Closed in the 2026-10-10 pass:** A1, A2, A3, B1, B3, B5, B8, B10, and the retired G1–G7
product-gap mirror. See *Answered / closed*.

---

## A · Pricing correctness

### A4 — Rate sheet doesn't respect "Waive All Incidentals" (fuel surcharge shown when the quote waives it)
A company profile's Billing tab has a **Waive All Incidentals** flag. When it's on, the
client's fuel surcharge is waived — confirmed correct on the exact-pricing tools
(`calculate_quote_units`, `generate_quote_options`, etc.): `effective_rate_amount` reflects
the waiver, no surcharge line appears.

`preview_rate_batch` (the rate sheet — used for the internal preview at decision-tree node
F, and the underlying data source for the standalone rate-sheet document still wanted per
the PRD) does **not** respect the flag. It still shows the fuel surcharge as applied, so for
a client with this flag set, the rate sheet actively disagrees with the quote the same client
will actually receive.

**Need:** confirm whether this is a `preview_rate_batch` bug (should read
`waive_all_incidentals` the same way the quote tools do) or intentional (the rate sheet is
meant to show the un-waived reference rate). If intentional, the plugin needs to know to
caveat the rate sheet whenever this flag is set — right now it has no way to know the two
will disagree.

---

## B · Tool surface

### B2 — Passenger pool scope
`resolve_passengers` takes only `travel_coordination_profile_id`.

**Need:** (a) is the pool per TC profile or per company? The Yerdle company has four Ayush
profiles — do they share a pool? (b) What happens on a newly created profile with no
passengers?

> **Downgraded 2026-10-10**, Medium → Low. The second half of the original Need ended
> *"That currently drops us to the approximate path, which A1 says is the wrong price."*
> **Both halves of that are now obsolete:** `passenger_id` is optional (B1, closed), so the
> plugin no longer picks a passenger at all, and there is no approximate path to drop to
> (A1, closed). `QuoteBuilder::PassengerSearch` also removes the 10-passenger cap. The
> question survives only for the case where a user *names* a passenger, which is the one
> path that still resolves one.

### B4 — `scenario_comparison` hides data the payload already carries
The scenario widget renders a condensed card; the `quote_result` widget renders base rate,
effective rate, discount %, billable time and cancellation as tiles. But
`generate_quote_options`' payload **already contains all of those fields** — plus
`minimum_hours`, which `calculate_quote_units` doesn't return.

**Need:** enrich the comparison view (or make each scenario expandable).

> **Downgraded 2026-10-10**, Medium → Low — a workaround shipped, and it is a good one.
> `render_presentation.py` prints Core's own `presentation` block, which gives every CSM the
> same view of the same quote with Core's figures rather than restated ones, and falls back
> to the plugin's own summarizer when a response carries no presentation block. The original
> Need closed with *"Today we make a second `calculate_quote_units` call purely to render the
> detailed card — that call would disappear."* That call is still made (node G2), so the
> saving is still available; the widget's omissions are simply no longer load-bearing.

### B7 — Known commercial flights are unquotable: no airline resolver
Sending a real flight on an airport stop fails:

```
stops: [{ stop_type: "airport", stop_ref: "…",
          flight: { flight_type: "departure", airline_code: "AA", flight_number: "1234",
                    commercial_tbd: false, scheduled_time: "2026-09-25T14:30:00-04:00" } }]
```
> `MCP error -32602: flight.airline must be a resolved airline object with id.`
> `Use commercial_tbd=true if the airline id has not been resolved.`

The schema requires `flight.airline` as a **resolved object with an id**, but no tool in the
MCP resolves one. So whenever a client supplies an airline and flight number (common in
RFPs), the quote call fails.

**Current workaround:** the plugin always sends `commercial_tbd: true` with the flight time
and keeps the flight number as a client-facing note, disclosed to the client as "to be
confirmed". The quote is correct; the reservation just isn't linked to flight tracking. The
seam is written down in `mcp-contract.md` so that when a resolver lands, the next person
knows the shape was understood and consciously deferred rather than missed.

**Need:** a `resolve_airlines` tool (name / IATA code → id), or accept an IATA code directly
on `flight.airline_code`. Either unblocks it. PRD R14. **This is the highest-priority
functional gap in the product.**

### B7b — No FBO resolver either
**Observed (2026-10-07)** The flight object also documents a private form requiring
`private: true` plus `fbo` as a resolved object with an id. There is no FBO resolver, so
private flights are specified and unreachable, exactly as B7 describes for commercial ones.

**Evidence** FBO ids do exist and do come back incidentally — `resolve_itinerary_stops` on
an address near an airport returns them under `nearby_airport`:

```json
"nearby_airport": {
  "airport": {"id": 4655980, "iata_code": "SNA", "display_name": "SNA - John Wayne Arpt Orange Co"},
  "fbo": {"id": 111845, "name": "ACI Jet South", "airport_id": 4655980}
}
```

So the ids are real; what's missing is a way to resolve an FBO the user *names*. Scraping one
out of a `nearby_airport` block would mean guessing that the FBO nearest the pickup is the
one the client is flying into, which is exactly the kind of inference the quote integrity
contract forbids.

*Note for B7's original framing, which contrasted the two: it said "private-flight FBO ids
**are** obtainable" because `resolve_itinerary_stops` returns one incidentally. True of the
ids, not of resolution — a named FBO is as unreachable as a named airline.*

**Need:** an FBO resolver, or confirmation that private flights stay out of scope. PRD R52.

### B9 — `quote_units_unavailable` doesn't say which unit failed
A unit that can't be priced returns:
```json
{"error_type": "quote_units_unavailable", "core_status": 422,
 "client_error": {"code": "quote_units_unavailable", "category": "availability"},
 "presentation": {"data": {"issues": []}}}
```
`issues` is empty. With one unit that's survivable — you re-quote with another vehicle. With
sixteen (a World Cup shuttle programme), there's no way to tell which unit or which vehicle
caused it, so the only recovery is to bisect the payload.

Contrast: when a vehicle fails *inside* a priced unit, the response is precise —
`vehicle_options[].failure.code = "rate_unavailable"` with a per-vehicle message. The
whole-unit path just loses that detail.

**What we do meanwhile** Say plainly that the market has no stored rate for that vehicle and
offer the two routes that work — a different vehicle, or a user-supplied temporary base rate
(PRD R34). Adequate for the no-rate case and inadequate for every other cause, because they
are indistinguishable.

**Need:** populate `issues[]` with the unit key and the per-vehicle failure reasons that the
priced path already produces.

---

## C · Resolver

### C1 — `as_directed` city lookup fails on state abbreviations
`"Dallas, TX"` returns no candidates; `"Dallas, Texas"` works. Also returns nearby cities
(Lake Dallas, Cedar Hill) with no obvious ranking — we match on the pickup's city id.

**What we do meanwhile** Always query `"<City>, <State spelled out>"` and pick the candidate
whose id matches the pickup's city id — deterministic, not a guess, and it asks only if none
matches. Written into the decision tree.

**Need:** accept standard state abbreviations, or document the expected format.

### C2 — Stop-ref TTL undocumented
Observed ~24 hours. We re-resolve after that.

**Need:** the official TTL, so the plugin can pre-empt expiry rather than discovering it on a
failed call.

> **Partially answered by observation, 2026-10-10.** The plugin now relies on "stop refs live
> ~24h" when a user asks for a rate sheet later in a conversation — a measured number
> standing in for a specified one. Worth noting the contrast: a sourcing `market_ref` has its
> own expiry *and* a documented recovery path (`sourcing_reference_expired` → look up again
> from the same reference market and swap each ref). The stop ref should be as clear.

---

## D · Rate configuration (data, not code)

| # | Observation |
|---|---|
| D1 | Yerdle profile: Sedan `CompanyTransferRate` of **$990** against a rack rate of $99 for the same Irvine→Irvine transfer — looks like a decimal slip. |
| D3 | **Chicago** has 8 Mini Buses in market inventory and **no rates at all** (hourly or transfer) — unquotable. |
| D4 | **Executive Van** is unrated in most markets we've touched (Orange County, NYC before a rate was added, Boston). |

> **Context added 2026-10-10.** These surface to the user as "no stored rate", which is now a
> recoverable path rather than a dead end: the CSM supplies a temporary **base** rate and Core
> prices from it (PRD R34). So they cost a conversation rather than blocking the quote — but
> that conversation carries its own risk, since a CSM who enters a partner's cost rather than
> a quoting rate goes out ~23% low (see the *Answered* note under A2/A3).

**Need:** data correction, and ideally a sweep for the same shape elsewhere.

---

## E · Product

### E1 — Host quote documents at a Savoya URL · **P3**
The plugin produces a complete, self-contained HTML quote document (single file, images
inlined, prints to a byte-identical PDF). Today a CSM can only **attach** it. There is nowhere
to point a link at, so "send the client a link" isn't an option.

Why a hosted link beats a PDF attachment:
- **Nothing to quarantine.** Corporate mail filters routinely strip or warn on `.html`
  attachments, and BCD / ExxonMobil / Ritz-Carlton are exactly the recipients whose IT does
  that. A link to `savoya.com` arrives clean.
- **It's on your domain.** A branded URL reads as Savoya; an unknown file attachment reads as
  risk.
- **It can't go stale.** Re-quote and the same link shows the current version, instead of a
  client working from a superseded PDF in their inbox.
- **You'd know when it was opened** — which for a sales team is arguably the most valuable
  part.

**The place probably already exists.** Every Julia and Robyn signature points clients at
`core.savoya.net`, and clients already go there to view reservations. A quote at something
like `core.savoya.net/quotes/<id>` fits the existing mental model.

**Both audiences use the same document.** Internal users (the CSM, their manager, whoever
picks the account up next) need to find it later; the client — often the client's travel
agency rather than the end company — needs to open it without an account. Same artifact, two
very different access paths. Any design that serves only one of them is the wrong one.

**Need:** somewhere to POST a self-contained HTML document and get back a URL.

**Still to brainstorm — not asking for a decision yet, flagging it as the real design
question:**

| Question | The tension |
|---|---|
| **Public-but-unguessable, or login-gated?** | The recipient is frequently BCD or a Ritz concierge — not a portal user, and won't create an account to read a quote. A login gate kills the use case. An unguessable URL is how Docusign, Stripe invoices and most quoting tools do it, but it means pricing is readable by anyone with the link. |
| **Filed under the client profile, or under quotes?** | Under the **client profile** it accumulates into account history — every quote that account has ever had, useful for renewals and for whoever inherits the account. Under **quotes** it's a flat, simpler object that doesn't presume a profile exists (a first-contact RFP may not have one yet). Possibly both: stored as a quote, linked from the profile. |
| **How long does it live?** | A quote has a validity window (currently 7 days on our documents). Does the URL expire with it, show an "expired — contact us" state, or live forever as history? Expiring is safer; living forever is friendlier to the internal audience. |
| **What happens on a re-quote?** | Same URL updated, or a new one? Same-URL means the client can't work from a superseded price — the main argument for hosting. But it also means a link you sent yesterday silently shows different numbers today. |
| **Who can see it internally?** | Anyone at Savoya, or the owning CSM and their team? Pricing and discounts are on the page. |

*Scoped P3: this is a feature request, not a defect. B7 (no airline resolver) fails quotes
outright and should come first. The access model above is worth settling before any code — it
drives the data model.*

---

## F · Core QuoteBuilder & Auth — from reviewing Ethan's change inventory (2026-09-20)

Surfaced while writing the technical design doc against `quote-builder-core-change-inventory.md`
(Ethan Ward), cross-checked against the shipped plugin and against A–E above — not from a live
quoting session, so these are gaps in what's documented, not confirmed plugin bugs. Point of
contact: Ethan Ward, since it's his inventory.

### F1 — Auth0 vs. today's per-CSM OAuth: what does "per end-user identity" actually add?
Today's plugin already authenticates each CSM individually — `README.md`: "OAuth via
`dev.auth.savoya.net`, scope `access:savoya_mcp` … sign in with your Savoya account," a public
PKCE client shared by all installations, **not a single shared identity**.
`Api::V1::QuoteBuilderController` "uses the authenticated Savoya user, limits access to
internal roles" — i.e. it's already per-user internally, same as today.

**Need:** Since both the current path and QuoteBuilder already resolve to an individual Savoya
user, what specifically does moving to Auth0 change? Candidates: (a) it's about a different
kind of "end user" — the client-side recipient, not the CSM, eventually getting an identity of
their own; (b) it's an infra migration off `dev.auth.savoya.net` for reasons unrelated to the
plugin; (c) something else. Worth a plain sentence from Ethan or product before this gets
designed around.

### F2 — Is QuoteBuilder a replacement for the MCP tool surface, or a parallel path?
The inventory is explicit that it's "Core changes only; MCP and connector code are excluded" —
it says nothing about whether `Api::V1::QuoteBuilderController` becomes what the Savoya MCP
server calls internally (invisible to the plugin), or whether the plugin/MCP would eventually
be rewritten to call it directly.

**Need:** This determines how much of the shipped plugin survives unchanged — the
unit-structuring rules, the decision tree, `handoff.py`, and the workarounds (F3, F5) are all
written against today's MCP tool surface. If QuoteBuilder replaces it, the surface these were
written against changes shape.

> **New evidence 2026-10-10 — two things make this more pressing, not less.**
>
> 1. **The cross-market sourcing work landed on the MCP tool surface, not in `QuoteBuilder`.**
>    Three new tools (`lookup_nearby_markets`, `calculate_sourced_quote_units`,
>    `resolve_service_areas`) and two removals (`plan_approximate_quote_units`,
>    `calculate_quote_options`) all happened on the MCP side, with no `QuoteBuilder`
>    involvement and no mention in the change inventory. That is evidence toward "parallel",
>    but it was never stated as a decision.
> 2. **The approximate path has diverged between the two layers.** The plugin removed its
>    approximate path entirely — the tool is gone from the contract and a guard fails the
>    build if any file names it — while the inventory is still building
>    `QuoteBuilder::ApproximateQuotePlanner`. If the plugin is QuoteBuilder's consumer, that
>    service currently has **no consumer at all**; if it is not, the two layers are being
>    built to different pricing philosophies.
>
> **Added to the Need:** who is `ApproximateQuotePlanner` for?

### F3 — Does QuoteBuilder's exact path still require a resolved passenger?
Today's most uncomfortable workaround (B1): the exact-pricing tools require a `passenger_id`,
so the plugin takes the first cached passenger on the profile before any real passenger is
known. `QuoteBuilder::PassengerSearch` is new, but the inventory doesn't say whether
`EstimateOptionsBuilder`/`QuoteUnitsEstimator` still require selecting one.

**Need:** Confirm either way — if the requirement is gone, B1 closes; if not, the same
workaround carries forward and should stay documented as intentional, not re-flagged as a bug
each time someone reviews the code fresh.

> **Narrowed 2026-10-10.** The MCP side answered it: `passenger_id` is now **optional** on
> every pricing tool and Core attaches an eligible passenger to the unsaved calculation itself
> (B1, closed). The question survives only for `QuoteBuilder` — **if its exact path still
> requires one, the workaround B1 just retired comes back on migration.**

### F4 — No-client / rack-only quoting is still unbuilt everywhere
Confirmed in two places independently: the inventory's own limitations list for
`ApproximateQuotePlanner` — "a travel coordination profile is still required; the no-client
path is not implemented" — and the requirement-coverage table. This is a real case
(first-contact RFP, no TC profile yet) the current plugin also can't handle.

**Need:** Is this scheduled anywhere, or explicitly deferred past pilot? It's the one gap that
shows up from three independent angles — current plugin, this document's B-series, and the new
Core work — without ever being picked up.

> **Re-confirmed 2026-10-10**, now from a fourth angle: the plugin's own decision tree at node
> A (no client match → ask for a name, email or profile id; never guess). It blocks **two** PRD
> requirements rather than one — R9 (price without a named client) and R4 (a standalone
> client-facing rate-sheet document), which cannot exist until R9 does.

### F5 — Airline resolver (B7) is confirmed still unaddressed
Worth restating directly rather than leaving it buried above: none of the new
`StopResolution::*` services resolve an airline object, and the inventory's own coverage table
says so — "No dedicated airline lookup" under R14. `flight_builder.rb`'s change is scoped to
commercial-TBD normalization, not to resolving a real flight number. The plugin's
`commercial_tbd: true` workaround is still necessary after this ships.

**Need:** Nothing new to ask — flagging so QuoteBuilder shipping doesn't get mistaken for
solving it. The same now applies to B7b (FBO).

### F6 — Is mixed-fleet quoting on any roadmap?
Explicitly out of scope twice over: `QuoteUnitsEstimator` "compares homogeneous options only …
does not generate mixed fleets," and `ApproximateQuotePlanner` "does not generate mixed-vehicle
combinations." Maps to R19 (manifest grouping) and R21.

**Need:** Confirm whether mixed fleets are a later phase or permanently out of scope for the
API shape chosen — affects how the plugin should represent multi-vehicle programs going forward.

> **Narrowed 2026-10-10.** Partially softened on the MCP side: `generate_quote_options` accepts
> **2–5 named options**, and Core sizes and picks the cheapest candidate **per unit**, so a
> value option may legitimately mix vehicle types *across legs*. What is still absent is a
> mixed fleet **within one movement** — 2 SUVs plus 1 Sprinter for a single leg — which is what
> PRD R21 asks for at full strength. So the question is now specifically about within-leg
> mixing, and R21 is otherwise unblocked and a product decision.

### F7 — Greeter pricing (B8), same open question, new context
`VehicleTypeSearch` returns greeter metadata ("greeter, limited-availability, and
client-bookable metadata") but nothing in the inventory prices a greeter or on-site-coordinator
service — R36 is listed "Not implemented … greeter rates and add-on pricing are excluded."

**Need:** Is a priced greeter/add-on service planned at all, or does this stay a manual,
non-reconciling document line item indefinitely?

> **Answered in part, 2026-10-10.** The MCP side works: greeters price as Core quote units on
> vehicle types 12/13 (B8, closed), so it is **not** a manual line item any more. What survives
> is the question underneath — Core also carries `greeter_fee` fields on every ordinary
> vehicle's quote that no tool can set, which may be a second, different model for the same
> thing. See **G1**; that is where the live question now lives.

### F8 — Rate preview gaps carried forward unchanged
`RateDiscoveryBuilder`'s own limitations list and R23–R25's coverage row name the same gaps: no
no-client rates, no greeter rates, no market fleet count, no explicit discount indicator. Not
new findings — the same shape of gap as this document's B-series, just confirmed to persist in
the new service rather than being fixed by it.

**Need:** Confirm these are roadmapped rather than permanently descoped — rate preview is a
routine, early step in the current plugin flow.

> **Narrowed 2026-10-10.** Of the four, one is resolved by observation and one moved:
> - **Market fleet count — present.** `market_vehicle_count` appears in the presentation rate
>   rows, which also closes PRD R25. It is a *static* count, not date-specific availability.
> - **Greeter rates — still absent, and worse than "absent".** Greeters do not appear in
>   `vehicle_rate_evaluations` *and* are not listed in `missing_vehicle_type_ids`, so the rate
>   sheet is **silently incomplete** rather than reporting a gap. The plugin works around it by
>   attempting a price and reading the answer.
> - **No-client rates** — see F4; the rate preview inherits the same requirement.
> - **No explicit discount indicator** — still open. The preview shows rack and effective
>   rates and the discount is inferable from the difference, but nothing states it as a field.
>
> A fifth omission from the same block is filed separately as **G2**, because it is a field
> missing from one part of a response that carries it in another.

### F9 — International stop-resolution policy is an open product decision
The inventory says it plainly: `StopResolution::Resolver` "Product still needs to define when
an inferred international service area is acceptable," and `GooglePlacesClient`'s international
city matching "need[s] production fixtures." This isn't an engineering gap — it's a product
decision sitting inside an engineering document.

**Need:** This probably belongs on Ayush's own list rather than Ethan's — flagged here since it
was found in Ethan's doc, not because it's his to answer.

> **Sharper 2026-10-10, from live use.** A real London/Sicily/Milan itinerary resolved with
> **Sicily in no Savoya service area at all.** Core reported one market as *both* source and
> primary for those stops and priced them from Naples, billing **14.75 hrs** against a shorter
> request. The plugin handles and discloses it (PRD R57) and it is not a defect — but it means
> "international coverage is inconsistent" understates the case. The real boundary is
> **covered / nearest-market / nothing at all**, and only the first two were ever in the policy
> question.
>
> **Added to the Need:** a stated policy on the no-service-area case specifically — how far a
> nearest-market fallback should reach before a request is refused rather than priced.

### F10 — NFR-2 permission granularity beyond "internal roles"
The inventory calls this open in its own coverage table: NFR-2 "Confirm whether a more specific
existing permission is required" — `QuoteBuilderController` currently allows any internal role.
Same underlying question as F1, from the authorization side rather than the identity side.

**Need:** Whatever answer settles F1 probably settles this too — worth asking together.

> **Worse than it looks, noted 2026-10-10.** PRD NFR-2 ("a user only sees and prices what their
> role allows") has **never been tested on any path** — it is the only requirement in the PRD
> with no evidence in either direction. The plugin inherits whatever the connector grants and
> has no way to check it from inside. A restricted-role test account would settle it.

### F11 — Migration/rollout plan once QuoteBuilder ships
Not a gap in the code — a gap in the plan. The inventory lists regression-testing priorities
(existing reservation creation, stop validation, `/airports/nearby` parity, rate precedence,
exact-quote parity) but nothing about how the plugin itself would cut over: dual-support period,
feature-flag-gated rollout per CSM, or a hard swap once `enable_quote_builder_api` flips on.

**Need:** A rough shape of this — even "not decided yet, here's roughly when we'll think about
it" — is useful before the TDD's architecture gets treated as a moving target.

> **One concrete thing to fold in, 2026-10-10.** The handoff contract between the two skills is
> at **v3** and **rejects** an older handoff rather than interpreting it. If a migration changes
> the response shape, that contract versions again — and a CSM mid-quote when the cutover
> happens gets "re-run the quote", which is correct behaviour and worth planning for rather than
> discovering.

---

## G · Tool-surface findings from the MCP migration (raised in the repo, 8–10 Oct)

### G1 — `greeter_fee` / `adjusted_greeter_fee` exist on the quote object but no tool can set them
*(**G5** was the same observation filed twice, with the same evidence and the same Need. It is
merged here and its id is retired.)*

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

The same shape appears on all five document fixtures, including `boston-offsite/raw_quote.json`
— an ordinary Mini Bus unit with no greeter involved. No argument on `calculate_quote_units`,
`generate_quote_options` or `calculate_temporary_quote_units` accepts a greeter fee, so from the
plugin's side these fields can only ever be read.

**Why it matters.** It suggests Core has a second, different model for greeters: a fee attached
to an ordinary vehicle's quote, rather than the separate greeter unit the plugin builds. The
plugin prices greeters as their own quote units on vehicle types 12 (Hourly
Greeter/Coordinator) and 13 (Single Greet), which works and shipped in 0.23.0 — Core priced id
12 in Orange County at rate 55549, $100.00/hr rack → **$76.99/hr** effective with a 2-hour
minimum, and an Irvine request came to **$404.20**. So nothing is blocked.

But if the fee route is the intended one, a greeter priced as its own unit may be invisible to
whatever downstream reads `greeter_fee`, and the two models would then disagree about what a
booking with a greeter actually costs.

**Need:** confirm which model is intended — a separate greeter quote unit, or a fee on the
vehicle's quote — and if it's the fee, which tool is meant to set it. Also F7.

### G2 — `client_can_book` is missing from the `presentation` rate-preview rows
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

`limited_availability` made it across; `client_can_book` did not. So the rate sheet a CSM reads
does not say a Mini Bus cannot be booked by the client, even though Core knows it in the same
payload.

**What we do meanwhile** Read it from `resolve_vehicle_types` at the vehicle-selection step
rather than enriching Core's presentation block from the evaluations, because mixing sources
into that block is how a rendered view starts drifting from what Core sent.

**Need:** add `client_can_book` to the presentation rate-preview rows, or confirm the omission
is deliberate. PRD R70.

### G3 — `temporary_rate_used` is `false` at aggregate level while the unit says `true`
**Observed (2026-10-08)** A `calculate_temporary_quote_units` call with an explicit temporary
rate returned contradictory flags within one response.

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
top-level aggregate is wrong. A consumer that reads the aggregate flag to decide whether a quote
contains unsaved pricing would get the wrong answer — and that flag is exactly the kind of thing
a document layer checks before printing "temporary rate, not saved" on a client-facing page.

**What we do meanwhile** Read the unit-level flag, never the aggregate.

**Need:** fix the aggregate flag, or confirm it means something other than "any unit used a
temporary rate".

### G4 — The quote response needs the no-local-provider warning *and* `excess_drive_time`
**Observed (2026-10-08)** `resolve_itinerary_stops` returns the sourcing warning; the quote
response does not. The quote response instead sets `excess_drive_time: true`.

**Evidence** Resolving The Westin Whistler returns, with `service_area_source: "nearest"`:

```json
"warnings": ["No local providers are available for this reservation. Availability will be
confirmed from our local providers in Vancouver, Canada. Additional drive time will be
incurred on the reservation."]
```

`calculate_temporary_quote_units` for the same stops returns **no such warning**, and the stop's
own `service_area` comes back `null`. The only quote-side signal is `excess_drive_time: true`,
and the billing consequence is substantial: `duration: 8` on the as-directed stop billed
**12 hours**, 4 of them positioning, at $327.25/hr effective.

**Why both are needed, not one.** They are different facts and a client needs both:

| Signal | What it tells the client |
|---|---|
| no-local-provider warning | **where** the vehicle is coming from — "sourced from our Vancouver partners" |
| `excess_drive_time` | **that** the extra drive time is billed, which is why the hours exceed the request |

`excess_drive_time` alone cannot name the market, so a document built from the quote response
can only say "a neighbouring market". A CSM looking at a 12-hour bill against an 8-hour request,
with no named source, has nothing to tell the client.

**What we do meanwhile** The disclosure fires from either signal, and the wording falls back to
generic when the market is unnamed. The precise name is carried forward through the handoff from
stop resolution — **the only field the plugin carries across its own skill seam purely to cover
a Core gap.** It works only when intake and document run in the same conversation, and it
duplicates something Core already knows.

**Need:** carry the no-local-provider warning, with the sourcing market named, on the quote
response as well. Confirm the two are intended to co-occur: no local provider → sourced from
another market → excess drive time applies. **Closing this retires plugin state**, which is why
it is worth more than its size suggests.

### G6 — Compact response mode, and why it is now a correctness item
*(Filed earlier as **B6**, "compact response mode", Low. B6 is merged here. The request is the
same; the justification changed. B6's original note: each vehicle option is returned up to three
times — `value_option`, `elevated_option`, `vehicle_options[]` — plus a `presentation` block, and
a `compact: true` returning only the chosen option per unit would cut payload roughly 70%.)*

**Observed (2026-10-10)** On a live 16-unit World Cup shuttle quote, four tool responses were too
large to read directly and had to be written to disk and pulled apart with `jq` before the flow
could continue.

**Evidence** From the session capture for `yerdle-world-cup-2027` (16 units: 4 origins × 4 match
dates, one Mercedes Sprinter each, out-and-back hourly with a 4.5-hour wait):

| Tool | Response size |
|---|---|
| `preview_rate_batch` | ~230 KB |
| `generate_quote_options` | ~190 KB |
| `calculate_temporary_quote_units` | ~124 KB |
| `calculate_quote_units` | ~108 KB |

Sixteen units is not an unusual job — it is four shuttles on four dates, and the request that
produced it was two sentences long. A 43-vehicle request would be several times larger again.

**Why this is not a convenience request.** Each response has to be read before the next step can
be chosen, so when one cannot be read the session improvises. In **five separate sessions** the
improvisation was the same: the engine response was **re-typed by hand** into `raw_quote.json`,
recorded each time in the capture's `--workaround` field.

That defeats the plugin's strongest money protection. The document's fail-closed check compares
its own reconstruction of the total against the engine's `aggregate_total` and refuses to render
on any gap. But when the response is hand-typed, **both sides of that comparison come from the
same typing** — `aggregate_total` is read from the same file — so a transcription slip in a line
total propagates to the aggregate and the check cannot see it. Nothing in the plugin can verify a
hand-typed number against a source it does not have.

Most of the volume is repetition, exactly as B6 described. The plugin's own capture slimming drops
`vehicle_options` and `elevated_option` as duplicates of `value_option` and gets about **3×**
smaller doing it, with nothing it needs lost. But that only helps *after* the response has been
received; it cannot help a response that cannot be received.

**What we do meanwhile** Nothing that works. The workaround is the problem.

**Need:** a compact or summary response mode for multi-unit packages — ideally one that omits
`presentation` and collapses duplicated vehicle options, so a 16-unit quote can be read in one
call. A full written spec, including the measured tier sizes, is in
`G6_Compact_Response_Spec_for_Ethan.md`.

---

## Product gaps — owned by the PRD, not by this file

The old **G1–G7** block mirrored product-owned gaps from `Requirements_Quoting_Pilot.md` so Ethan
would see them alongside the engineering-discovered ones. That block is **retired** as of
2026-10-10: its ids collided with the newer G-block above, and the PRD is now the base document
that owns these. They are listed here as pointers only.

| Old id | Gap | Now |
|---|---|---|
| G1 | Standalone client-facing rack-rate-sheet document | **PRD R4** — still a gap, blocked behind R9/F4 |
| G2 | No-client / rack-only route | **PRD R9** — still a gap; engineering side is **F4** |
| G3 | Multiple named vehicle-mix combinations, not just value/elevated | **PRD R21** — **unblocked**: the engine accepts 2–5 named options. A product decision now, except for within-leg mixed fleets (**F6**) |
| G4 | Rate-sheet completeness (buses / greeters / fleet count) | **PRD R24, R25** — **resolved by observation.** Buses and the market fleet count are present. **Greeters are not, and cannot be answered by the rate view at all** — see the F8 annotation |
| G5 | International location & rate coverage unconfirmed | **PRD R15** — still open; engineering side is **F9**, now sharper |
| G6 | NFR-2 auth/permissions never tested | **PRD NFR-2** — still untested; engineering side is **F10** |
| G7 | Luggage-capacity default (~1 bag/pax) | **PRD R22** — a product decision, no engineering dependency |

---

## Answered / closed

*Items move here with the answer and the date, only on Ayush's say-so.*

### A2 — Are effective rates inclusive of the fuel surcharge? · **answered 2026-09-20, by observation**
**Yes — `effective_rate_amount` already folds in both the contracted discount and the fuel
surcharge.**

Verified on a London LGW arrival (profile 201890):
```
base_rate_amount         200.00
discount_basis_points     3000   → × 0.70 = 140.00
fuel_surcharge_basis_points 1000 → × 1.10 = 154.00
effective_rate_amount    153.99   (per-vehicle rounding)
```
So a document must not add a fuel surcharge on top of the effective rate. The plugin
reconstructs from `base_rate_amount`, shows the discount and the fuel surcharge as separate
lines, and reconciles the total to `aggregate_total` exactly.

*No engineering action required — recorded so the answer isn't re-litigated.* One thing worth
confirming when convenient: is the order always **discount then fuel**, or can a market apply
them the other way round? The plugin assumes discount-then-fuel.

> **2026-10-10 — one correction to the mechanism above, and one addition.** The residual is no
> longer "absorbed": absorbing it made the document reconcile *and* made the absorbing line
> misstate its own percentage, and put a 5-vehicle Boston job 30 cents above Savoya's quote.
> Engine line amounts are now **pinned per leg at Core's own granularity** with fuel as the
> remainder, so the total matches by construction and a mismatch **refuses to render**. The
> addition: **discounts are additive in basis points** — 30% contracted plus 10% more is 40%,
> not 37% — which is why an extra discount is a Core re-quote rather than local arithmetic.

### A3 — A profile with a non-zero fuel surcharge · **answered 2026-09-20**
Found one without needing a new profile: **London on profile 201890 returns
`fuel_surcharge_basis_points: 1000` (10%)**, while the same profile returns 0 in US markets. So
the surcharge is **market-scoped, not profile-scoped**.

This also caught a plugin bug — our terms bullet was hardcoded to "5%" and would have printed the
wrong percentage on a London quote. Now read from the engine.

*No engineering action required.*

### A1 — `plan_approximate_quote_units` prices differently from the web app · **closed 2026-10-10, moot**
The original observation, kept because it is why the tool is gone. Same Boston job, same Mini
Bus, same date:

| Path | Rate | Job total |
|---|---|---|
| `plan_approximate_quote_units` | $311.84/hr (base $405 less ~23%) | **$9,355.20** |
| `calculate_quote_units` | $283.50/hr (base $405 less 30%, `discount_basis_points: 3000`) | **$7,945.00** |

The contracted discount on the profile is 30%. The approximate path applied something else — a
**$1,410.20 difference** on one job.

**Closed because the tool was removed from the MCP contract.** The plugin now has **no
approximate pricing path at all**: `mcp-contract.md` records the removal and a guard fails the
build if any file in either skill names the tool. Where the approximate path used to be used, the
plugin either prices normally (a profile with no passenger) or asks the user a question (a market
with no stored rate → a temporary base rate through `calculate_temporary_quote_units`). The
discrepancy can no longer occur, because the path that produced it is gone.

*Open question this leaves on the Core side:* `QuoteBuilder::ApproximateQuotePlanner` is still
being built and now has no consumer on the MCP side — tracked under **F2**.

### B1 — `passenger_id` required for quoting · **closed 2026-10-10, answered by the contract**
`passenger_id` is now **optional** on every pricing tool, and when omitted Core deterministically
attaches an eligible passenger to the unsaved calculation and says so in a warning.

The plugin's workaround is gone: node B (`resolve_passengers`) is skipped unless the user names a
passenger, and the per-profile passenger cache was **removed rather than kept**, because caching
would only keep alive a disclosure the CSM no longer needs to see. PRD Business Rule 2 (a quote
never requires knowing which traveler it is for) is now enforced by omission rather than by a
documented workaround.

*The previous workaround, for the record, and the verification that made it safe:* take the first
passenger on the profile — **pricing is passenger-independent**, confirmed by quoting the same
itinerary against two different passenger ids and getting byte-identical output, same rate id,
same totals, with the name appearing nowhere in the response payload or the rendered widget. The
original Need asked for "a `quote_only: true` flag that bypasses the reservation-builder
requirement, or a system/placeholder passenger per profile", and noted that borrowing a real
client contact's identity for a quote "works but is uncomfortable". **Optional is a better answer
than either.**

*Carried forward:* **F3** — whether `QuoteBuilder`'s exact path matches, or brings the requirement
back on migration.

### B3 — `calculate_quote_options` ignores vehicle capacity · **closed 2026-10-10, moot**
80 passengers against a 41-seat Mini Bus returned `required_quantity: 1`, `quantity: 1`.
`calculate_quote_units` and `generate_quote_options` both size correctly from `passenger_count`.

**Closed because the tool was removed from the MCP contract** and is guarded against, like A1. The
plugin had already stopped calling it — precisely because it ignored headcount — so nothing
changed on this side when it went.

### B5 — `plan_approximate` has no option grouping · **closed 2026-10-10, moot**
Two mutually exclusive scenarios sent in one call were summed: the widget showed **$4,712.40** for
a $693 option and a $4,019.40 option. The engine had no way to know they were alternatives.

**Closed with A1** — the tool is gone. The original Need was conditional on the tool surviving
("Need, if `plan_approximate` survives A1"), and it did not. `generate_quote_options` handles
alternatives correctly via separate per-option totals, which is the path the plugin uses.

### B8 — Does the engine already model greeters? · **closed 2026-10-10, yes — and it ships**
The original observation was that `resolve_itinerary_stops` returns `greeter_required: false` on
the airport object, which suggested greeters were a first-class concept somewhere in Core.

**They are, and they are priceable.** Greeters are separately priceable vehicle types: id 12
"Hourly Greeter/Coordinator" and id 13 "Single Greet", both `greeter: true`, `capacity: null`.
Core priced id 12 in Orange County at rate 55549 — $100.00/hr rack, **$76.99/hr** effective, with
a 2-hour minimum — and an Irvine on-site coordinator request came to **$404.20**. The plugin now
prices greeters as their own quote units (PRD R36), and asks a human for a cost only where the
market genuinely has no greeter rate.

**This mattered more than its priority suggested.** The original Need closed with "Hand-entered
amounts don't reconcile at invoicing", which understated it: a hand-entered *"On-site coordinator
— 4 hrs at $235/hr = $940"* reached a client against Core's $404.20 for the same request —
**2.3× over**. The rule it produced: never ask a human for a number Core has.

*Three things carried forward rather than closed:*
- The rate sheet **cannot answer the greeter question at all** — greeters are absent from
  `vehicle_rate_evaluations` and not listed in `missing_vehicle_type_ids` either, so the plugin
  attempts a price and reads the answer. See the F8 annotation and PRD R24.
- Core appears to have a **second greeter model** that nothing can set — **G1**.
- The original question (a) — what `greeter_required` actually drives, informational vs. pricing
  vs. dispatch — **was never answered**, and is worth asking alongside G1.

### B10 — Cross-market sourcing · **closed 2026-10-10, largely delivered**
Filed 2026-10-06 with six acceptance criteria as Jira `GREEN-371`; **five landed and the plugin
shipped against them within four days.** PRD R48–R51 are now *Built — in validation*, and four
live client quotes have exercised the path.

What landed: `lookup_nearby_markets` (the three nearest markets by **road** distance — the one
part of Core's existing override-service-area feature that had to be *fixed* rather than reused,
since it sorts by linear distance — each with the vehicle types and quantities it *adds*, plus a
signed `market_ref`); `resolve_service_areas`, for anchoring the lookup to any market the CSM
names; and `calculate_sourced_quote_units`, for a mixed-market package priced in one call through
the exact path, primary-market allocations included.

Three findings from live use worth keeping, because none is obvious from the design:

- **A sourced vehicle bills the primary market's rates, not its home market's.** An Austin Mini
  Bus sourced into Dallas billed Dallas's **$314.92/hr**, not Austin's **$244.09/hr**. The nearby
  market supplies the vehicle, not the price.
- **The returned counts are "additional", not totals** — vehicles whose vendors already serve the
  reference market are excluded, because they are already counted there — and they are
  **unconfirmed**, promising nothing about fulfilment.
- **A `market_ref` is scoped to the market it was looked up from**, and nearby is not the same as
  sourceable: Dallas returned only Shreveport, Austin and Oklahoma City, while Houston sits in
  Austin's list.

*Two acceptance criteria carried forward rather than closed:*

1. **AC #2 — a rate sheet for an arbitrary service area.** Obtainable only by resolving locations
   in that market and previewing there; there is no "rates for market X" call. It is also
   hazardous to show naively, per the first finding above — a nearby market's own rates are not
   what gets charged when sourcing from it.
2. **AC #6 — the excess drive-time cost as its own visible line.** Each market's vehicles carry
   their own line item with their own named source market, but the positioning *cost* sits inside
   the billed hours and is disclosed in words rather than shown as a separate money line.

Whether these two become their own items, or ride on a `GREEN-371` follow-up, is Ayush's call —
they are recorded here rather than silently dropped.
