# Client-safe translation rules

The engine talks to Savoya staff. The document talks to the client. This table is the boundary. Scripts enforce the mechanical rows; you enforce the judgment rows when assembling DOCX/XLSX by hand.

## Never shown to the client
| Engine field / phrase | Why |
|---|---|
| `rate_id`, `rate_record_type`, `rate_source: rack` | Internal pricing plumbing |
| `market_vehicle_count`, "inventory" | Availability is confirmed at booking, not implied in a quote |
| `transfer_rate_not_found`, "hourly fallback", "No transfer rates found" | Internal reason codes; the client just sees "billed hourly" |
| `capacity_adjusted`, `requested_quantity` vs `required_quantity` | Show the final quantity only |
| `custom_discount_basis_points`, `temporary_rate_used` | Show the discount as a labeled line, never the mechanism |
| `travel_coordination_profile_id`, `passenger_id` | Internal identifiers |
| `estimate_type: approximate` as a word | Covered by the terms bullet; don't put "approximate" in a heading |

## Always shown, in plain language
| Engine fact | Client wording |
|---|---|
| `pricing_method: hourly`, `billable_hours: 6`, `minimum_hours: 6`, rate | "6 hours × $311.84/hr (6-hour minimum)" |
| `pricing_method: transfer` | "Transfer" — and the wait-time rule from terms applies |
| `cancellation_hours: 48` | "Cancellation: 48 hours' notice" on every leg — it varies by vehicle and by event, so per-leg, not global |
| `quantity: 3`, `capacity: 41` | "3 × Mini Bus (41 passengers each)" |
| `special_event: { name }` | A visible callout on that leg: "Event pricing in effect for [name]: [N]-hour minimum, [N]-hour cancellation." This is the one engine warning that must reach the client |
| `flight.commercial_tbd: true` | "Flight details to be confirmed" next to the airport stop |
| Intermediate stop with `duration` | "Wait at [stop] — approx. 2¼ hours" |
| Warning "No local providers … confirmed from our local providers in [city] … additional drive time" | A line note on that leg: "Vehicles for this service are positioned from our [city] partners; additional drive time is included in the reservation." The normalizer adds this automatically — keep it. It changes what the client is paying for |
| Engine discount (`custom_discount_basis_points`) | Standard rate on the line; "Preferred client discount (N%)" in the breakdown. Never the words "basis points", "custom", or "temporary" |

## Judgment calls
- **Airport labels.** The engine returns an airport *id*, not a name. Use the `display_name` from `resolve_itinerary_stops` (e.g. "BOS – Boston Logan International"). Never ship "Stop 2".
- **Leg headings.** The engine `label` is whatever the user typed in the tool call. Rewrite it for the client: date, purpose, route. "Wednesday, September 16 — Offsite: Hyatt Regency → Rowes Wharf → Hyatt Regency."
- **Placeholders.** If a flight time, date, or address was a placeholder, the document says "to be confirmed" *and* you tell the user in the chat which values were placeholders. Both, every time.
- **Comparisons.** Present complete Core-generated options during intake. Select one complete option before generating a document; never mix alternatives or synthesize a second total in the document layer.
- **Discounts.** Label with what it is, not the mechanism: "Preferred client discount (10%)", not "custom discount 1000 bps".
- **Fuel surcharge.** Line item only if the engine result carries one or the user added one. The terms bullet about the 5% surcharge stays regardless — it's contract text.
- **Rounding.** Cents everywhere; format as `$5,613.12`. Never round a total to the dollar in a client document.
