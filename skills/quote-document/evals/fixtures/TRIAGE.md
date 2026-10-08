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
