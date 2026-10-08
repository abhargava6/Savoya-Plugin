# Changelog

Reconstructed from the working sessions of 22–24 September 2026. Versions before
0.19.1 predate this repository and are not recorded here.

## 0.22.1
**The connector dropped two tools and the plugin was still calling them.** A live probe on
7 October found nine tools where 22 September served ten:
`plan_approximate_quote_units` and `calculate_quote_options` are gone and
`calculate_temporary_quote_units` is new. 0.22.0 worked on the happy path and hit an
unknown-tool error on two real paths — a profile with no eligible passenger, and a market
with no stored rate. Nineteen references across eleven files, instructions *and* code.

- **No passenger on the profile is no longer a special case.** `passenger_id` is optional;
  Core attaches an eligible passenger to the unsaved calculation and returns a warning.
  Node B omits it and quotes normally — no estimate, no fallback, no disclosure to the CSM.
- **No stored rate in the market is no longer a dead end, and never an estimate.** Core's
  own recovery wording is the flow: ask for a temporary rate or another vehicle, then
  re-quote through `calculate_temporary_quote_units`. The result is never persisted and the
  reply says so.
- **A waiting leg can only take an *hourly* temporary rate.** A `transfer` rate needs
  exactly two stops; a three-stop out-and-back with `rate_type: "transfer"` returns
  `quote_units_unavailable` (Core 422, verified). The ≲3h out-and-back rule produces that
  shape routinely, so the tree now says never to offer a transfer rate for one.
- **New guard: the tool contract.** `regress.py` fails if any instruction file or script
  names a tool outside the current nine — a pattern, not a blocklist of the two we know
  about, so it catches the next change too. The nine live in `MCP_TOOLS` in `regress.py`
  as the single place to edit when the server moves. Two files are exempt with stated
  reasons: `feedback-archive.md` (dated history — rewriting it would falsify the record)
  and `regress.py` itself (it holds the contract and issues no tool calls).
- Behaviour on every path that worked in 0.22.0 is unchanged. This release only replaces
  calls to tools that no longer exist.

## 0.22.0
- **Questions are now gated by format.** `decide.py order_for()` drops the `cover` and
  `map` questions once the format is known not to use them. Only the PDF and the
  printable document read either answer: `cover` is built solely by `render_print`, and
  `route_page()` is the only reader of `quote.route_map` anywhere. An email-only job now
  asks 4 questions instead of 7 and skips 10–20s of routing for a field nothing reads.
  Nothing changes when the format hasn't been stated yet.
- **Email copy is a real option.** The format picker offers `Email copy` on its own;
  previously every choice but Word/Excel produced a PDF, so "just the email" was off-menu.
- Stage 4 no longer attaches a PDF to an email request by default — it offers one.
- `personalization` question text adapts: for email/Excel it stops promising an intro
  note, client logo, per-leg notes and closing line, none of which the email renderer reads.
- Fixed a second hardcoded 5% fuel surcharge, in `decide.py`'s no-fuel-line fallback.

## 0.21.1
- **Line notes rendered one character per line.** `client_notes` given as a bare string
  instead of a list was iterated character by character, printing a vertical column of
  letters that overflowed the page. Both renderers now accept either shape via
  `notes_of()`, and `verify_document.py` fails a string so the quote.json gets corrected
  rather than silently patched at render time.

## 0.21.0
- **A capture is written and uploaded at delivery**, not only after the feedback
  exchange. A session where the user takes the document and leaves is now on record.
  One Drive call per delivered document; the full capture still rides with the feedback run.
- `--workaround` is its own field. `--change` is the user's words only — mixing Claude's
  own notes into it made a CSM request indistinguishable from a defect Claude patched itself.
- `asked` / `answered` / `declined` are separate and honest. `answered` previously read
  true whenever Claude had filled in a note, whether or not the user said anything.

## 0.20.1
- **Fuel surcharge verification is market-aware.** `verify_document.py` matched the
  literal string "fuel surcharge of 5%" while `apply_adjustments.py` templates the live
  figure, so every 10% market (London, Orange County) false-failed on a correct document.
  It now reads the percentage and cross-checks it against the quote's fuel line.
- **Offline route map.** When the tile service is unreachable — some corporate networks
  block it outright — the overview is drawn from the engine's own stop coordinates rather
  than skipped. Tagged `style: offline` so the blank-map check doesn't fire on it.
- Fixed a `global` declaration missing from `render_offline`, which left the offline flag
  set on a local and never reaching the metadata.

## 0.20.0
- **Drive times come from the engine.** `route_map.py` was overwriting
  `normalize_quote.py`'s engine-sourced `travel_times` with a public demo router's guess.
  Any stop that failed to geocode was dropped from the route while the remaining points
  still routed, so an out-and-back whose midpoint was lost came back as 0 min. The engine's
  minutes now win; routing supplies distance and the drawn line only.
- **A blank map is never shipped.** Tile failures were swallowed, leaving a flat
  background that still saved, still reported success and still embedded in the PDF.
  Tiles are counted; a stale map from an earlier run is cleared rather than riding along.
- Geocoding retries once with backoff; a leg that loses any stop gets no route at all.
- `verify_document.py` fails a near-uniform map, a sub-minute drive across 2+ stops, and a
  route with fewer segments than the leg has stops.
- Fixed a crash in the summary print, which assumed every route carried `distance_mi`.
- **The regression stub was the bug.** The map placeholder was a flat fill in exactly the
  colour a failed tile fetch produces, so the suite could never have caught a blank map.

## 0.19.3
- The intake question sequence is inline in `SKILL.md` — the ask order, the
  `ask_user_input_v0` rule, and "never fold two questions into one sentence" — so the flow
  survives a reference file failing to load.
- "Never guess a path": sessions were constructing `/mnt/skills/plugins/savoya-quoting:…`
  from the skill's display name and then improvising when it did not exist.

## 0.19.2
- **All 70 instruction paths anchored to `${CLAUDE_PLUGIN_ROOT}`.** Bare `scripts/x.py`
  resolves against the session's working directory, not the skill folder. Whether a
  session recovered depended on it noticing the runtime's "Base directory" header — so it
  worked in a demo and failed in front of a CSM.
- `regress.py` lints for unanchored paths and dead references.
