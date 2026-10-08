# rate-preview-orange-county

A real `preview_rate_batch` response, 8 Oct 2026, profile 201890, Irvine Marriott →
Anaheim Convention Center on 2027-03-20. Verbatim, including both `hourly_rates` and
`vehicle_rate_evaluations` — the renderer only reads `presentation`, but the first draft of
this fixture trimmed those and a trimmed fixture cannot test code that later reads them.

The `rate_preview` presentation view, which lives under **`data.groups[]`** with a `rows`
array per vehicle type. The renderer was first written against a guess
(`scenarios`/`service_areas`/`rows`) and fell through to a generic dump; it was corrected
against this capture.

Facts worth keeping:

- **No transfer rates exist in this market for this pair** (`transfer_rates: []`, warning
  "No transfer rates found"), so a 23-minute hop prices *hourly* and pays the vehicle's
  minimum. Mini Bus carries a 5-hour minimum and a 72-hour cancellation window.
- **Exec Van is capacity 14** with no rates at all, and **Coach Bus is 50** with none
  either — both `hourly_rate_not_found, transfer_rate_not_found`.
- `market_vehicle_count` per type (Sedan 16, SUV 23, Sprinter 3) is a field we never had.
- **No greeter types appear**, and `missing_vehicle_type_ids` is `[]` — Core does not
  consider them missing. This is why D1's rate check has to be an attempted price.
- **`client_can_book` is in `vehicle_rate_evaluations` but NOT in the presentation rows.**
  So the rate sheet a CSM reads does not say a Mini Bus can't be client-booked, even though
  Core knows it in the same response. We read that field at node C instead
  (`resolve_vehicle_types`), and the gap is logged for engineering rather than patched by
  enriching Core's block.
