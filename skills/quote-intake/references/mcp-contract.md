# The Savoya MCP contract — nine tools

**This file is the contract.** `regress.py`'s tool-contract guard parses the block below
and fails if any instruction file or script names a tool that isn't in it. When the server
changes, edit this file first and let the suite tell you what else has to move.

Last verified **2026-10-07** by reading all nine tool schemas off the live connector.

```tools
resolve_client
resolve_passengers
resolve_itinerary_stops
resolve_vehicle_types
preview_rates
preview_rate_batch
calculate_quote_units
calculate_temporary_quote_units
generate_quote_options
```

## Removed — do not call, do not reference

```tools-removed
plan_approximate_quote_units
calculate_quote_options
```

| Tool | Gone by | What it did |
|---|---|---|
| `plan_approximate_quote_units` | 2026-10-07 | The approximate/estimate path. Accepted `custom_rates` and `custom_discount_basis_points`; replaced by `calculate_temporary_quote_units`. |
| `calculate_quote_options` | 2026-10-07 | Priced one vehicle and ignored headcount. Was already under a never-call rule. |

A name listed above is tolerated **in this file and nowhere else** — recording what left the
contract is this file's job. The guard allows exactly these two names here, so a third dead
tool cannot hide in this prose either.

Both were live on 22 September and gone by 7 October. Plugin 0.22.0 still routed to them,
which is why 0.22.1 exists. **Nothing told us** — that is what the guard is for.

---

## Resolution

**`resolve_client`** — `query` (name, email, company or profile id). Always first.

**`resolve_passengers`** — call **only when the user names a passenger**. `passenger_id` is
optional everywhere; omitted, Core deterministically attaches an eligible passenger to the
unsaved quote calculation and returns a warning saying so. Do not cache, do not pre-flight.

**`resolve_itinerary_stops`** — `stops[1..25]`, each `{key, query, stop_type}`.
`stop_type` is `address` | `airport` | `as_directed`. Returns opaque `stop_ref` tokens,
good for roughly 24h. Reuse an unchanged `stop_ref` across previews, dates and options;
re-resolve only what changed or was rejected. **Pickup can never be `as_directed`.**

**`resolve_vehicle_types`** — authoritative for `id`, `name`, `capacity`, `classification`,
`greeter`, `bus`, `limited_availability`, `client_can_book`. Capacity is `null` on greeter
types. Catalog membership does **not** imply a rate exists in a market.

## Rate discovery

**`preview_rates`** — one itinerary. **`preview_rate_batch`** — up to 40 trips/dates; the
server splits the work and returns one table per service area. `display: "show"` when the
user asked for a rate sheet; `display: "internal"` when previewing to choose vehicles.

Covers **capacity-bearing vehicles only**. Greeter types do not appear in
`vehicle_rate_evaluations` and are not listed in `missing_vehicle_type_ids` either — Core
does not consider them missing. To learn whether a greeter rate exists, price one.

## Pricing

**`calculate_quote_units`** — one package of trips bought together, all contributing to one
total. Per unit, required: `travel_coordination_profile_id`, `pickup_date` (with timezone
offset), **one** `vehicle_type_id`, `stops[2..25]`. Candidate lists are **not accepted**
here. Up to 40 units.

**`generate_quote_options`** — comparisons. `options[2..5]`, each with its own `key`,
`label` and a complete `quote_units` list. **Every option must contain every trip**, and
Core enforces it: a duplicate option is rejected outright (*"labels alone do not create an
alternative"*). Candidate `vehicle_type_ids` **are** allowed here — Core prices each and
takes the lowest successful total per unit.

`strategy` is an enum of five (`value`, `elevated`, `cost_saving`, `quality_focused`,
`custom`) and is a **presentation label only**. Verified 7 Oct: the same two options run
twice with only the strategy strings swapped returned identical totals, vehicles,
quantities and rate ids. Selection comes from the vehicle argument, never the label.

**`calculate_temporary_quote_units`** — the only tool that accepts user-supplied pricing.
Same required args as `calculate_quote_units`, plus **at least one** of:

- `temporary_rate` — `rate_type` (`hourly` | `transfer`), `amount` in **cents**, optional
  `label`, `cancellation_hours`, `minimum`. Omitting the last two inherits the ordinary
  quote's terms; supply `cancellation_hours` when no ordinary rate exists.
- `temporary_discount` — `basis_points` (500 = 5%), optional `label`. Additive to the saved
  client discount and run through Core's normal discount formula.

Never persisted, never accepted by reservation APIs. Say so when presenting the number.
The "at least one" rule is in the tool description, not the JSON schema — Core enforces it,
the schema won't catch it for you.

**A `transfer` rate needs exactly two stops.** A three-stop out-and-back with
`rate_type: "transfer"` returns `quote_units_unavailable` (Core 422, verified 7 Oct). The
under-3-hour waiting rule produces that shape routinely, so **a waiting leg can only take
an hourly temporary rate.**

## Things Core owns that the plugin must not recompute

- **Vehicle quantity.** `passenger_count` + capacity → `required_quantity`, with
  `capacity_adjusted: true`. 80 passengers returned 2 Mini Bus / 14 SUV / 7 Sprinter in one
  call. Prefer `passenger_count` and omit `quantity` unless the user fixed a vehicle count.
- **Billable hours.** `duration` is the lever but not the answer: an as-directed greeter
  sent `duration: 2` billed 3.25 hours and `duration: 4` billed 5.25 — a constant +1.25h of
  positioning time. Send what the user asked for; display what Core billed; never
  back-solve the duration.
- **Every total.** `unit_total`, `line_total`, `aggregate_total`,
  `pricing_summary.total_amount`. Copy and validate; never reconstruct.

## Shapes worth knowing

- **`vehicle_options[]`** on each unit returns **every candidate Core priced**, each with
  its own `unit_total`, `quantity`, `line_total`, `rate_id` and `pricing_summary` — not just
  the winner. A free per-leg comparison, and the nearest thing to the multi-source shape
  GREEN-371 will need.
- **`presentation`** on every response: a `view` (`rate_preview`, `scenario_comparison`,
  `quote_result`, `blocked`), a `title`, severity-tagged `warnings`, pre-formatted rows, and
  `actions` carrying intents (`select_scenario`, `refine_quote`). This is the CSM-facing
  view. It is **internal**: it carries rate ids and rack-versus-effective rates, so it
  never becomes client copy.
- **Blocked responses** carry `status: "blocked"`, a typed `error_type`, a `client_error`
  with `category` and a CSM-ready `user_message`, and a `recovery` block with an actionable
  next step. Surface that wording rather than inventing one.

## Limits

| | |
|---|---|
| Stops per unit | 2–25 (`requested_stop_count` same range) |
| Quote units per call | 1–40 |
| Comparison options | 2–5 |
| Preview trips/dates | up to 40 |
| `duration` | **hours** — `2`, `0.5`, `0.25`. Never minutes. |
| `query` inside a pricing call | forbidden (`{"not": {}}`) — `stop_ref` only |

## Flights — one shape reachable, two specified

| Form | Needs | Reachable? |
|---|---|---|
| Commercial TBD | `commercial_tbd: true`, `flight_type`, timezone-aware `scheduled_time` | **Yes — the only one we send** |
| Known commercial | `flight_type`, `flight_number`, `scheduled_time`, **`airline` as a resolved object with an id** | No — no airline resolver among the nine |
| Private | `private: true`, `flight_type`, `scheduled_time`, **`fbo` as a resolved object with an id** | No — no FBO resolver among the nine |

An FBO id does appear inside `resolve_itinerary_stops` results, under
`nearby_airport.fbo` (e.g. `{"id": 111845, "name": "ACI Jet South"}`), so the ids exist and
are reachable incidentally — but there is no tool that resolves an FBO the user names. Both
gaps are deliberate deferrals, not oversights: see `ENGINEERING.md` B7 and its FBO sibling.

---

**Provenance.** `resolve_client`, `resolve_itinerary_stops`, `calculate_quote_units` and
`calculate_temporary_quote_units` argument lists were read off the live schemas in this
repo's own session and are exact. The remaining five were read on 7 Oct and recorded in
`docs/0.23-contract-delta.md`; their argument detail is summarised rather than
transcribed, so check the live schema before relying on an argument this file doesn't name.
