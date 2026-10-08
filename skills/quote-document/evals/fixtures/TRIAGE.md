# Fixture triage — Phase 1 of the 0.23 test plan

Taken 8 Oct 2026, before any fixture is touched. Records what each fixture currently
proves, so that coverage gets **replaced** rather than lost. Phase 2 (re-capture) needs the
Savoya connector, which was unavailable when this was written.

## The problem, stated precisely

The register said "seven of ten fixtures encode the removed path." The measured figure is
**eight of ten**, and the framing was wrong in a way that matters:

> `estimate_type` across the suite: **100 × `"approximate"`** against **8 × `"exact"`**.

**These fixtures do not fail. They pass — all ten, with PDF.** That is the actual problem.
The tool that produced approximate quotes was removed from the connector (see the Removed
table in `mcp-contract.md`), so no live response can carry `estimate_type: "approximate"`
any more. The suite is green while asserting the behaviour
of a shape the server can no longer produce. A red suite announces itself; this one looks
like safety.

Two fixtures are clean: `boston-exact-path` (7 × exact) and `six-leg-heavy-notes`.

## Per fixture

| Fixture | Source of truth | `approximate` | `exact` | Tag | What it proves that must survive |
|---|---|---|---|---|---|
| `boston-exact-path` | `raw_quote.json` | 0 | 7 | **still-valid shape** | The exact path end to end. The one fixture whose shape a live call could still return. |
| `six-leg-heavy-notes` | `quote.json` | 0 | 1 | **still-valid shape** | Rendering under heavy per-leg notes. Normalized input, so the contract change doesn't reach it. |
| `access-tca-wedding` | `quote.json` | 1 | 0 | needs-new-capture (low) | Cover + personalization rendering. Post-normalize, so only the `estimate_type` string is stale. |
| `nine-leg-pagination` | `quote.json` | 1 | 0 | needs-new-capture (low) | Page breaks at nine legs. Same: rendering only. |
| `sixteen-leg-route-map` | `quote.json` | 1 | 0 | needs-new-capture (low) | Route map at sixteen legs, and the blank-map guard's source quote. Rendering only. |
| `whistler-iol-invitational` | `raw_quote.json` | 5 | 0 | **removed-path** | Multi-day international, no `vehicle_options`. Needs a real capture. |
| `boston-offsite` | `raw_quote.json` | 23 | 0 | **removed-path** | The core multi-unit quote. Carries a `presentation` block and `requested_stop_count` already. |
| `boston-offsite-options` | `raw_quote.json` | 23 | 0 | **removed-path** | Comparison options. Must be re-captured against the new `options[2..5]` structure. |
| `boston-offsite-handoff` | `handoff/` | 23 | 0 | **removed-path** | The intake→document seam. Will need re-capturing with handoff contract v3 (F2). |
| `three-city-suv-special-event` | `raw_quote.json` | 23 | 0 | **removed-path** | Special-event pricing and the 8-hour minimum. Needs a real capture. |

### Correction, 8 Oct — these are not real client itineraries

This file originally described the five re-capture fixtures as real client itineraries.
**That was wrong.** `boston-offsite`, `boston-offsite-options`, `boston-offsite-handoff`,
`whistler-iol-invitational` and `three-city-suv-special-event` all carry
`normalize.client: "Yerdle"` — profile 201890, the internal test account. The venues in
them are real public places; the *pricing* was never a real client's.

The only real client name anywhere in the suite is **"Access TCA"**, in
`access-tca-wedding` — and that one is post-normalize, so it needs no capture at all.

So there was no re-capture trade-off to make: these fixtures were already on the test
profile, and re-capturing them is a straight **shape refresh**, not a pricing change.
Re-capturing `boston-offsite` on 8 Oct returned `aggregate_total: 935520` — byte-identical
to its existing `engine_subtotal_cents`, because the Boston Mini Bus rate ($311.84/hr
effective, 6-hour minimum) has not moved. What was stale was the response *shape*:
`estimate_type: "approximate"`, no `presentation` block, no `requested_stop_count`, no
`capacity_adjusted`.

**Five need a live capture** (the four `raw_quote.json` ones plus the handoff). **Three are
rendering-only** and can have their stale `estimate_type` string corrected without a new
capture, because nothing downstream of `normalize_quote.py` reads it. **Two are clean.**

That is a smaller job than "rebuild all ten from scratch", and it is the honest version:
the three post-normalize fixtures test the renderer, and the renderer is not what the
contract change touched.

## Baseline, frozen

Run on 8 Oct 2026 at commit `514437a` + B8, before any fixture changes:

```
✓ instruction paths
✓ tool contract
✓ warning surfacing
✓ presentation render
✓ route guards
✓ access-tca-wedding          ✓ boston-exact-path
✓ boston-offsite              ✓ boston-offsite-handoff
✓ boston-offsite-options      ✓ nine-leg-pagination
✓ six-leg-heavy-notes         ✓ sixteen-leg-route-map
✓ three-city-suv-special-event ✓ whistler-iol-invitational

10/10 fixtures passed (with PDF)
```

Any fixture that goes red during Phase 2 should be checked against this list before being
"fixed" — a fixture turning red because it was rebuilt correctly is the point, not a
regression.

## New in this release

| Fixture | Source | Why it's here |
|---|---|---|
| `quote-intake/evals/fixtures/greeter-as-directed` | real `calculate_quote_units` response, 7 Oct | A complete `presentation` block (`quote_result`), the suppressed no-passenger warning, billable hours that differ from hours requested (4 → 5.25), and `limited_availability` on a greeter type. `render_presentation.py` is tested against it. |

## Phase 2 — blocked

Needs the connector, plus a test profile with known rates across the markets involved,
**including one market with greeter rates and one without**, which D1's four-way rule
cannot be tested without. Ayush is providing the profile; 201890 (Yerdle / Orange County)
covers the greeter-present half.

Scenario matrix to capture against: §8 of `docs/0.23-change-register.md`.

---

## Phase 2 outcome, 8 Oct 2026 — all five re-captured

Every fixture re-priced under profile 201890 against the live MCP. `regress.py --pdf`
green 10/10 with six guards.

| Fixture | Re-captured as | Subtotal → total |
|---|---|---|
| `boston-offsite` | 2 units, Mini Bus, out-and-back + BOS departure | $12,150.00 → **$9,355.20** |
| `boston-offsite-options` | `options[2]`, Mini Bus vs Sprinters, document built for the chosen option | $12,150.00 → **$9,355.20** |
| `boston-offsite-handoff` | regenerated with `handoff.py write`, contract **2** | $12,150.00 → **$9,355.20** |
| `whistler-iol-invitational` | 2 units, Coach Bus on a **temporary rate**, Vancouver positioning | $15,300.00 → **$11,781.00** |
| `three-city-suv-special-event` | 3 units, SUV hourly, Orlando / LA / NYC | $3,993.00 → **$3,074.61** |

### What the re-capture bought

**Standard → discount → net now renders.** The old approximate responses exposed neither
the discount nor the fuel percentage, so the rate card could not show the breakdown —
`feedback-archive.md` recorded that as an engine gap. The new responses carry
`discount_basis_points` and `fuel_surcharge_basis_points`, and `normalize_quote.py` lands
on Core's aggregate exactly: $12,150.00 standard, −$3,645.00 discount, +$850.20 fuel =
$9,355.20.

**Core sizes the fleet.** 120 passengers → 3 Mini Buses, 80 → 2, 60 → 2 Coach Buses, all
`capacity_adjusted: true`. The old fixtures had our multiplication baked in.

**Minimums and cancellation windows are market-scoped.** Boston Mini Bus is a 6-hour
minimum and 48-hour cancellation; Orange County's is 5 and 72. A 7-minute run to Logan
bills 6 hours. No local reconstruction would produce those.

### Two bugs the re-capture found, both fixed and guarded

1. **Airport stops stopped being recognised.** The connector moved airport identification
   from a top-level `airport` object to `location.type == "airport"`. `normalize_stop` read
   only the old shape, so every airport stop normalized as an address *and the flight
   object was dropped with it* — the "flight time to be confirmed" disclosure silently
   stopped appearing on client documents. Invisible before, because every fixture carried
   the old shape. Guard: `airport shape`, three cases.
2. **The positioned-from disclosure stopped firing.** The "No local providers" warning now
   appears only on `resolve_itinerary_stops`; the quote response signals it as
   `excess_drive_time: true`. A Whistler job priced out of Vancouver billed 12 hours
   against a requested 8 and told the client nothing. Now triggered by either signal.
   Guard: `positioned-from`, three cases. The market *name* still needs carrying through
   the handoff (F2) — the fallback wording is generic.

### Coverage genuinely lost

- **Special-event pricing.** `three-city-suv-special-event` tested NYC under a US Open
  special event with an 8-hour minimum. No `special_event` object came back for
  2027-09-05, so that path has no fixture. The slug is now a misnomer; it is a multi-city
  hourly fixture. Reproducing it needs a date with a known event.
- **A comparison where neither option has a stored rate.** `generate_quote_options` accepts
  no temporary pricing fields, so two motorcoach scenarios in a market without bus rates
  cannot be compared in one call. Whistler is captured as a single temporary-rate package
  instead.
- **Alternatives inside one response.** Replaced by `options[]`. The harness now passes
  `--option`; `option_b_total_cents` and `alternative` no longer apply to these fixtures.

