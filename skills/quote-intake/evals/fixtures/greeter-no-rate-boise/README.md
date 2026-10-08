# greeter-no-rate-boise

A real **blocked** `calculate_quote_units` response, 8 Oct 2026: greeter
`vehicle_type_id: 12` in Boise, ID (service area 11217), where no greeter rate exists.
Profile 201890.

This is D1's second and fourth rows — *client asked / no rate* and *CSM added / no rate* —
and it is also **A1's replacement path**, which previously had no test data at all.

What it proves:

- the `blocked` presentation view, with `severity: "error"`
- `client_error.recovery.message` is CSM-ready wording we surface verbatim rather than
  inventing: *"choose another vehicle, provide a temporary rate, or remove the unavailable
  option"*
- `data.issues[]` carries the sentence that names **which** unit failed and why — the most
  useful line in the response, and the one the renderer's first draft dropped
- D1's amended rate check works: attempting to price a greeter is how you learn whether a
  market has a rate, because greeters never appear in `preview_rate_batch`

Pairs with `greeter-as-directed`, which is the same vehicle type in a market that *does*
have the rate.
