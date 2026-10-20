# The Savoya MCP contract — twelve tools

**This file is the contract.** `regress.py`'s tool-contract guard parses the block below
and fails if any instruction file or script names a tool that isn't in it. When the server
changes, edit this file first and let the suite tell you what else has to move.

Last verified **2026-10-09** by reading all twelve tool schemas off the live connector.
The server went from nine tools to twelve on 9 October (cross-market sourcing,
`GREEN-371` / PRD R48–R51) and **nothing told us** — the guard below only fails when
*we* name a tool outside the contract, so it cannot see the server gaining tools. It
was found by re-querying the connector on a hunch. A bidirectional check is still
outstanding.

```tools
resolve_client
resolve_passengers
resolve_itinerary_stops
resolve_vehicle_types
resolve_service_areas
preview_rates
preview_rate_batch
lookup_nearby_markets
calculate_quote_units
calculate_sourced_quote_units
calculate_temporary_quote_units
generate_quote_options
```

## Added 2026-10-09 — cross-market sourcing

| Tool | What it does |
|---|---|
| `resolve_service_areas` | Find a service area by a name the CSM typed, and return its id. Needed only when the CSM anchors the nearby-market lookup somewhere other than the itinerary's own market. Never infer the id from a city name. |
| `lookup_nearby_markets` | The three nearest markets **by road distance** (not linear — that correction was the point), each with the vehicle types and quantities it *adds*, the other listed markets that share some of those vehicles, and a combined distinct count for every market listed so far. Takes `reference_service_area_id` and `inventory_date`; `shown_service_area_ids` pages to the next three nearest, and `service_area_ids` (up to three) returns markets the CSM named at any distance. Returns a signed `market_ref` per market. |
| `calculate_sourced_quote_units` | The exact-quote path when some or all vehicles come from a non-primary market. One allocation per itinerary × vehicle type × source market; primary-market allocations omit `source_market_ref`. `quantity` is **required** here and means *vehicle count*, which is not what it means on `calculate_quote_units`. |

`calculate_temporary_quote_units` also gained `source_market_ref`, so a sourced package
can still be discounted — but every allocation must be resent, primary-market units
included, each carrying the temporary input.

Three things to know that are not in any schema:

- **A `market_ref` is valid for 24 hours, and is scoped to the trip's primary market.**
  Core returns `sourcing_reference_expired` past the window; look the same markets up
  again with `service_area_ids` and retry with the new ref for the same market. A ref
  obtained by looking up from another market is rejected with a
  `source_market_ref_mismatch` issue. Look up from the market you are sourcing *into*.
- **Any service area is sourceable.** The nearby list is a display aid. A market the CSM
  names that is not among the nearest is looked up with `service_area_ids`, at any
  distance, and quoted like any other.
- **Sourced vehicles bill the PRIMARY market's rate**, with the positioning drive time
  inside the line total. Verified live: an Austin Mini Bus sourced into Dallas billed
  Dallas's $314.92/hr, not Austin's $244.09/hr. The nearby market supplies the vehicle,
  not the price — which is why there is no sourcing rate sheet to fetch.
- **Core can return `market_inventory_shortfall`.** Markets returned together share
  vendors, so their *combined distinct* vehicles can fall short even when each market
  alone looks sufficient. Never show a price on a shortfall.
- **Every quote unit takes `inventory_override: true`** (calculate_quote_units, the
  sourced and temporary paths, and options). Set it only after Core reported the
  shortfall and the CSM chose to override it, on the units in the shortfalls they
  overrode. Core then prices the package and puts an `Inventory override: …` warning on
  each affected unit and on the package, plus `overridden_inventory_shortfalls`.
  The warning is internal. A shortfall among units without the flag still blocks.
- **Counts are "unconfirmed"** and exclude vehicles whose vendors already serve the
  reference market — so the number is *additional* supply, not that market's total.
  Say which when presenting it; a CSM reading "SUV 4" will assume four exist there.

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
  view, rendered by `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/render_presentation.py`.
  It is **internal**: it carries rate ids and rack-versus-effective rates, so it never
  becomes client copy. The `actions` intents are read and named, bound to nothing — the
  refine loop stays ours until they are documented.
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
| Known commercial | `flight_type`, `flight_number`, `scheduled_time`, **`airline` as a resolved object with an id** | No — no airline resolver in the contract |
| Private | `private: true`, `flight_type`, `scheduled_time`, **`fbo` as a resolved object with an id** | No — no FBO resolver in the contract |

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
