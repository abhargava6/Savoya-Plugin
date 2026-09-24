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
    "estimate_type": "approximate",            // from engine: approximate | exact
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

## Adjustment order and compounding
Adjustments apply in list order on the running total. Negative `value` = discount. So `[discount −25%, fuel +5%]` yields fuel = 5% of the discounted subtotal — matching Savoya billing ($13,842 → −$3,460.50 → +$519.08 = $10,900.58 on the reference wedding quote). Leg-scoped adjustments (`applies_to`) use that leg's `line_total_cents` as the base. `flat` values are dollars on the CLI and cents in the file.

The print renderer derives the rate card's *net* rates from the **global percent** adjustments only (no `applies_to`): `net = standard × (1 + Σdiscount%) × (1 + Σsurcharge%)`.

## What the normalizer does with engine alternatives
If the raw result has several units and `--select` isn't passed, it keeps all of them and prints a loud warning listing the keys. The document must never contain two priced options for the same leg unless the user explicitly wants an options comparison — and in that case the leg gets `"alternative_of": "<key>"` and the renderer shows it as an option, excluded from the subtotal.
