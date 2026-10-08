# comparison-two-options

A real `generate_quote_options` response, 8 Oct 2026, profile 201890: value (candidates
`[1, 8]`) against elevated (fixed `143`), one trip, Irvine → Anaheim.

Covers the **`scenario_comparison`** presentation view and the new `options[2..5]` call
shape from B4.

- Response is **nested**: top-level `options[]`, each with its own `result` carrying
  `quote_units` and `aggregate_total`. There is no top-level aggregate, which is why the
  renderer's presentation/units cross-check correctly stays silent here rather than
  comparing against a number that doesn't exist.
- `presentation.actions` carries **one `select_scenario` per option** with a
  `selection_key`. The renderer prints each distinct intent once; before that it read
  "select_scenario, select_scenario".
- **`vehicle_options[]` shows the candidate that lost**: Sedan $346.50 priced against SUV
  $372.68 within the value option. Core prices every candidate and keeps the lowest — and
  returns all of them. That is a free per-leg comparison we currently discard, and the
  nearest existing thing to the multi-source shape GREEN-371 will need (E1).
- `strategy` round-trips as the label it is. It is in the response because we sent it, not
  because Core did anything with it.
