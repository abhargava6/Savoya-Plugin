# quote.json — canonical quote schema

`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/normalize_quote.py` produces this from raw engine output. Every renderer reads only this file. Edit by hand where marked ✎; leave engine-derived numbers alone.

```jsonc
{
  "meta": {
    "client": "Yerdle",                       // ✎ required
    "profile_id": 201890,
    "prepared_by": "Ayush Bhargava",           // ✎
    "prepared_on": "2026-09-14",
    "valid_until": "2026-09-21",               // ✎ default: prepared_on + 7 days
    "estimate_type": "exact",                  // from engine: always "exact" now — the approximate path is gone
    "currency": "USD",
    "title": "Boston Offsite — Ground Transportation",  // ✎ optional; default "Ground Transportation Quote"
    "reference": null,                         // ✎ optional external ref (Salesforce opp, etc.)
    "travel_coordinator": "Desiree Strobel",   // ✎ client-side TC, shown in header
    "service_area": "Boston, MA"               // from first leg's stops; ✎ override for multi-market
  },
  "legs": [
    {
      "key": "offsite_9_16_minibus",           // engine unit key
      "ref": "A1",                             // auto-assigned A1, A2 … in order; ✎ renumber if you reorder legs
      "service_area": "Boston, MA",
      "label": "Wed 9/16 Offsite …",            // ✎ client-facing heading
      "date": "2026-09-16T17:45:00-04:00",
      "passenger_count": 120,
      "vehicle": { "name": "Mini Bus", "capacity": 41, "quantity": 3 },
      "stops": [
        { "label": "Hyatt Regency Boston Harbor", "address": "101 Harborside Drive", "kind": "address" },
        { "label": "Classic Harbor Line Boston", "address": "60 Rowes Wharf", "kind": "address", "wait_hours": 2.25 },
        { "label": "BOS – Boston Logan International", "kind": "airport",   // ✎ fix "Stop N" labels here
          "flight": { "tbd": true, "type": "departure", "scheduled_time": "2026-09-18T14:30:00-04:00" } }
      ],
      "pricing": {
        "method": "hourly",                    // hourly | transfer
        "rate_cents": 31184,
        "billable_hours": 6,                   // hourly only
        "minimum_hours": 6,                    // hourly only
        "cancellation_hours": 48,
        "special_event": null,                 // or { "name": "US Open" }
        "per_vehicle_cents": 187104,
        "line_total_cents": 561312
      },
      "client_notes": [],                      // ✎ ALWAYS a list of strings, one per note — never a bare string (a string renders one character per line). The normalizer pre-fills the out-of-market note when the engine warned
      "alternative_of": null,                  // set by --alternative altKey:primaryKey → this leg is Option B, ref "B1", excluded from Option A totals
      "engine_discount_pct": 20.0              // present when the engine applied a discount; line shows standard rate
    }
  ],
  "option_b": {                                // computed when any leg has alternative_of
    "alt_subtotal_cents": 400000, "carried_subtotal_cents": 800000, "carried_refs": ["A2"],
    "subtotal_cents": 1200000, "total_cents": 960000   // program total: swapped lines + unchanged Option A lines, global adjustments applied
  },
  "engine_subtotal_cents": 935520,            // sum of selected legs — computed, never edited
  "adjustments": [                             // managed by apply_adjustments.py; engine-sourced lines sort first and survive --clear
    { "label": "Preferred client discount", "type": "percent", "value": -20, "applies_to": null, "source": "engine", "amount_cents": -320000 },
    { "label": "Fuel surcharge", "type": "percent", "value": 5, "applies_to": null, "amount_cents": 46776 },
    { "label": "Special handling", "type": "flat", "value": 150, "applies_to": "offsite_9_16_minibus", "amount_cents": 15000 }
  ],
  "total_cents": 997296,                       // computed
  "personalization": {                         // ✎ see personalization.md
    "cover": "event-planners",                 // audience cover key, or "custom"
    "cover_image_url": null,
    "client_logo_url": null,
    "event_name": null,
    "intro_note": null,
    "pull_quote": null,
    "pull_quote_attribution": null,
    "account_manager": { "name": null, "title": null, "email": null, "phone": null },
    "closing_note": null
  },
  "terms": [ "…verbatim from assets/terms.md…" ],
  "internal": {                                // never rendered — kept for audit
    "rate_ids": [53396],
    "warnings": ["…engine warnings…"],
    "placeholders": ["departure_9_18_minibus: flight time 14:30 is a placeholder"],
    "dropped_units": ["departure_9_18_sprinter"]
  }
}
```

## Money
All amounts are integer cents. Renderers format. Never store floats.

## Adjustments — copy and validate, never rebuild

**Engine-sourced lines carry `amount_cents_fixed`, and that amount is Core's.** It is
computed per leg at the granularity Core rounds at — per hour, per vehicle — not as a
percentage of a running subtotal. Those differ: applying 30% and 10% to a subtotal instead
of to an hourly rate made a 5-vehicle Boston job come out **30 cents above** Savoya's quote.
The fuel line is pinned as the **remainder**, so standard + lines equals Core's aggregate
**by construction**.

**Document-sourced percentage lines are refused.** This is where local money math lived:
percentages compounded in list order, so `[−25%, +5%]` depended on which was entered first.
Nothing legitimate produces one now — an additional discount is a Core re-quote
(`temporary_discount.basis_points`), fuel is market-scoped and engine-applied, and a greeter
is a priced Core unit. **Flat** document lines still apply, on top of Core's total: a
fallback on-site cost in a market with no greeter rate is a real amount a CSM was told.
`flat` values are dollars on the CLI and cents in the file. Leg-scoped lines (`applies_to`)
use that leg's `line_total_cents` as the base.

**Fail closed.** If `total_cents` doesn't equal `engine_total_cents` and no document line has
been added, rendering **stops**. The previous behaviour absorbed the gap into the last
engine-sourced line, which made the document reconcile *and* made that line misstate its own
percentage. `rounded_to_engine` is gone; a fixture carrying it fails the suite.

The print renderer derives the rate card's *net* rates from the **global percent** adjustments only (no `applies_to`): `net = standard × (1 + Σdiscount%) × (1 + Σsurcharge%)`. That is presentation of a rate, not computation of a total — the total is Core's, pinned and checked.

## What the normalizer does with engine alternatives
If the raw result has several units and `--select` isn't passed, it keeps all of them and prints a loud warning listing the keys. The document must never contain two priced options for the same leg unless the user explicitly wants an options comparison — and in that case the leg gets `"alternative_of": "<key>"` and the renderer shows it as an option, excluded from the subtotal.

## Fields the normalizer adds for Core's benefit, not the renderer's

| Field | Why |
|---|---|
| `engine_total_cents` | Core's aggregate, verbatim. The fail-closed check compares against this. |
| `engine_net_line_cents` *(per leg)* | Core's net for the leg. `line_total_cents` is replaced by the **standard** presentation, so this is the only place Core's own figure survives. |
| `engine_standard_rate_cents`, `engine_rate_units`, `engine_standard_line_cents` *(per leg)* | What the discount line is computed from, at Core's granularity. |
| `is_greeter` *(per leg)* | Suppresses drive time. A greeter drives nowhere, and Core still reports a travel time on the as-directed stop. |

## Forward-looking — GREEN-371 (E1)

A leg's pricing will become an **array of sources**, each with its own service area, rate,
quoted and billable time, cancellation policy, minimum and excess drive time. Every renderer
currently assumes **one rate, cancellation policy and minimum per vehicle type per leg**, and
R51 breaks exactly that.

On the exact path Core prices one vehicle per unit, and the compact view (MCP presentation
version 2) carries that vehicle's rate, cancellation policy and minimum on the unit.
A leg served from several markets is several units, one per vehicle type and source market.
Design for several units per leg rather than several candidates per unit, and
**do not add new logic that deepens the single-rate assumption** while touching
`normalize_quote.py`, `render_print.py` or `verify_document.py`.

