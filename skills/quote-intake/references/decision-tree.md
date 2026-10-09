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

Before any exact quote, compare the requested vehicle type and effective quantity with the primary market's unconfirmed inventory. Use an internal rate preview for this check even if the CSM declines a displayed rate preview. If sufficient, stay in the primary market. If short, or the user explicitly asks to explore, use `lookup_nearby_markets`. Show each market's additional vehicle types and counts, noting that vehicles shared with the reference market are excluded. Sourced vehicles are billed at the primary market's rates, so answer rate questions from the primary-market preview. Ask the CSM in chat which market or mix to use, and wait for their answer. Use only the signed lookup reference for a market they explicitly selected, with their vehicle type and quantity, before pricing. If Core reports `market_inventory_shortfall`, give the counts for each returned market or market group (grouped markets share vehicles) and ask for a new split instead of presenting the price. Never infer an override from nearby results. If Core reports `sourcing_reference_expired`, look up nearby markets again and retry with the new reference for the same chosen market; ask again only if that market is no longer returned.

Always ask: best value, comparison, or selected vehicles.

| Need | Tool |
|---|---|
| One selected vehicle per unit | `calculate_quote_units` |
| User-selected market mix | `calculate_sourced_quote_units` |
| Two or more complete value/elevated packages | `generate_quote_options` |
| Temporary rate, temporary discount, or both | `calculate_temporary_quote_units` |

`generate_quote_options` is the comparison tool. Do not create synthetic Option B totals in the document layer.

## F. Temporary pricing

Temporary pricing is non-persisted quote presentation only. Send it only through `calculate_temporary_quote_units`. Every unit in a temporary package must contain a temporary rate or temporary discount. For a sourced package, keep every allocation, primary-market units included, with the same quantities and `source_market_ref` values. A package that would leave only some units temporary is unsupported; never merge totals locally.

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
