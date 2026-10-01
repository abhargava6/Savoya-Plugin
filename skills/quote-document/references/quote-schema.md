# Canonical presentation schema

`quote.json` is a presentation-safe copy of one selected exact Core result. It is never a second source of pricing truth.

| Presentation field | Authoritative source |
|---|---|
| `total_cents` / `engine_total_cents` | `raw_quote.aggregate_total` |
| `package_subtotal_cents` | top-level `pricing_summary.subtotal_amount`, only when present |
| `legs[].vehicle.quantity` | `quote_units[].quantity` |
| `legs[].pricing.unit_total_cents` | `quote_units[].unit_total` |
| `legs[].pricing.line_total_cents` | `quote_units[].line_total` |
| `base_rate_cents` | `pricing_summary.rate.base_rate_amount` |
| `effective_rate_cents` | `pricing_summary.rate.effective_rate_amount` |
| unit subtotal and temporary discount amount | returned pricing-summary fields, only when present |

Copy by field presence, not truthiness: `0` is valid. Missing fields stay missing. Do not infer a subtotal, adjustment amount, alternate option total, or package total.

`internal.raw_quote_path` points verification back to the authoritative result. Verification compares direct fields and intentionally does not assert that line totals sum to the aggregate total.
