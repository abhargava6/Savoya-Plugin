# greeter-as-directed

A real `calculate_quote_units` response, captured 7 Oct 2026 against profile 201890 in
Orange County: greeter `vehicle_type_id: 12`, pickup + an `as_directed` stop with
`duration: 4`.

Kept because it carries four things at once that nothing else in the suite does:

- a complete **`presentation` block** of view `quote_result`, which is what
  `render_presentation.py` is tested against — the renderer is checked against Core's
  actual output rather than against our idea of it
- the **no-passenger warning** on both the unit and the presentation block, which is the
  one warning B9 suppresses
- **billable hours that are not the hours requested**: `duration: 4` → `billable_hours:
  5.25`, Core's constant +1.25h of positioning time
- `limited_availability: true` and `capacity: null` on a greeter type

Client data: none. The pickup is a hotel and the profile is the internal test account.
