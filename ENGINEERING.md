# Open items for Savoya engineering

Observations from building and testing the `savoya-quoting` plugin that need a decision or
a change on the Savoya side. Each item records **what was observed**, the **evidence** (real
tool responses and real numbers, never paraphrase), and a one-line **Need**.

**Nothing here is marked done.** A resolved item moves to *Answered / closed* with the
answer and the date, and only when Ayush says it is resolved.

> **⚠ This file was started in the repo on 2026-10-08 and needs reconciling with the
> existing copy.** `CLAUDE.md` has always referred to an `ENGINEERING.md` holding item
> **B7** (no airline resolver), but no copy exists under `~/Documents/Savoya MCP`, so the
> prior items are not reproduced here — only a stub for B7, below, so the reference in
> `CLAUDE.md` still resolves. Item ids **G1–G3** are provisional: the existing numbering
> isn't visible from here. On merge, renumber and fold the B7 stub into the real entry.

## Index

| # | Item | Raised | Status |
|---|---|---|---|
| **B7** | No airline resolver, so flights can only go as `commercial_tbd` — **stub, see note above** | before 2026-10-08 | Open |
| **B7b** | No FBO resolver either, so private flights are specified but unreachable | 2026-10-07 | Open |
| **G1** | `greeter_fee` exists on the quote object but no tool can set it | 2026-10-08 | Open |
| **G2** | `client_can_book` is missing from `presentation` rate-preview rows | 2026-10-08 | Open |
| **G3** | `temporary_rate_used` is `false` at aggregate level while the unit says `true` | 2026-10-08 | Open |
| **G4** | The quote response carries `excess_drive_time` but not the no-local-provider warning — we need **both** | 2026-10-08 | Open |

---

## B7 — No airline resolver *(stub)*

Placeholder so `CLAUDE.md`'s reference resolves. The substance lives in Ayush's copy of this
file; fold this stub into it rather than keeping both.

**In short:** the flight object documents a known-commercial form requiring `airline` as a
resolved object with an id, and no tool among the nine resolves an airline. So the plugin
sends `commercial_tbd: true` on every airport stop, even when the client supplied a flight
number, and keeps the number as a client-facing note.

**Need:** confirm whether an airline resolver is coming, or that TBD stays the only
supported shape.

## B7b — No FBO resolver either

**Observed (2026-10-07)** The flight object also documents a private form requiring
`private: true` plus `fbo` as a resolved object with an id. There is no FBO resolver among
the nine tools, so private flights are specified and unreachable, exactly as B7 describes
for commercial ones.

**Evidence** FBO ids do exist and do come back incidentally — `resolve_itinerary_stops` on
an address near an airport returns them under `nearby_airport`:

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

**Need:** an FBO resolver, or confirmation that private flights stay out of scope.

## G1 — `greeter_fee` exists on the quote object but no tool can set it

**Observed (2026-10-07, confirmed 2026-10-08)** Every quote response carries greeter-fee
fields on the `quote` object, always null in our calls:

```json
"adjusted_greeter_fee": null,
"greeter_fee": null,
"greeter_fee_in_vendor_currency": 0,
"adjusted_greeter_fee_in_vendor_currency": 0
```

So Core can apparently attach a **greeter fee to an ordinary vehicle's quote** — distinct
from pricing a greeter as its own quote unit. Nothing in the nine tool schemas sets it; I
checked `calculate_quote_units`, `calculate_temporary_quote_units` and
`generate_quote_options`.

**Why it matters.** Greeters *are* separately priceable vehicle types — id 12 "Hourly
Greeter/Coordinator", id 13 "Single Greet", both `greeter: true`, `capacity: null` — and
that path works. Core priced id 12 in Orange County at rate 55549, $100.00/hr rack →
**$76.99/hr** effective, 2-hour minimum. But an Irvine quote that reached a client carried a
**hand-entered "On-site coordinator — 4 hrs at $235/hr = $940"** against Core's **$404.20**
for the same request — 2.3× over. If the greeter-fee field is the intended route, we are
about to build the other one.

**Need:** is `greeter_fee` on an ordinary unit the intended way to price on-site staff, or
is a greeter quote unit (vehicle type 12/13) correct? If the fee field is intended, it needs
to be settable.

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
omission is deliberate.

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
kind of thing a document layer would check before printing "temporary rate, not saved" on a
client-facing page.

**What we do meanwhile** Read the unit-level flag, never the aggregate.

**Need:** fix the aggregate flag, or confirm it means something other than "any unit used a
temporary rate".

## G4 — The quote response needs the no-local-provider warning *and* `excess_drive_time`

**Observed (2026-10-08)** `resolve_itinerary_stops` returns the sourcing warning; the quote
response does not. The quote response instead sets `excess_drive_time: true`.

**Evidence** Resolving The Westin Whistler returns, with
`service_area_source: "nearest"`:

```json
"warnings": ["No local providers are available for this reservation. Availability will be
confirmed from our local providers in Vancouver, Canada. Additional drive time will be
incurred on the reservation."]
```

`calculate_temporary_quote_units` for the same stops returns **no such warning**, and the
stop's own `service_area` comes back `null`. The only quote-side signal is:

```json
"excess_drive_time": true
```

and the billing consequence, which is substantial — `duration: 8` on the as-directed stop
billed **12 hours**, 4 of them positioning, at $327.25/hr effective.

**Why both are needed, not one.** They are different facts and a client needs both:

| Signal | What it tells the client |
|---|---|
| no-local-provider warning | **where** the vehicle is coming from — "sourced from our Vancouver partners" |
| `excess_drive_time` | **that the extra drive time is billed**, which is why the hours exceed the request |

`excess_drive_time` alone cannot name the market, so a document built from the quote
response can only say "a neighbouring market". A CSM looking at a 12-hour bill against an
8-hour request, with no named source, has nothing to tell the client.

**What we do meanwhile** The disclosure fires from either signal, and the wording falls back
to generic when the market is unnamed. The precise name would also be fixable on our side by
carrying the resolution warning through the handoff — but that only works when intake and
document run in the same conversation, and it duplicates something Core already knows.

**Need:** carry the no-local-provider warning (with the sourcing market named) on the quote
response as well, alongside `excess_drive_time`. Confirm the two are intended to co-occur:
no local provider → sourced from another market → excess drive time applies.

---

## Answered / closed

*(Nothing yet. Items move here with the answer and the date, only on Ayush's say-so.)*
