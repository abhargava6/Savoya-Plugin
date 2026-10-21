# Evals & fixtures

- `evals.json` — the behavior evals for the skill-creator loop (prompts + assertions). Keep this to ~8–12 cases, one per *shape* of quote.
- `fixtures/<slug>/` — regression fixtures. Every real session can become one (`scripts/capture_session.py`); only promote the ones that add a new shape or caught a real bug.

Each fixture: `request.md` (what the client asked), `raw_quote.json` (engine output) *or* `quote.json` (already normalized), `expected.json` (assertions), optional `outputs/`.

Run `python3 scripts/regress.py --pdf` before every repackage. Zero failures or it doesn't ship.

## Shapes currently covered
| Fixture | Shape |
|---|---|
| boston-offsite | multi-vehicle quantity, out-and-back hourly block, alternatives to drop, TBD airport flight, leg-scoped flat adjustment |
| three-city-suv-special-event | multi-market, special-event override on one leg |
| access-tca-wedding | group discount + compounding fuel surcharge, wave-based charter, line notes, CSM benchmark numbers |
| whistler-iol-invitational | engine-applied discount surfaced as a line, Option A/B scenarios, out-of-market sourcing note, custom rate with no minimum |
| nine-leg-pagination | synthetic >7 lines → multi-page quote, summary on its own page, null-date fallback |
| boston-offsite-options | vehicle-swap Option B (Sprinters vs Mini Bus) with fuel surcharge; program-total math |

## Shapes still wanted
discount re-quote through the engine · transfer-rate leg (not hourly) · client logo + cover image · multi-origin per-date units (World Cup shape) · multi-day full-day usage with airport transfers and hourly overage (Bangkok shape) · multi-city international with one special-event date (Europe shape) · XLSX output
