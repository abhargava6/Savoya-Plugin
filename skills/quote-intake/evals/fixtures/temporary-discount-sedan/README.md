# temporary-discount-sedan

A real `calculate_temporary_quote_units` response, 8 Oct 2026, profile 201890. Sedan,
Irvine → Anaheim, with `temporary_discount: {basis_points: 1000, label: "Event discount"}`.

**This fixture is the proof that C1 needs no local arithmetic.** Core returns every number
the document needs:

| Field | Value |
|---|---|
| `subtotal_amount` | **$346.50** — before the temporary discount |
| `total_amount` | **$297.00** — after |
| `temporary_discount_amount` | **$49.50** |
| `temporary_discount_label` | `"Event discount"` |
| `discount_basis_points` | 3000 (the saved client discount) |
| `temporary_discount_basis_points` | 1000 |
| `effective_discount_basis_points` | **4000** |

Two things to note:

- **Discounts are additive in basis points, not compounded.** 3000 + 1000 = 4000, not
  1 − (0.70 × 0.90) = 3700. Our old local `recompute()` compounded in list order, which
  would have produced a different number.
- **Standard → discount → net is now Core's, end to end.** `subtotal_amount` is the
  "before" the rate card has always wanted, and the label is the line's name. Nothing is
  left for the plugin to calculate.

Reconciled in integer cents: 22500 × (1 − 0.40) × 1.10 = 14850/hr, × 2 hrs = 29700, and
34650 − 29700 = 4950 exactly. (Checking this in floating point fails by 4e-12, which is its
own argument for the integer-cents rule.)
