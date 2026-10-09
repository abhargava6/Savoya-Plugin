# Changelog

Reconstructed from the working sessions of 22–24 September 2026. Versions before
0.19.1 predate this repository and are not recorded here.

## 0.23.7

- **`RUNBOOK.md` documents how to verify a build**, which was missing: it covered the full
  weekly pass but had no short "does this work here" entry, so the way to run the suite
  from a chat was undiscoverable. The phrase is now written down, with the warnings that
  matter — `--pdf` is the real gate, the suite runs against the *installed* copy, and a
  session must never "fix" what it finds there because the next rebuild overwrites it.
- **New guard `lint_paired_docs`.** Several files exist twice: at the repo root, where
  anyone would naturally open them, and under `assets/plugin-root/`, which is the copy
  `rebuild_plugin.py` actually ships. Editing the root one alone looks right in the repo
  and silently never reaches a CSM — which is what happened to the RUNBOOK edit above,
  caught only because the packaging path was checked by hand.
  **The first version of this guard hardcoded the two filenames from that incident, and
  `README.md` was already diverged at the time, uncovered.** A hardcoded list only ever
  covers the incident you just had. The list is now derived from what is actually
  duplicated, which immediately surfaced a fifth file nobody had noticed — `.mcp.json`,
  which carries the MCP server URL and is the one where a drift would be worst. Each pair
  declares its relationship (`same`, or `prefix` for README, whose root copy is a superset
  carrying a maintainer section a CSM should not get), and **a duplicated file with no
  declared relationship fails** rather than passing silently, so adding a third copy of
  something forces a decision instead of creating the next drift.
  **This is the third time two homes have cost something here**: the tool contract had
  two and shipped 0.22.0 calling tools that no longer existed, and the question set had
  three and kept `fuel` alive for a day. Neither was caught by anything automatic.

## 0.23.6

Ayush's call on the maps: keep the public services, make the degradation honest.

- **The document distinguishes the two pictures.** A street map is *Itinerary map*; the
  basemap-free fallback is *Itinerary overview · stops in order — not a driving route*, and
  states in bold that its connecting lines are not driving routes. They previously shared
  a heading, so a client had no way to tell a schematic from a street map.
- **The CSM is told which one went out** — they decide whether a schematic suits that
  client, and they can't see the PDF as the client will until it's sent.
- **New guard `lint_map_honesty`** — renders one fixture as both styles and fails if they
  come out identical, if the schematic omits its disclaimer, or if a street map disclaims
  itself as a schematic.

## 0.23.5

CSMs reported route maps "not drawing the actual route" and coming out "blank with just
straight lines". Both describe the same thing, and it is the fallback working as designed.

- **"Blank with straight lines" is `render_offline`.** When fewer than 60% of map tiles
  load, the map is redrawn from the coordinates the engine already resolved: stops in true
  relative position, joined in order, on a near-white grid. No basemap and no road geometry
  means straight lines. Nothing crashed — but the only disclosure is an attribution string
  appended to a sentence about wait time, so a CSM has no way to read it as intended.
- **The map needs three public community services** — `tile.openstreetmap.org`,
  `router.project-osrm.org` (the demo router, which this file's own header calls "fine for
  a few quotes a day") and `nominatim.openstreetmap.org` (rate-limited to 1 req/s).
  Corporate networks block these routinely. No setup instruction can change that.
- **Fixed: the map's fonts were Linux-only.** `/usr/share/fonts/truetype/dejavu/…` does not
  exist on macOS, where every CSM is, so `truetype` always raised and every label fell back
  to Pillow's default bitmap face at its own size, ignoring the 16pt and 13pt requested.
  The map still rendered, so nothing ever failed and nobody reported a font bug — it simply
  looked worse on every machine that was not Linux. Now resolves across macOS, Windows and
  Linux, with Pillow's default only if a machine genuinely has none of them.
- **The setup check now reports what the map can actually do here** — whether Pillow is
  present and which of the three services this network can reach, named in plain language
  ("Route maps will come out as a simple diagram of the stops in order, not a street map —
  this network blocks the mapping services").

**Open, and a product decision rather than a bug:** the engine already supplies drive
times, so these three services buy only a street basemap and a road-shaped line. Whether to
keep them, pay for a provider, or make the basemap-free overview the designed default is
recorded as unresolved.

## 0.23.4

The plugin ran with CSMs for weeks and nothing reached the Drive capture folder, with no
symptom on either side.

- **The instructions were already right** — local fallback, a plain line for a missing
  connector, retry-then-tell for a failed upload. **But all of it was downstream of the
  capture script running**, and three separate failures (the pre-0.23.3 crash, a connector
  never switched on, and an account without Editor on the folder) all produced the same
  silence. Nothing anywhere verified setup: `preflight.py` checks local Python packages and
  never touches a connector, the folder, or identity.
- **New setup check, in two halves.** `setup_check.py` reports identity, the capture
  folder, the local backlog and any failed captures in CSM language — no paths, no
  commands, always exits 0. `references/setup-check.md` has the session call the connectors
  instead of assuming them, including writing a small test entry to the shared folder,
  which is the only way to tell Editor access from view-only. The entry is left behind on
  purpose so the folder's owner can see whose setup is verified.
- **Reachable by the words a CSM would use** — "check my quoting setup", "is this saving?",
  "why isn't anything showing up?" are in the skill description, which is what routes them.
- **The Drive nudge is now every session, not once**, and names the backlog ("that's 4
  sessions now that haven't reached the team folder"). It stops when an upload succeeds.
- **`SETUP.md` gains step 5** and lists missing Editor access and skipping the check as
  their own rows in the skipped-steps table.
- **Removed `log_feedback.py`** — superseded around v0.10.0 when its fields moved onto the
  capture, orphaned ever since, and the first thing anyone found when looking for where
  feedback goes.

## 0.23.3

The capture never ran for the session that hit both 0.23.2 bugs, so those defects reached a
client PDF and came back only because the CSM pasted them into a chat days later.

- **It could not have run.** `--request` was required and pointed at `handoff/request.md`,
  which node K's own fallback path (a quote brought from elsewhere) never has — so the
  capture died with an uncaught `FileNotFoundError` there, and in argparse when called
  without the flag. The step is specified as silent, so the traceback reached nobody. The
  session most likely to be improvising was the one structurally least able to report it.
- `--request` is now optional and its absence is recorded as `request_missing`.
- **The capture cannot throw.** Any unexpected error writes a failure record, says so, and
  exits 0. A capture that crashes is a bug report that never arrives.
- The instructions now say to capture *hardest* when the session went worst, and that the
  plugin being a read-only build artifact says nothing about whether feedback can be
  recorded — the capture writes outside the plugin. That conflation appears to be what
  happened.
- **New guard `lint_capture_resilience`** — runs the script with both degraded inputs and
  fails if either exits non-zero, writes no feedback file, or survives only via the
  last-resort handler.

## 0.23.2

Two bugs reported from a live client quote; both reached the PDF, both reproduced here
against fixtures already in the repo.

- **An additional discount printed as a negative "Fuel surcharge."** `normalize_quote.py`
  read only `discount_basis_points`, so a 10% discount asked for in the document flow had
  no line of its own while still sitting inside Core's net — and C5's fuel remainder
  absorbed it, printing −$422.39 under a label that says surcharge. The total was correct
  throughout, which is why nothing failed: **C4 compares totals, and C5 makes that
  comparison pass by construction.** Core sends everything needed
  (`temporary_discount_basis_points`, `effective_discount_basis_points`, and its own
  `temporary_discount_label`); all of it is now read, and the line is pinned per leg at
  Core's granularity like the contracted one. Fuel is the remainder of *all* discounts.
- **New guard `lint_discount_attribution`** — a line stating a positive percentage may not
  carry a negative amount, and the stated discounts must sum to Core's effective basis
  points. Written about signs rather than about discounts, so it generalises.
- **Page 2 clipped and printed rows under the footer.** Measured at **246px of overflow
  with five rows underneath the footer** on a six-leg quote with a long intro note and
  hotel names carrying street addresses. The first-page budget was a flat constant that
  ignored the intro note rendered above the table, and the route line's height was counted
  in stops rather than characters. Both now measured.
- **New guard `lint_page_fit`** — structural, not geometric, so the suite still runs
  without a browser: a long intro note must cost the first quote page rows.

## 0.23.1

Three instruction files still carried the money rules Group C replaced on 7 Oct. The code
was right throughout; only the prose was wrong, and no guard read prose.

- **`decision-tree.md` node L** listed the removed `fuel` question and said an additional
  discount was *"a document-level line. Never re-quote through the engine."* It is a Core
  re-quote through `calculate_temporary_quote_units`, and that file is the one `CLAUDE.md`
  calls authoritative — a session following it would have done local arithmetic on Core's
  number. Node M now also states C2's refusal of document percentage lines and C4's
  fail-closed total.
- **`RULES.md`** carried the same reversed discount rule and still described adjustments as
  compounding in list order, discount before fuel. Both corrected; it is read before every
  render.
- **`SKILL.md` Stage 3** said "never re-quote from the document flow" directly above text
  saying an additional discount is a re-quote. Disambiguated.
- **New guard: `lint_question_set`.** `BASE_ORDER` in `decide.py` becomes the single home
  for the document question set, the way `mcp-contract.md` is for the tool list. The guard
  fails if an instruction file names a question the script doesn't ask, omits one it does,
  or tells a session not to re-quote a discount — unless the sentence explicitly recounts
  that as the old rule, which the tree does on purpose. Broken four ways before being
  trusted. It found the `RULES.md` and `SKILL.md` instances on its first run; only the
  decision-tree one was known when it was written.
- **The flow diagrams ship as PNGs** beside their Mermaid sources, so replacing the copies
  circulating with sales no longer needs anyone to install `mermaid-cli`.

## 0.23.0

The 0.23 register, start to finish: the plugin's assumptions and the server's contract had
diverged in seven places, and the fixtures could not have caught it. No new capability
here beyond greeters — correctness, and three live bugs found on the way.

- **The contract lives in one file.** New `skills/quote-intake/references/mcp-contract.md`
  holds the nine tools, their required arguments, the limits, the two removed tools, and
  the behaviours Core owns. `regress.py` parses its ```tools block rather than carrying its
  own copy — the contract previously had two homes, a reference file sessions read and a
  constant only the suite read, and two homes is how the last drift happened. The guard
  fails loudly if the file is missing or the list is empty, rather than passing vacuously,
  and it tolerates the retired tool names inside that file only.
- **A passenger is resolved only when the user names one** (B1). `passenger_id` is optional
  on every pricing tool; omitted, Core attaches an eligible passenger to the unsaved
  calculation. The per-profile passenger cache is gone from `handoff.py`, along with the
  `passenger` and `remember-passenger` subcommands. Existing cache entries in a user's
  config are left alone rather than pruned — nothing reads them now. `resolve_passengers`
  also leaves the opening tool search.
- **Core is the authority on vehicles** (B2). `resolve_vehicle_types` is now called once per
  quote, reversing a context-budget decision that stopped paying when the static table was
  found *wrong* rather than stale: Exec Van is capacity 14, not "~10", and seven types were
  missing including both greeters. `vehicle-types.md` keeps what Core has no concept of —
  physical dimensions, which are what rule a coach out of a 9×18 ft parking cap — plus our
  candidate-set policy, with capacity deliberately removed.
- **`requested_stop_count` goes on every unit** (B3), so Core can detect being handed fewer
  stops than were asked for. Dropping a stop silently is what produced 0-minute drive times
  in 0.20.0.
- **Comparisons take an `options` array of 2–5** (B4), each with a complete `quote_units`
  list. Every option must contain every trip, which Core now enforces — a duplicate option
  is rejected outright. `strategy` is documented as a presentation label: the same two
  options run twice with only the strategy strings swapped returned identical totals,
  vehicles, quantities and rate ids.
- **`calculate_quote_units` takes one vehicle, never a list** (B5), stated explicitly so it
  isn't drifted back into. Candidate lists belong only in `generate_quote_options`.
- **Flights stay TBD-only, with the seam written down** (B6). The contract describes
  known-commercial and private flights, both needing resolved ids, and neither resolver
  exists among the nine tools. Recorded as a deliberate deferral so the next person knows
  the shape was understood rather than missed.
- **Warnings: one suppression, and the rest finally surface** (B9). The intake summarizer
  used to print only the two warning shapes it recognised and drop everything else in
  silence — an allowlist hides a real warning as effectively as a filter does. It now shows
  every warning, translating what it knows and printing the rest verbatim. Exactly one is
  suppressed: Core's "No passenger was selected" note, and only on a unit that priced,
  because omitting `passenger_id` is now the normal path. A distinct warning is said once
  per quote rather than once per unit per option.
- **New guard: warning surfacing.** Five independent assertions — the suppression string is
  identical in both skills (it is duplicated across skills that cannot import from each
  other), the suppressed warning doesn't render on a priced unit, an *unrecognised* warning
  does, warnings dedupe across units, and suppression stays conditional on the unit having
  priced. Each was broken on purpose and seen to fail alone.
- **Core's `presentation` block is now the CSM-facing view** (B8). New
  `render_presentation.py` prints Core's own rows — `quote_result` and `blocked` field by
  field from captured responses, the other views from whatever structure is actually
  present rather than from field names we'd be guessing at. Three boundaries are enforced
  by the suite, not just documented: it is internal and never client copy; a response with
  no `presentation` block exits 3 so the caller falls back to `handoff.py summarize`; and a
  presentation total that disagrees with the quote units prints **both** figures and says
  so rather than silently preferring one. `presentation.actions` intents are named and
  bound to nothing — the refine loop stays ours until they're documented.
- The renderer also states **requested versus billed hours** where they differ (4 requested,
  5.25 billed), which is what stops a CSM reading Core's positioning time as a bug.
- **New guard: presentation render**, five assertions against a real captured response —
  Core's figures appear verbatim, the suppressed warning doesn't, the requested-vs-billed
  note does, an absent block falls back instead of rendering blank, and a total mismatch
  surfaces with both numbers. Each broken on purpose. One of those breaks was real: the
  renderer printed the suppressed passenger warning twice on its first run, because the
  suppression lived in `handoff.py` and this was a third code path. It now imports that
  constant.
- Also recorded from the live tests: a greeter unit is pickup + an `as_directed` stop with a
  `duration` in hours, Core adds a constant +1.25h of positioning time on top of it, and a
  `duration` on a dropoff is ignored. Billable hours are Core's — send what the user asked
  for, show what Core billed, never back-solve.
- **Phase 2 captures: seven real fixtures** under `quote-intake/evals/fixtures/`, covering
  all four `presentation` views. Two renderer guesses were wrong and were corrected against
  the captures: `rate_preview` lives under `data.groups[]` (the guess fell through to a
  generic dump), and the renderer showed the contracted 30% discount while the client was
  getting 40% because it read `discount_basis_points` and ignored
  `effective_discount_basis_points` — understating the discount on screen by a third. It
  now prints the effective figure with its breakdown, plus Core's subtotal → total line.
- **▲ A temporary rate is a BASE rate, and the client's discount comes off it.** $250.00/hr
  supplied became **$192.50/hr** effective. Documented behaviour, but it means a CSM who
  enters the partner's cost quotes the client 23% below it — a margin leak, catchable only
  where the number is asked for. The decision tree and `RULES.md` now say so.
- **C1 needs no local arithmetic.** Core returns `subtotal_amount`, `total_amount`,
  `temporary_discount_amount` and `temporary_discount_label`, and discounts are **additive
  in basis points** (30% + 10% = 4000 bps, not 37%). The old local `recompute()` compounded
  in list order and would have disagreed with Core on exactly this case.
- **Resolver rules from real behaviour.** "John Wayne Airport, Santa Ana, California"
  resolved to nothing as an airport stop while `"SNA"` resolved first time — use the IATA
  code. And the same location `id` can cover genuinely different addresses: "Anaheim
  Convention Center" returned the venue, a Residence Inn and a Hampton Inn all under
  `id: 4645260`, which is why the tree's rule is "same id **and** address".
- The presentation guard now renders all seven fixtures and asserts per-view facts, plus
  that none of them shows the suppressed passenger warning.
- **All five document fixtures re-captured** against the live MCP under profile 201890
  (Phase 2). They were never real client itineraries — all five carried
  `normalize.client: "Yerdle"`, the test account; the triage said otherwise and was wrong.
  So this was a shape refresh, not a pricing change.
- **Standard → discount → net renders for the first time.** The old approximate responses
  exposed neither the discount nor the fuel percentage, which `feedback-archive.md` recorded
  as an engine gap blocking the rate card. The new responses carry both, and
  `normalize_quote.py` lands on Core's aggregate exactly: $12,150.00 standard, −$3,645.00
  discount, +$850.20 fuel = **$9,355.20**.
- **▲ Bug fixed: airport stops had stopped being recognised.** The connector moved airport
  identification from a top-level `airport` object on the stop to
  `location.type == "airport"`. `normalize_stop` read only the old shape, so every airport
  stop normalized as a plain address **and the flight object was dropped with it** — the
  "flight time to be confirmed" disclosure silently stopped appearing on client documents.
  Invisible until now because every fixture carried the old shape. Both shapes are accepted;
  new `airport shape` guard, broken three ways.
- **▲ Bug fixed: the positioned-from disclosure had stopped firing.** The "No local
  providers" warning now appears only on `resolve_itinerary_stops`; the quote response
  signals it as `excess_drive_time: true`. A Whistler job priced out of Vancouver billed
  12 hours against a requested 8 and told the client nothing. Either signal now triggers the
  note; new `positioned-from` guard, broken three ways. The market *name* still needs
  carrying through the handoff (F2), so the fallback wording is generic.
- The harness learned the new comparison shape: `expected.json` accepts
  `normalize.option`, and `regress.py` passes `--option`. Every fixture predated
  `options[]` and used alternative units inside one response instead.
- Coverage genuinely lost, recorded rather than papered over: special-event pricing (no
  `special_event` came back for the replacement date, so that slug is now a misnomer), and
  a comparison where neither option has a stored rate — `generate_quote_options` accepts no
  temporary pricing fields, so Whistler is captured as a single temporary-rate package.
- **`ENGINEERING.md` started in the repo** with G1 (`greeter_fee` unsettable), G2
  (`client_can_book` missing from presentation rows) and G3 (`temporary_rate_used` false at
  aggregate level while the unit says true), each with the real response as evidence, plus a
  B7 stub so `CLAUDE.md`'s reference resolves. It needs reconciling with the existing copy.
- **Fixture triage** (`evals/fixtures/TRIAGE.md`). The register said seven of ten fixtures
  encoded the removed path; measured, it is eight, and the framing was wrong in a way that
  matters: `estimate_type` runs **100 × approximate against 8 × exact**, and those fixtures
  all **pass**. No live response can carry `approximate` any more, so the suite is green
  while asserting a shape the server cannot produce. Triage splits the work honestly — five
  need live captures, three are post-normalize and only carry a stale string, two are
  clean — which is a smaller job than rebuilding all ten. Phase 2 is blocked on the
  connector.

### Group D — greeters

- **D1 — a greeter is a priced Core unit** (vehicle types 12 and 13), never a number a human
  invents. New node **G3** in the decision tree. The rate check is an **attempted price**,
  because greeters do not appear in `preview_rate_batch` at all and Core does not list them
  as missing either — the rate sheet simply cannot answer the question. It isn't a wasted
  call: in three of the four rows the priced unit is what you wanted anyway.
- The unit shape is **pickup + an `as_directed` stop carrying the hours**. A `duration` on
  the dropoff is ignored and collapses to the 2-hour minimum.
- **The reply states both hour figures.** Core adds a constant +1.25 h of positioning, so
  4 hours requested bills 5.25. Never back-solve the duration.
- **A greeter leg carries no drive time.** Core still reports one — 5 minutes at Irvine,
  13 on the wrong shape — and "5 min drive" against a person meeting a flight is what a
  client notices. New `greeter leg` guard; the price survives, only the drive figure goes.

### Group F — artifacts and documentation

- **F2 — handoff contract v3**, and a stale handoff is now **refused rather than
  reinterpreted**. A v1 or v2 handoff was written when `estimate_type` could be
  `approximate`, a passenger id was always present and the sourcing market arrived on the
  quote; reading those fields as if they still meant that produces a document that looks
  right. New `handoff contract` guard pins the version across the three places it lives.
- **F3 — `quote-schema.md`** rewritten around copy-and-validate, with the fields the
  normalizer now keeps for Core's benefit and E1's forward-looking note on
  `vehicle_options[]`.
- **F1 — the flow diagrams are regenerated and in the repo** at `docs/diagrams/`, validated
  by rendering. The copies circulating with sales are from the 0.22 tree and still show the
  approximate fallback, a passenger on every quote, six questions and no greeter node.
- **F4 — `CLAUDE.md`** gains the lesson these three releases keep teaching: *a signal moving
  is as dangerous as a signal breaking.* Three live bugs had the same shape — the connector
  moved something, the plugin kept reading the old place, and nothing errored.

### Group C — money ownership moves to Core

- **C3 — the fuel question is gone.** Fuel is market-scoped and engine-applied, and nothing
  in the contract subtracts it: `temporary_discount` is additive and a surcharge is not a
  discount. The old `waive` already told the CSM the booking needed the waiver applied in
  Savoya, so it was never really ours to give. **Five questions, not six.** The
  `[if:fuel_surcharge]` terms bullet stays, because it reflects what Core applied.
- **C1 — the discount is a Core re-quote.** `questions.md` used to say, in writing, *"Do not
  re-quote through the engine."* That was right under the old contract and is wrong now.
  The question calls `calculate_temporary_quote_units` with
  `temporary_discount.basis_points` and rebuilds from the response, which returns
  `subtotal_amount`, `total_amount`, `temporary_discount_amount` and the label — the whole
  standard → discount → net line with nothing left to compute.
- **C5 — engine line amounts are pinned to Core's own granularity.** They were re-derived as
  percentages of a running subtotal; Core rounds **per hour and per vehicle**. On the
  5-vehicle Boston job the document came out **30 cents above** Savoya's quote. The discount
  is now computed per leg at Core's granularity and fuel is pinned as the remainder, so
  standard + lines == Core's aggregate **by construction**.
- **C4 — fail closed.** The old code absorbed any gap into the last engine-sourced line, so
  the document always reconciled *and that line then misstated its own percentage*. Removed.
  A mismatch now refuses to render, with a message naming both figures and the difference
  and telling the CSM to re-quote — a bare failure would just look like a bug.
- **C2 — no document percentage lines.** This is where local money math lived: percentages
  compounded against a running subtotal in list order, so a 25% discount followed by a 5%
  surcharge depended on which was entered first. Nothing legitimate calls it now. Flat lines
  still apply, on top of Core's total — a fallback on-site cost is a real amount a CSM was
  told, not a percentage of Savoya's number.
- **New guard: money ownership.** Four assertions — the total equals Core's exactly, no line
  carries `rounded_to_engine`, standard + engine lines == Core's aggregate, and a 30-cent gap
  refuses to render with a usable message. Broken three ways, including restoring the
  absorption.
- **Two fixtures changed by design.** `access-tca-wedding` used a −25% group discount and a
  5% fuel line, both document percentages; it keeps the discount as the flat amount it
  resolved to and loses the fuel line. `nine-leg-pagination` loses its fuel line. Their
  totals move accordingly — the announced visible regression, now visible.

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
