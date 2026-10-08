# Feedback archive

Dated history of every rule in `RULES.md` — what was observed, in which session, and why the rule exists. **Read during the weekly pass only, never at runtime.** New entries go here; if an entry creates or changes a constraint, update `RULES.md` too.

---

## 2026-09-14 (Initial build — from the Yerdle / Boston / 3-city sessions)

- **Engine `aggregate_total` includes alternative units.** Always `--select` the chosen units before rendering. A Boston quote with Mini Bus and Sprinter alternatives for the same leg summed to $12,481 when the real total was $9,355.
- **Airport stops arrive unlabeled.** The engine returns an airport id; the presentation layer prints "Stop 2". Replace with the airport display name from `resolve_itinerary_stops` before rendering.
- **Special events can be invisible in the rate preview and present in the quote.** NYC on 3/20 previewed clean and then quoted against a "US Open" special-event rate with an 8-hour minimum. Trust the quote result and tell the user.
- **Out-and-back with wait time is one hourly block, not two transfers.** Two transfers double the minimum. Model it as pickup → venue (with `duration`) → return.
- **Placeholders must be disclosed twice.** In the document ("to be confirmed") and in the chat to the user (which value, and that it was a guess).
- **Fuel surcharge is a question, not a default.** Ask once; never add silently, never omit silently.
- **Discounts go through the engine, not through arithmetic.** Re-quote with `custom_discount_basis_points`; the engine's audit fields are the point.
- **No inline SVGs, no local image paths, no Drive links in HTML.** Inherited from release-notes; Front and Outlook strip them.
- **Font stacks with inner quotes break inline styles.** `'DM Sans', Arial` inside `style='…'` truncates the attribute and every following style on that element silently drops. Use unquoted family names (`DM Sans, Arial`) in all inline CSS. Caught on the first Boston render — intro note, totals, and contact card lost their colors.

## 2026-09-14 (Print/PDF format — benchmarked against the Access TCA wedding quote)

- **Fuel surcharge compounds after discounts.** Savoya bills discount first, then 5% fuel on the discounted amount. Adjustments are sequential on the running total; add the discount line before the surcharge line.
- **The white logo PNG disappears on white paper.** Every light-theme page needs a dark header bar behind the logo until a dark-on-light logo asset is hosted.
- **Terms have seven bullets, not six.** "We have a 2-hour cancellation policy unless otherwise noted above." was in the CSM reference and is now in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/terms.md`.
- **Line refs are load-bearing.** Clients and CSMs talk in A1/A2/A3. Refs go on the line table, the line notes, the leg-scoped adjustment labels, and the email summary.
- **Rate card shows standard over net.** Net = standard × (1 − discount) × (1 + surcharge), computed from global percent adjustments only. Leg-scoped flat items never touch the rate card.
- **Hero total top-right, breakdown bottom-right.** The client reads the number first and the math second; the reference doc had it backwards.

## 2026-09-15 (Audience cover pages)

- **Cover choice is a question with a recommendation, not a default.** Seven marketing covers ship in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/covers/`; infer the buyer type from the request and propose one. `general` is the fallback, not the answer.
- **Covers are 2:3, the quote is Letter.** Fit to height on a black page; never scale-to-fill (it crops the logo and footer). The generated `custom` cover is the only Letter-native one.

## 2026-09-15 (Drive capture, verified end to end)

- **Captures upload as JSON text through the Drive connector, and Claude echoes the file contents in the tool call.** Keep captures small: the raw engine JSON is slimmed to the chosen option per unit and the presentation block is dropped (~14 KB compact vs 25 KB). Never put the PDF in a capture — it's re-renderable.
- **The Drive folder ID lives in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/capture.json`, not per-user config.** Every CSM install uploads to the same place; only the CSM's name is per-machine.

## 2026-09-16 (First weekly pass — Whistler + World Cup sessions)

- **Options are Option B, never a line note.** Both real sessions needed a second scenario; both improvised. `--alternative alt:primary` now renders an Option B page with a program total (swapped + unchanged lines). Source: Whistler capture, World Cup capture.
- **Engine discounts surface as a line automatically.** Standard rate on the line, "Preferred client discount (N%)" in the breakdown, `source: engine`, survives `--clear`. Do not hand-rewrite legs to show standard rates. Source: Whistler — Claude did exactly that by hand.
- **"No local providers" reaches the client as a line note.** Out-of-market positioning changes what they pay for. Normalizer adds it; don't strip it. Source: Whistler (Vancouver), World Cup (NJ).
- **Build units per date when the client thinks per date.** World Cup units were per-origin × 4 games and had to be regrouped by hand. Source: World Cup capture `internal.restructure`.
- **Verify the Drive upload returned an id; pass --version in claude.ai.** World Cup v1 never landed. Source: Drive folder listing.
- **Keep Claude's self-reported workarounds in `--change`.** They were the only feedback in both captures and pointed straight at the fixes above.

## 2026-09-16 (Manual feedback from Ayush after first week of use)

- **The fuel terms bullet is conditional.** It shows only when a fuel line is live on the quote. `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/terms.md` marks it `[if:fuel_surcharge]`; `apply_adjustments.py` rebuilds terms on every recompute.
- **Engine-applied fuel surcharge can be waived, not removed.** `--waive` keeps the audit line, zeros it, drops the bullet, and records that the booking needs the waiver in Savoya. `--remove` on an engine line refuses with that hint.
- **The feedback line was being dropped.** It's now a mandatory verbatim last sentence on the first deliverable. Evals assert on it.
- **Discount, fuel, and cover are asked right after the rate sheet** — one question, three parts — because that's where pricing decisions happen.
- **Personalization is asked, always, once**, with defaults pre-filled so "yes" is a full answer.
- **Route map is opt-in via the personalization question**, built from free services (Nominatim, OSRM, OSM tiles), best-effort, never blocks a quote.
- **Email voice guide added; samples folder empty.** Until Robyn's emails are in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/samples/`, the draft will sound competent but generic.

## 2026-09-16 (Email voice — from 15 real Robyn/Julia emails)

- **The house quote email carries the quote inline**, per leg: Vehicle type (max capacity) · Cancellation policy* · Minimum hours · Quoted time · Adjusted Client Hourly Rate · Estimated Total, then the asterisked cancellation note, then inclusions. The PDF is the polished companion, not the only version.
- **Block figures are post-discount.** "Adjusted Client Hourly Rate" and "Estimated Total" show what the client pays; the discount is named in the opener ("which includes a 20% discount").
- **Exclamation marks are house style** (2–5, warm sentences only). The earlier guide banned them; the samples overruled it.
- **Two registers:** Sales (Robyn — "Warm Regards", standing-by closer) and CSM (Julia — "All the best", "As always, let us know if you have any questions! We are happy to help."). Chosen by the account manager's role.
- **The Stryker/Irvine RFP thread is the origin story.** The manual reply mislabeled a Coach Bus line as "2 Sprinter Van Estimated Total" — the kind of error a rendered document prevents.

## 2026-09-16 (Cover rendering in macOS Preview)

- **Never merge PDF content streams for the cover.** The marketing covers use transparency groups and patterns; pypdf-stitched pages render correctly in Poppler and the in-chat viewer but come apart in macOS Preview (Quartz). The cover is now rasterized (170 dpi JPEG) and placed in the HTML so Chromium emits one single-origin PDF. Verified with a Skia-only producer and a single XObject on page 1.

## 2026-09-17 (Slow quotes, chat compaction)

- **The PDF must never enter a tool call.** A session tried to attach the PDF to a Gmail draft as base64, truncated, retried, and blew the context — the quote took "way too long" and the chat needed compaction. Email drafts are text-only; the PDF is delivered with `present_files`. A "Context budget" section now sits at the top of SKILL.md.
- **Don't read rendered artifacts back.** HTML, PDF, map PNG, capture JSON (except the one read to upload it). Scripts print what's needed.

## 2026-09-17 (Email is copy-paste, not a connector action)

- **Email deliverable = text in the chat + PDF via present_files.** No Gmail/Outlook drafts, no attachments, no sending. Per Ayush: the user pastes the copy and drags the PDF. Mail connectors are out of scope for this skill.

## 2026-09-17 (Speed)

- **Cover rasterization was ~20s per quote, cold every session.** Covers are now pre-rendered JPEGs made by `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/make_covers.py` at packaging time; the renderer embeds them. Render is ~1.3s. Source PDFs live in the plugin's `covers-src/`, outside the skill.
- **One question, with defaults.** Discount, fuel, cover, and personalization are all settled in a single message after the rate sheet; "go" is a complete answer. No second ask.
- **SKILL.md trimmed** — the hard-won-rules list now lives only here.

## 2026-09-17 (Split: quote-intake + quote-document, v0.8.0)

- **Intake and document are separate skills.** Intake: resolve (parallel), one quoting question, `plan_approximate` only (the `calculate_*`/`generate_*` tools require a passenger id, so they're out while quoting is by headcount), value+elevated summary from a script, refine loop, handoff. Document: reads `handoff/intake.json`, asks six questions in fixed order, one at a time, and persists each answer.
- **The handoff path is regression-tested** (`boston-offsite-handoff`): `--from-handoff` must equal the manual `--select/--alternative` path to the cent.
- **Quote-only sessions are captured too** (`handoff.py capture`, deliverable `quote-only`).
- **Static vehicle table replaces `resolve_vehicle_types`** except for names it lacks.

## 2026-09-17 (Live end-to-end validation before install, v0.8.1)

- **Live run of intake → document on a fresh request (Sprinter as directed, Dallas) passed end to end** from the packaged scripts: summary, handoff, six decisions, `--from-handoff`, PDF, email copy, both captures.
- **As-directed resolver rules:** state abbreviations return nothing — use the full state name; pick the as-directed candidate whose id matches the pickup's city id. Same-place duplicates share an `id` and address.
- **As-directed stops are now labeled** ("As directed — Dallas") and rendered as "As directed — 3 hours", not "Wait on site".
- **Capacity warnings in the summary are scoped to the chosen vehicle**, not every class the engine priced.

## 2026-09-17 (Feedback from Cowork sessions — v0.8.2)

- **One question per message, both skills.** Intake: ambiguities → rate sheet? → best/options/define, each its own message. Document: `decide.py --next` prints the next question; Claude asks exactly that and nothing else. Consistency comes from the script deciding, not Claude.
- **Discounts are document-level lines now.** No re-quote through the engine from the document flow; the quote is final when it arrives. Engine-applied discounts still surface automatically. (Supersedes the 09-14 rule.)
- **One capture, one upload, per conversation** — at the end of the document flow, or in intake only when the user explicitly declines a document. Drive tool loaded once. PDF + email rendered before a single reply.
- **Quote pages paginate.** ~4 legs on the first page, ~7 per continuation; notes + breakdown move to their own page when the last page is crowded. A 6-leg Europe quote overflowed a fixed page.
- **A leg can never lose its date.** Renderer falls back to "Date to be confirmed"; the handoff writer refuses units without `pickup_date`.

## 2026-09-18 (Session review — options added together; discount/fuel invisible in quote)

- **Alternatives are inferred.** Same date + stops + headcount, different vehicle → options, not additive. `handoff.py summarize` and `write` detect it without `--alternative`; the engine aggregate is ignored and said so. Never relay the widget total after a refine.
- **Engine gap (raised with engineering):** the profile discount is baked into rack rates and the quote result exposes neither the discount % nor the fuel surcharge %; the rate sheet shows both. Until `plan_approximate` returns them in `pricing_summary.adjustments`, the document can't show standard → discount → net for profile discounts, and there is no fuel line to waive.
- **Open question for engineering:** are quote effective rates inclusive of the fuel surcharge? Decides whether "add 5%" double-charges and whether a waiver reduces the total.

## 2026-09-19 (Exact pricing path — v0.9.0)

- **Quoting moved off `plan_approximate_quote_units`.** It uses a separate service whose discount differs from the web app: same Boston job priced $9,355.20 approximate vs **$7,945.00** exact ($311.84/hr vs $283.50/hr on the same Mini Bus — 23% vs the contracted 30%). Exact is now the default; approximate is a fallback for no-passenger profiles, rate-less markets, and user-supplied temporary rates only.
- **`generate_quote_options` with candidate `vehicle_type_ids` replaces the rate sheet.** Core sizes the fleet from headcount, prices every candidate, picks the lowest per unit, and reports unquoteable vehicles with reasons. The rate sheet is genuinely optional again.
- **Core mixes vehicles across legs correctly** — Mini Bus for a long offsite, Sprinters for a short airport run whose 6-hr bus minimum costs more. Don't override it.
- **Never `calculate_quote_options`**: it prices one vehicle and ignores headcount (80 pax came back `quantity: 1`).
- **Passenger is required but price-neutral.** Two different passenger ids returned byte-identical quotes; the name never appears in the response or widget. Take the first, cache per profile, don't ask.
- **The exact path exposes what we were inferring**: `base_rate_amount` / `effective_rate_amount` and `discount_basis_points` / `fuel_surcharge_basis_points` / `special_handling_basis_points`. Document lines are built from these, and the standard-rate subtotal minus the contracted discount reconciles to the engine's `aggregate_total` to the cent.
- **Drive times come from the engine** (`travel_times`, `estimated_drive_minutes`) — no OSRM needed for times, only for the map image.
- **Detail card needs a second call.** `scenario_comparison` renders condensed; `calculate_quote_units` on the selected option renders the full card with identical numbers. Ask the engineer to enrich the comparison view — the payload already carries every field.

## 2026-09-19 (Guided questions, self-check, fix-then-log — v0.10.0)

- **Every enumerable question uses `ask_user_input_v0`.** Questions typed as prose left users guessing at the vocabulary and made the flow feel inconsistent between sessions. Option labels for all of them live in `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md`. The tool ends the turn, which enforces one-question-at-a-time for free. The cover question is the only one over four options — recommendation + two alternates + "Show all / upload".
- **`verify_document.py` runs after every render, before the reply.** It reconciles totals against `quote.json`, confirms every leg's ref and line total survived pagination, requires the terms block, keeps the fuel bullet and fuel line in sync, flags undisclosed TBD flights, and refuses internal vocabulary. A FAIL is fixed and re-verified — never delivered, never handed to the user as their problem. It is also wired into `regress.py`, so every fixture is checked on every run.
- **Feedback is now ask → fix → log.** "Anything you'd like changed?" A named change is fixed, re-rendered, re-verified and re-delivered *first*; the capture then records `--change` and `--fixed`. The weekly pass can now separate session-fixable gaps from ones needing a plugin change.

## 2026-09-19 (Session cse_01Dj2Esn — Yerdle Irvine shuttle — v0.11.0)

All three entries from that session's `feedback.jsonl`, addressed:

- **Blocking vs non-blocking clarifications.** *(reported: intake silently defaulted a missing year to a placeholder, and the document surfaced "please confirm the date" to the client.)* Anything that changes the quote — missing year or ambiguous date, headcount given as a range, an unresolvable location, an unsettled service shape — is now a **blocking question asked of the internal user before quoting**, batched with stop ambiguities. This reverses the earlier "year missing → next occurrence, recorded as a placeholder" rule, which was wrong. A missing **flight time** remains the one legitimate placeholder: it doesn't change the price and "flight details to be confirmed" is normal client-facing language. New reference: `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/client-questions.md`.
- **The client's own questions don't block.** Tax, gratuity and cancellation are already answered by the terms block; operational asks (on-site staff, greeter, signage, PA, luggage vehicle) become a client-facing line note that says arranged separately and not included in vehicle pricing. Carried across the handoff with `--client-question`.
- **Never put an internal question in a client document.** If an unresolved internal gap reaches the document stage, stop and ask the user — don't write it into the PDF.
- **Detail card is an explicit dialog.** *(reported: Claude inferred it from earlier phrasing.)* After scenarios: `Detailed quote for A` · `Detailed quote for B` · `Both` · `Let me define my own mix`. Never inferred.
- **Hand-off is always asked.** *(reported: the session jumped straight into building the document, which made the flow feel slow and presumptuous.)* The PDF/email/just-the-quote question is mandatory and never assumed from context.
- **`capture_session.py --fixed` AttributeError** — the session hit this and patched it locally; it shipped in 0.10.0 and is present in source.

What worked, per the same log: whole-program Value vs Elevated comparison with Option A/B totals — a client choosing between two fleets. Keep it.

## 2026-09-19 (from the Yerdle Irvine capture — wait vs release)

- **An out-and-back is one hourly block only if the vehicle waits.** The session correctly split two Irvine transfers ~6.5 hours apart into two transfer units rather than one hourly block, reasoning "not a wait-and-return". My rule said out-and-back → one hourly unit, full stop, which is right for Boston's 2.25-hour dinner gap and wrong here. Now: gap ≲ 3h → one hourly unit (vehicle waits); gap ≳ 3h → two transfer units (vehicle released); price both ways when it's close.
- **Confirmed working in the same capture:** the missing client name was treated as a blocking ask; the on-site-staff request was correctly flagged as an ops ask outside pricing; the 5% fuel surcharge applied as a document line to both options ($630 → $661.50 and $3,654 → $3,836.70); and the fix-then-log loop ran exactly as designed — the client-facing date note was removed, re-rendered, re-verified, and logged with both `--change` and `--fixed`.

## 2026-09-19 (Dependency preflight — v0.12.0)

Tested on a simulated bare machine (no Playwright, Pillow, pypdf, or poppler). Two real failures found and fixed:

- **`render_print.py` died with a developer message** even though the HTML had already been written to disk. Now it exits **3**, names the HTML file, and tells the user to Print → Save as PDF. A missing dependency costs the PDF, not the deliverable.
- **`verify_document.py` reported PASS having run 5 of 14 checks.** Silently reduced safety is worse than no check. It now exits **2 PARTIAL**, lists which check groups were skipped, and the skill must say the document wasn't fully verified.
- **`preflight.py`** runs once per conversation: reports what this machine can produce, in plain language, with the exact install commands. Never fails hard.
- Everything on the stdlib-only path — quote, summary, normalize, adjust, email copy, HTML — works untouched on a bare machine. The only hard dependency is a PDF engine, and it now degrades instead of failing.
- **Install instructions are device-aware.** `preflight_helpers.py` detects macOS / Windows / Linux and renders the right package manager (brew · choco/scoop · apt/dnf), the right python/pip command, the right shell name, and the right Print-to-PDF path for that OS (macOS: File → Print → PDF dropdown; Windows: Ctrl+P → Microsoft Print to PDF). Both `preflight.py` and the `render_print.py` exit-3 message use it, so the guidance is correct at the moment the user actually needs it.
- **CSMs are never shown install commands.** They're salespeople; a Terminal command they can't run reads as a broken tool. `preflight.py` defaults to CSM-facing language ("a one-time setup on this computer, which IT can do in a couple of minutes") and only prints commands under `--admin`. `render_print.py`'s no-PDF message tells Claude explicitly not to paste commands. Setup lives in `SETUP.md` for whoever preps the machine. The only technical instruction a CSM ever gets is Print → Save as PDF, worded for their OS — and since our PDF *is* a browser-rendered page, the result is identical.

## 2026-09-20 (Six fixes from the overnight test sessions — v0.14.0)

Reviewed 20 files across four sessions in the capture folder. Two sessions were clean; the two large ones broke in different ways.

- **`--fixed` really was missing.** The session reported an AttributeError on `capture_session.py --fixed` and patched it locally. I said it shipped in 0.10.0 — it hadn't; the edit targeted a line that didn't exist and silently did nothing. Now present, along with `--skipped`, and guarded: a small AST check asserts every `a.<attr>` the script reads is declared in the parser. **Lesson: an edit that "succeeds" isn't a change — verify the behaviour, not the exit code.**
- **Capture size forced a 12-part upload.** An 82 KB capture was chunked into 12 `.txt` files plus a reconstruction README, because uploads echo the whole file as a tool parameter. Now a small `.feedback.json` (~2 KB: request, decisions, totals, placeholders, feedback) is always written and always uploaded; the full capture uploads only under 25 KB and otherwise stays local with its path recorded. The script prints an explicit `upload` list, and the skill is told never to split a capture across uploads.
- **One session produced four 32 KB captures** (v1–v4) because each revision re-captured and the script auto-versioned. Capture now overwrites the same slug and fires only after the feedback exchange concludes; `--new-version` is opt-in.
- **`route_map.py` geocoded bare street addresses without a city.** `leg.service_area` was null on the exact path, so "16 Ferris Avenue" matched Melbourne, Australia. Now: never re-geocode a stop that already has lat/lon, always qualify with the leg's service area or `meta.service_area`, and skip with a warning rather than guess when neither exists.
- **`route_page()` didn't paginate** — 16 rows plus the map on one fixed-height page with `overflow: hidden`, clipping rows under the footer. Now paginates like the quote table (6 rows with the map, 16 per continuation). `verify_document.py` gained a check that every leg's ref appears in the route table, and `sixteen-leg-route-map` is a fixture so it can't return.
- **Third category of client question: data-answered.** A client asked "Can you suggest pick-up times?"; the document computed drive-adjusted times into each line's timestamp and never answered the question. `client_questions` handled boilerplate (tax, gratuity, cancellation) and operational asks (on-site staff), but not asks the quote data answers implicitly. These now get an explicit callout at the top of both the PDF and the email.
- **Feedback files are first-class.** `unpack_capture.py` reads `*.feedback.json` as well as `*.capture.json`, so a session whose full capture stayed local is still visible to the weekly pass, and flags entries that were fixed in session.

## 2026-09-20 (Greeter cost, flight-derived pickup, flight numbers — v0.15.0)

- **Greeter / on-site coordinator now has a price.** Previously it was only ever a note saying "arranged separately". When the client asks for one, `decide.py` inserts a `greeter_cost` question into the document flow (only then — the order is otherwise fixed); an amount becomes an "On-site coordinator" line on the quote and is named in the email. No amount keeps the old note.
- **Departure leg with a flight time but no pickup time** is a blocking question, not a guess: 2 hours before departure for domestic, 3 for international, confirmed by picker. It changes billable hours, so it changes the price.
- **Flight numbers break the engine — always send `commercial_tbd: true`.** Reproduced: `calculate_quote_units` rejects `flight.airline_code` / `flight_number` with *"flight.airline must be a resolved airline object with id. Use commercial_tbd=true if the airline id has not been resolved."* There is no airline resolver among the tools, so an id can't be obtained. (FBO ids *are* discoverable — `resolve_itinerary_stops` returns `nearby_airport.fbo.id` — but airline ids are not.) Keep the flight number as a client-facing line note and tell the user once it isn't linked to flight tracking yet.

## 2026-09-20 (Context diet — v0.16.0)

Measured against published guidance (SKILL.md body < 5k tokens / < 500 lines; startup = name + description only) and against `obra/superpowers` issue #190, where 25 preloaded skills cost 22k tokens.

**Startup cost was already right: 339 tokens for both descriptions.** Progressive disclosure works; the 15 scripts cost zero context because they're executed, not read. The problem was the per-quote load.

- **`feedback.md` had become a changelog read as a rulebook** — 5,336 tokens, larger than either SKILL.md, read before every render, and growing with each fix logged. Split into `RULES.md` (942 tokens, constraints only, read at runtime) and `feedback-archive.md` (the dated history, weekly pass only).
- **`decision-tree.md` and the intake SKILL.md described the same flow twice.** The tree is now the single source; SKILL.md gives the shape in a paragraph and the command sequence, and says to read the tree once.
- **The six document questions and the capture procedure moved to `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/questions.md` and `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/capture.md`**, loaded at their stage rather than sitting in SKILL.md's body.

Typical quote → PDF path: **16,186 → 10,136 tokens**, a 37% cut with no rule removed. Both SKILL.md bodies are now well inside guidance (1,340 and 3,022).

**Caught while cutting:** the Stage 0 machine check had been silently swallowed by an earlier edit whose replacement range spanned it. Restored. Same lesson as the `--fixed` bug — verify the result, not the exit code.

## 2026-09-20 (Four sessions on v0.16.0 — fixes in v0.17.0)

**The capture redesign worked.** Four files for four sessions (was twenty for four): three small `feedback.json` always uploaded, one `capture.json` under the 25 KB cap uploaded too, two over the cap correctly kept local. No chunking, no duplicate versions. Ask → fix → log recorded on every session with both `change` and `fixed`.

Five issues found, all fixed:

- **Page overflow returned, and my fix for it was wrong.** The Onvia Europe PDF clipped a line item and a line note. My pagination counted *legs* (4 per page), but legs are near-uniform in height while `client_notes` render in a separate block that grows without bound — six legs with three long notes each overflowed. Now pages are packed by **estimated height**, notes are costed against their own block, and the notes+breakdown block moves to its own page when it won't fit. Budgets calibrated against all nine fixtures. New fixture `six-leg-heavy-notes`.
- **`normalize_quote.py` couldn't read a `generate_quote_options` response.** It expects the single-package shape; the multi-option response nests it at `options[].result`. Sessions had to extract it by hand. Now it accepts either and takes `--option <key>` (or the handoff's `selected_option`), refusing with the available keys when ambiguous.
- **The engine's own stop coordinates were being thrown away.** `normalize_quote.py` copied `travel_times` but not `position`, so `route_map.py` re-geocoded through Nominatim — which mis-placed a Long Island pickup into New Jersey and failed entirely for Sicily, silently dropping the map from two PDFs. Coordinates now copy into `quote.json`, so the public geocoder is only ever a fallback.
- **Physical vehicle constraints had no mechanism.** The World Cup request capped vehicles at 9 × 18 ft for parking passes — which rules out Mini Bus (35 ft) and Coach Bus (45 ft), and makes a Sprinter (24 ft) marginal. `vehicle-types.md` now carries approximate dimensions, and a stated size or access limit is a **blocking question**. A coach turned away at the gate is worse than a higher price.
- **Candidate sets were being narrowed by intuition.** The Irvine session quoted 2 × Sprinter hourly at $812 for a leg one Mini Bus transfer covered for $210, and put an SUV in the mix for 80 passengers. Core can only choose from what it's sent. The rule is now explicit, and the summarizer flags any alternative more than 30% cheaper than the chosen option with "← cheaper; check the candidate set".

## 2026-09-20 (Europe + Bangkok failures, and what the London test revealed — v0.18.0)

Neither session captured — both died mid-quote, which is itself the signal.

- **`flight is required for airport stops` at `stops[0]`.** The rule was written for *departures* ("flight time but no pickup time") and said nothing about an **arrival** leg, where the airport is the *first* stop. Every airport stop now needs a `flight` object in either position, with `flight_type: "arrival"` when it's the pickup and `"departure"` when it's the drop-off, always `commercial_tbd: true`. Verified against the engine: the arrival shape validates and prices.
- **The rate-sheet question was skipped on Bangkok.** It is now explicitly asked on *every* quote — not only when the request looks ambiguous. Marking a recommended option `(Recommended)` is good; skipping the question is not.
- **A failed call turned into probing.** The session fired four calls, including a cut-down "Test NYC" Sedan unit, to isolate the error. New rule: validation errors name the exact path — fix that field, resend **once**, and if it fails again say plainly what the engine is rejecting. Plus a pre-send checklist at node G.

**Three things the London verification test surfaced, which no fixture had covered:**

- **Fuel surcharge is real and it isn't 5%.** London returns `fuel_surcharge_basis_points: 1000` — **10%**. Our terms bullet was hardcoded to 5%, which would have understated what the client is charged. The bullet and the fuel question now take the percentage from the engine. *(Closes the long-standing "need a profile with a non-zero fuel surcharge" gap.)*
- **`effective_rate_amount` already includes both the discount and the fuel surcharge**: 200.00 × 0.70 × 1.10 = 154.00 against the engine's 153.99. Reconstructing from the standard rate therefore drifts by a cent or two per vehicle. `apply_adjustments.py` now absorbs that residual into the last engine-sourced line so the document reconciles to `aggregate_total` exactly — a client quote must not be off by pennies. *(This also answers ENGINEERING A2 from observation rather than assumption.)*
- **A second misconfigured special event:** "Wimbledon 2022" fires on a **2027** date and applies a `SpecialEventTransferRate`. Same class as the US Open case already logged as D2.
- Incidentally: **SUV and Sprinter have no London rates at all** — only Sedan and Premium Sedan — so five passengers priced as 2 × Sedan. The capacity-adjustment path working correctly on an international market.

## 2026-09-20 (The PDF fallback was handing over the wrong file — v0.19.0)

A CSM used the HTML fallback and found it "looks completely different from the PDF… not really client ready." Correct — they were given `render_html.py`'s output, which is the **dark-themed email body**, not `render_print.py`'s `.print.html`, which is the PDF's own source and looks identical.

- The `.print.html` is now a **deliverable rather than an intermediate**: on screen it renders as a stack of pages on a grey backdrop with a sticky print bar explaining how to save it as a PDF (worded for macOS or Windows by an inline script); the bar is hidden in print, so the saved file is clean.
- Verified: printing it produces the same page count, page size and text as the real PDF, byte for byte on extracted text.
- The skill now calls it **"the printable document"** rather than "HTML", and is told explicitly never to substitute the email HTML for a PDF — a client would notice.
- **Printable document is now an offered format, not only a fallback.** It's the right answer when someone wants a page to open in a browser. But it is a **file**, not a hosted link — Drive dropped web hosting in 2016 and `.html` attachments are frequently quarantined by corporate mail filters, so for an external client the PDF remains the safer send. The skill says this plainly rather than implying a link exists.

## 2026-10-07 (The MCP contract changed and nothing told us — v0.22.1)

A live probe of the connector found **nine** tools where 22 September served ten.
`plan_approximate_quote_units` and `calculate_quote_options` are gone;
`calculate_temporary_quote_units` is new.

- **The plugin was calling two tools that no longer exist.** Node G fell back to
  `plan_approximate_quote_units` when a profile had no eligible passenger or a market had
  no stored rate. On the happy path 0.22.0 worked; on those two paths a CSM would have got
  an unknown-tool error. Nineteen references across eleven files, instructions *and* code.
- **Entries above this line are kept as written.** The approximate path was real and these
  notes recorded it accurately at the time — including the 23%-vs-30% discount discrepancy
  that moved quoting onto the exact path in the first place. They are history, not
  instructions, and the contract-drift guard exempts this file by name for that reason.
- **No passenger on the profile is no longer a special case.** `passenger_id` is optional;
  Core attaches an eligible passenger to the unsaved calculation and says so in a warning.
  The case prices like any other.
- **No stored rate in the market is not a dead end and never an estimate.** Core's own
  recovery wording is the flow: ask for a temporary rate or another vehicle, then
  `calculate_temporary_quote_units`. The result is never persisted and the reply says so.
- **A waiting leg can only take an hourly temporary rate.** A `transfer` rate needs exactly
  two stops; a three-stop out-and-back with `rate_type: "transfer"` returned
  `quote_units_unavailable` (Core 422). Our ≲3h rule produces that shape routinely.
- **The lesson worth keeping:** the server changed and we found out two weeks later, by
  looking. `regress.py` now fails if any instruction file names a tool outside the current
  nine — the same idea as the instruction-path lint, applied to tool names.
