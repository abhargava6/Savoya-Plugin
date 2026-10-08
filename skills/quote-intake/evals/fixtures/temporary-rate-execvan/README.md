# temporary-rate-execvan

A real `calculate_temporary_quote_units` response, 8 Oct 2026, profile 201890. Exec Van
(id 25) in Orange County, which has **no stored rate** — so this is A1's replacement path
with real data, and it is the only fixture covering a temporary rate.

Sent: `temporary_rate: {rate_type: "hourly", amount: 25000, cancellation_hours: 24,
minimum: 4, label: "Partner-supplied Exec Van rate"}`.

## ▲ The finding that matters more than the fixture

**The supplied rate is a base rate, and the client's discount comes off it.**

| | |
|---|---|
| Supplied | **$250.00/hr** |
| Effective, after 30% discount + 10% fuel | **$192.50/hr** |
| Total, 4-hour minimum | **$770.00** |

The schema does say "before existing client adjustments", so this is documented behaviour
— but a CSM who types in **the partner's cost** quotes the client **23% below cost**. That
is a margin leak, not a display quirk, and it has to be said at the point the number is
asked for.

## Other facts

- `rate_id: null`, `rate_type: "CustomHourlyRate"`, `rate.source: "custom"` — a temporary
  rate is distinguishable from a stored one in three places.
- Core turns our `label` into CSM-visible provenance: *"Partner-supplied Exec Van rate was
  used for this quote and was not saved in Savoya."* Labels are read, so write them to be.
- `minimum: 4` and `cancellation_hours: 24` were both honoured.
- **`presentation.data.pricing.adjustments.temporary_rate_used` is `false` while the unit
  says `true`.** Core's own presentation block contradicts its own unit at the aggregate
  level. Logged for engineering; we read the unit.
