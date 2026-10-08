# capacity-80pax-minibus

A real `calculate_quote_units` response, 8 Oct 2026, profile 201890. 80 passengers,
Mini Bus (capacity 41), Irvine Marriott → Anaheim Convention Center.

**C5's whole justification, demonstrated.** Core decided the fleet size:

| | |
|---|---|
| `passenger_count` sent | 80 |
| `vehicle_capacity` | 41 |
| `required_quantity` | **2** |
| `capacity_adjusted` | **true** |
| Per vehicle | $1,574.60 |
| Line total | **$3,149.20** |

We sent no `quantity`. The plugin currently multiplies this out itself; under the new
contract it copies.

Two further facts this fixture pins:

- **A 23-minute hop billed 5 hours.** There is no transfer rate for this pair in Orange
  County, so it priced hourly, and the Mini Bus rate carries a **5-hour minimum** and a
  **72-hour cancellation window** — far longer than the sedan's 2 and 2. `quoted_time` is
  1.5 while `billable_hours` is 5. A CSM needs the minimum visible or the total looks wrong.
- `limited_availability: true` on Mini Bus, which the rate preview also reports.
