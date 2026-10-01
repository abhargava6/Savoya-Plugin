# Quote workflow decision tree

Every branch ends in a call, skip, or user question. Core owns all money, vehicle metadata, and capacity sizing.

## A. Client

- A uniquely cached profile: use it.
- Otherwise call `resolve_client`.
- Cache only a unique result or the profile the user explicitly selects.
- Multiple matches: ask. Never cache a preselection or ambiguous result.

## B. Passenger

- User named a passenger: call `resolve_passengers` and send the selected `passenger_id`.
- No passenger named: skip passenger resolution and omit `passenger_id`.
- Always send `passenger_count`; Core uses it for quantity/capacity sizing.

## C. Stops and flights

Call `resolve_itinerary_stops` once with deduplicated stops. Keep the existing flight construction unchanged: airport pickups use arrival, airport drop-offs use departure, and `commercial_tbd: true` is allowed with the current placeholder-time behavior.

## D. Rate-sheet decision

Always ask. If yes, call `preview_rate_batch` with `display: "show"`. If no, do not display one. A preview needed only for request construction uses `display: "internal"`.

Preview and `resolve_vehicle_types` output—not a plugin table—supply current vehicle IDs and capacities.

## E. Quote mode

Always ask: best value, comparison, or selected vehicles.

| Need | Tool |
|---|---|
| One selected vehicle per unit | `calculate_quote_units` |
| Two or more complete value/elevated packages | `generate_quote_options` |
| Temporary rate, temporary discount, or both | `calculate_temporary_quote_units` |

`generate_quote_options` is the comparison tool. Do not create synthetic Option B totals in the document layer.

## F. Temporary pricing

Temporary pricing is non-persisted quote presentation only. Send it only through `calculate_temporary_quote_units`. Every unit in a temporary package must contain a temporary rate or temporary discount. A package that would leave only some units temporary is unsupported; never merge totals locally.

## G. Result gate

Before handoff, require:

- `estimate_type: exact` on every unit;
- one complete selected package;
- `persisted: false`;
- Core-returned quantities, unit totals, line totals, and aggregate total;
- no locally calculated money.

Summarize using `handoff.py summarize`. Let the user refine; re-call the appropriate tool for every monetary or vehicle change.

## H. Handoff

Write contract version 3 with the selected raw result and exact source request. Then ask whether to build a document. A no-document path still uses the existing capture flow.
