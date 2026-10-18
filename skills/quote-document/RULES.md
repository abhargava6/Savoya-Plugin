# Rules

Hard constraints distilled from real sessions. Read this before rendering. The dated history and the reasoning behind each rule live in `feedback-archive.md` — read that only during the weekly pass, never at runtime.

## Money
- Lines show **standard** rates; the client's contracted discount is its own line built from `discount_basis_points`. Totals must reconcile to the engine's `aggregate_total` to the cent.
- **Flat** document lines apply in list order on the running total. **Percentage** document lines are refused (C2): they compounded against a running subtotal, so a 25% discount followed by a 5% surcharge depended on which was entered first. Percentages are Core's to compute.
- Engine-sourced lines (contracted discount, fuel, special handling) survive `--clear` and can only be `--waive`d, never `--remove`d. A waiver records that the booking needs the same waiver in Savoya.
- An additional discount asked for in the document flow is **a Core re-quote**, not a document line: `calculate_temporary_quote_units` with `temporary_discount.basis_points`, then re-normalize from the response. This rule was the other way round until 0.23 and the reversal is the point — a discount applied here was our arithmetic on Core's number. Discounts are **additive** in basis points: 30% contracted + 10% here is 40%, not 37%. The result is never persisted; say so.
- **Every discount Core applied gets its own line.** The contracted discount comes from
  `discount_basis_points`; an additional one from `temporary_discount_basis_points`, under
  Core's own `temporary_discount_label` when it sends one. Both are pinned per leg at
  Core's granularity, and fuel is the remainder of *all* of them. Reading only the
  contracted field leaves the extra discount inside Core's net with no line of its own, and
  the fuel remainder then prints it as a **negative** "Fuel surcharge" — with the total
  still exact, so nothing fails.
- **Shuttles converging on one place on one day are one movement** (2026-10-10). The
  header counts the people a quote moves, and what counts as one movement decides the
  number. An exact stop sequence was too strict: the World Cup quote ran four shuttles on
  one date from four stations to MetLife and back, ten guests each, and the header read
  **10** for a date on which forty travelled. The destination alone is too loose, and the
  wedding fixture shows why — two Sprinters one-way and three Mini Buses round-trip to the
  same place on the same day sum to **132** for a 120-guest wedding. The key is therefore
  (calendar date, one-way or round trip, where it goes), with the origin dropped and the
  turnaround standing in as the destination of a round trip. `regress.py` pins all three
  rejected rules — `max()`, `sum()` and the exact sequence — as failures.
- **Option B's total is Core's amounts summed, never percentages re-applied**
  (2026-10-10). `option_total()` added each percent adjustment to a *running* total, so
  two discounts compounded: 30% then 5% gives 0.665 where Core's additive 35% gives 0.65,
  and Option B came out about **2.3% high** — on a live London/Sicily/Milan quote it
  overstated the *cheaper* option, understating the saving being offered. It is the defect
  C2 was written about, and it survived in the one total with no fail-closed check behind
  it: Option A never computes a percentage (C5 pins each engine line at Core's
  granularity, C4 refuses to render if the sum misses Core's aggregate), while Core never
  priced the Option B combination as a package, so there was nothing to check against.
  **The only total nobody could verify was the only one still doing its own arithmetic.**
  It now sums `engine_net_line_cents` over the option's legs; where those are absent the
  percentages are summed and applied once, with a warning. Document flat lines still
  apply, and a leg-scoped one only when its leg is in that option.
- **A check must be tested against what the code actually produces** (2026-10-10).
  `verify_document` rejected any sourced leg whose market matched its primary market —
  correct for a cross-market override, and false by construction for a stop in no service
  area, where Core reports one market as both. The feature and its own validator
  contradicted each other, and the real Sicily legs failed verification on a live quote.
  The guard tested `normalize_unit`, which *sets* the flag; nothing ran the verifier, which
  *reads* it. **Testing a producer says nothing about its consumers** — and the suite had
  flagged three fixtures on this very check hours earlier, which was resolved by
  correcting normalize without re-examining the verifier.
- **The email states Core's line amounts, not its own** (2026-10-10). `draft_email.py`
  built one multiplicative factor over every percent adjustment — 0.70 × 0.95 × 1.10 —
  where Core adds discounts in basis points and applies 3500 once. With a single discount
  the two agree exactly (0.77 either way), so it was invisible for months; with two it is
  not, and on a 16-leg World Cup quote **every one of the 16 lines came out high and the
  email totalled $26,145.63 against the $25,555.91 the PDF showed on the same job**. The
  CSM pasted an email contradicting its own attachment. Line totals now come from
  `engine_net_line_cents` and the per-unit figure from
  `engine_net_line_cents / (quantity × engine_rate_units)` — Core's number divided only by
  Core's own unit count. The opener names the **summed** discount, not the first one it
  finds. `regress.py` reconciles the email against the engine on a quote with two stacked
  discounts; the PDF never had the bug because `render_print` sums the percentages.
- **A waived engine line has to be added back before comparing** (2026-10-10). Core's
  aggregate still contains it — the waiver is ours, recorded so the booking carries the
  same waiver in Savoya — so the document total is legitimately short by exactly that
  amount. Nothing added it back, so C4 refused on any waiver and **`--waive` was
  unusable**: waiving the fuel surcharge produced a "$58.50 gap" that was the waiver
  itself. It is the only documented way to drop an engine line and it had **no guard on
  it at all**, which is why this sat unnoticed. A real gap is still caught with a waiver
  in play.
- **A document line moves what C4 compares; it does not switch C4 off** (2026-10-10).
  The fail-closed check ran only when no document line had been added, on the reasoning
  that the total is then deliberately no longer the engine's — true of the total, not true
  of the engine's *share* of it. So adding one flat line disabled the only fail-closed
  money check in the plugin. On a live Irvine quote a $200 on-site coordinator line did
  exactly that, and that quote was also built from a hand-transcribed engine response,
  which is when the check matters most. Reproduced: a $100 slip in one leg's line total
  shipped a client document $100 light, silently. The document lines are now subtracted
  back out and the engine share is compared — exact, because C2 refuses document
  percentages, so only flat lines can be document-sourced. The refusal says it is
  comparing the engine share, or a CSM would read their own added line as the discrepancy.
- **A reconciling total does not mean a correct breakdown.** C4 and C5 guarantee the total
  by construction, which is exactly why they cannot catch a line mislabelled as its
  opposite. A line stating a positive percentage must never carry a negative amount.

## Commission: the rate is recorded, the amount is computed in code, no total moves
- **A commission changes no total** (2026-10-10). It is the first answer in the
  question set that is purely presentational: it never enters `adjustments`, the total is
  identical with it and without it, and C4 stays meaningful. `apply_adjustments.py
  --commission-pct <pct|none>` records it — in that script because it owns the terms
  block, so the rate and its terms bullet land in one call and cannot get out of order.
- **The amount is computed by `apply_adjustments.py`, never by the session** (amended
  2026-10-16, PRD R59). The 2026-10-10 rule said never to compute one, because the basis
  was not ours to assume. A live Yerdle session needed the amount on both options, worked
  it out by hand and edited it into the terms — a figure with nothing checking it. The
  basis is now fixed: **the subtotal after every discount, before the fuel surcharge**,
  times the rate, rounded half-up to the cent, per option. It is built from Core's per-leg
  figures; with none (a hand-assembled `quote.json`) the rate is stated and no amount is
  guessed. **A session must not work out a commission amount itself or edit one into
  `quote.json`** — re-run `apply_adjustments.py` instead. The wording is *"A 5% commission
  applies to this program, calculated after discounts and before the fuel surcharge:
  $600.50 on Option A, $728.61 on Option B."* A single-option quote drops the labels.
- **It names no beneficiary.** The commission may be earned by the client or by an agency
  acting for them, and a client-facing document must not assert which.
- **Three places, all automatic once recorded**: a hero line under each option total in
  the PDF, the terms list (which is how the HTML email gets it), and one flat
  sentence in the email copy after the inclusions paragraph. **Flat in the email on
  purpose** — it moves the needle sometimes, but the client is reading a quote, not an
  offer. On *No*, nothing is recorded and the word appears nowhere.

## Email, confirmation and recovery (0.27.0, 2026-10-16)
- **A carried client request is noted, never resolved** (R73). "PA on the bus" and
  "signage in the windows" come from intake's `client_questions`; `normalize_quote.py` carries
  them and `client_requests.py` builds one flat line ("We've noted your requests (…) and will
  confirm each with you"). Never write that a request is included, excluded or arranged
  separately: the session does not know. The line is in the email copy and the HTML email,
  **not the PDF** (it pushed the Yerdle page 2 past the footer).
- **Everything uncertain is confirmed before send** (R72). `confirm_items.py` lists the grouped
  service-area placeholders, each other placeholder and each operational request; the session
  asks one Right/Wrong question per item. Gate only; a Wrong answer stops the send.
- **The email asks for flight details only when a flight is TBD** (R74), never because some
  unrelated placeholder exists.
- **The email comes in two forms** (R71): full, and a short version with leg and option totals,
  the discount, the commission amount and a PDF pointer. Both copy Core's figures.
- **Capture happens at verification, not at the user's prompt** (R63).
  `verify_document.py --capture-slug` writes the snapshot and the marker on a pass; the session
  uploads both files and runs `--mark-uploaded` before presenting anything.

## What reaches the client
- Never: rate ids, inventory counts, "hourly fallback", basis points, profile or passenger ids, estimate_type as a word.
- Always: pricing basis with minimums, per-leg cancellation, quantity × vehicle with capacity, special-event pricing, TBD flights as "to be confirmed", out-of-market positioning ("vehicles positioned from [city]; additional drive time included").
- The fuel terms bullet appears **only** when a live fuel line is on the quote, and states the **engine's** percentage — never a hardcoded 5%. London returns 10%; assuming 5% would understate what the client is charged.
- The engine's `effective_rate_amount` already folds in both the contracted discount and the fuel surcharge. Lines show the standard rate and both appear as their own lines; `apply_adjustments.py` absorbs per-vehicle rounding into the last engine line so the document reconciles to `aggregate_total` exactly.
- An internal question (missing year, unresolved headcount, ambiguous location) must **never** appear as a client-facing "please confirm". It was settled during intake; if one reaches here, stop and ask the user.
- Airport stops label themselves from `display_name`. Never ship "Stop 2".
- A leg can never lose its date — the renderer falls back to "Date to be confirmed" and the handoff writer refuses units without `pickup_date`.

- **Core's own strings are read, not published unexamined** (2026-10-10). Three defects in
  one day from printing a Core field straight through. `temporary_discount_label` arrived
  as "Temporary user-supplied discount" and printed in a client PDF — "temporary" is
  Core's word for pricing it did not persist, an internal fact about the quote, and
  `normalize_quote.client_label()` now maps anything of that shape to "Additional
  discount". The same field arrived as "Additional 5% discount", and the adjustment table
  appends the percentage to every percent line, so the PDF read "Additional 5% discount
  (5%)" — `render_print.pct_suffix()` now withholds the suffix when the label already
  carries one. **The label itself is never edited to fix this**: an attempt that stripped
  any percentage it found turned "Loyalty 12.5% off" into "Loyalty off".
- **A special-event name with the wrong year is withheld; the disclosure is not**
  (2026-10-10). Core returned `special_event.name = "Wimbledon 2022"` against July **2027**
  London dates and it printed three times on a $17.9k proposal — both line notes and the
  rate card. The disclosure has to survive, because a special-event rate carries a real
  minimum and a different cancellation window; only the name is unsafe, and only when its
  year is not the year of travel. The leg then says event pricing is in effect and names no
  event, and the mismatch goes to the internal placeholders so the stale Core record gets
  fixed. A name with no year is published unchanged.
- **Out-of-market positioning is said once, and said for the case with no market to name**
  (2026-10-10). The sourced-line marker and the `excess_drive_time` line note describe the
  same fact in two places; on the real Irvine quote every leg was both, so the client PDF
  said "positioned from our San Diego, CA partners" **twice per leg**. The note is now
  emitted only when the marker will not fire. They cover complementary halves and both are
  needed: the marker handles a named source market, the note handles positioning with no
  market to name.

## Client questions (three kinds)
- **Boilerplate** (tax, gratuity, cancellation) — the terms block already answers it.
- **Operational** (greeter, on-site staff, signage, PA, luggage vehicle) — the document flow asks the user for a cost; an amount becomes a line. With no amount the request stays a carried client request: one neutral "noted, will confirm" line, built in code, never an inclusion or exclusion claim (R73).
- **Data-answered** (pickup times, drive times, vehicle counts, how long the vehicle is held) — the quote holds the answer implicitly. Surface it as an explicit callout at the top of the PDF **and** the email. Never make a client decode sixteen timestamps.

## Two copies of this plugin is a silent fork
- **A path lookup by name finds the OLDEST copy** (2026-10-10). The account had two
  uploads both named `savoya-quoting` — 0.19.1 from September and 0.25.0-sourcing.1 — so
  the newer one unpacked beside the old as `savoya-quoting~g2`. Every older copy stays on
  disk, which makes the un-suffixed directory permanently the first one ever installed,
  and a glob on the plain name matches it and nothing else.

  **The skills themselves loaded from the current copy** — confirmed from the skill
  description a session was given — so the flow looked right and the duplicate was
  invisible. The damage was narrower and worse for being quiet: a session that located a
  *script* by name ran September's. That `capture_session.py` has no `--auto` flag at all
  and requires `--request`, so a capture call built for the current contract was rejected
  with bare argparse usage and the session recorded nothing — which is exactly the "first
  capture call used wrong args and failed silently" that was reported.

  So the count of installed copies was never the useful signal; **which copy the bare name
  reaches** is. Both `SKILL.md` files now give the positive instruction — match
  `savoya-quoting*` and take the highest version, numerically, because as strings "0.9"
  sorts above "0.25" and this repo has passed through both — and `setup_check.py` reports
  `stale_copy_shadows_path_lookup` alongside the version actually in use. Prefer the Base
  directory header over any of it; that is already correct. **Uploading a new build does
  not replace the old one when the name collides**, and only one of the two shows as
  installed, so the other has to be removed from the uploads list.

## An instruction that the code refuses is worse than a wrong default
- **Documentation drift about a refusal gives a session a dead end, not a wrong answer**
  (2026-10-10). When the fuel question was removed on 7 Oct, `questions.md`,
  `decision-tree.md` and `decide.py` were all updated and `SKILL.md` was not. For three
  days it told sessions to add the fuel surcharge as a document *percentage* line, and
  described "a deal-specific group discount" the same way — **both refused outright by
  C2** — and to "ask about it in the post-rate-sheet question above", a question that no
  longer existed. (The literal flag is not reproduced here: the guard below cannot tell a
  cautionary example from a real instruction, and that is the right trade.) The paragraph immediately above all of it correctly said document
  percentages are refused, so the file contradicted itself on the same page. A session
  following it hits a hard refusal in the middle of handling money and then improvises,
  which is the failure this repo keeps paying for. `regress.py` now fails on any
  instruction file showing an `--add …|percent|…` example, because C2 admits no exceptions.
- **A guard that reads one file shape cannot see the same drift in another**
  (2026-10-10). The fuel question was removed on 7 Oct and four files were updated.
  `handoff-contract.md` was not, and went on documenting a `"fuel": "keep|waive|add|none"`
  decision key for three days — while also omitting `commission_pct` and `greeter_cost`,
  which had been added. The question-set guard existed the whole time and could not see it:
  it matches **numbered prose lists**, and this is a jsonc key block. So the file that *is*
  the contract between the two skills was the one file nothing checked. The guard now also
  parses that block and compares its keys **and their order** against `BASE_ORDER`. Broken
  four ways first, including by restoring the literal stale `fuel` key, which it catches.
  *When a guard protects an invariant, ask which file shapes state that invariant — not
  just which files you were thinking of.*
- **Fuel is never removed here; it is removed in Savoya** (7 Oct, restated 2026-10-10).
  There is no fuel question. A CSM who needs it waived does that in Savoya first and the
  quote is rebuilt. `--waive "Fuel surcharge"` still exists as an escape hatch and records
  that the engine total keeps it, but it is **never offered** — only used if the user asks
  directly after hearing the Savoya route, and always with the invoicing consequence
  stated.

## Flow
- Every enumerable question uses `ask_user_input_v0`, **one per turn**, never bare prose. Labels: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md`.
- **What the flow asks about, the flow writes** (2026-10-10). `decide.py` recorded the
  personalization answer in the handoff and nothing carried it into `quote.json`, so two
  of three live sessions hand-edited the document to set `event_name` and `intro_note`.
  Hand-editing a client document is how wrong claims get in: one of those notes asserted
  that tax and driver gratuity were included, contradicting the terms on the final page of
  the same PDF. Use `set_personalization.py`, which refuses the contradictions it
  recognises; a rejected note is a wrong note.
- **What Core sent is derived, never retyped** (2026-10-10). `source_tool`, `persisted`,
  `aggregate_total` and `temporary_pricing` were patched into `intake.json` by hand
  "since handoff.py write has no flags for them". They are all in the response already,
  so the missing flags were never the problem — the handoff reads them now.
- The document flow's questions are driven by `decide.py --next` — post what it prints, record, repeat. Never skip, merge, or reorder.
- Alternatives are Option A / Option B with program totals, never a price folded into a note.

- **An email heading a CSM has to retype is one that can be retyped wrong**
  (2026-10-10). The draft's leg headings read `A1 — Saturday, March 20 — 2 × Mini Bus`:
  no pickup time, and the route only when the leg's label happened to be under 60
  characters. On a live Irvine quote every heading was rewritten before sending. They now
  carry day, clock time, route and headcount — the same four facts the PDF line has had
  for months — and the rendered output matches what that CSM typed by hand, word for word.
- **Option B names each leg it replaces once, not each alternative** (2026-10-10). Twelve
  SUVs and a Sprinter both standing in for one Mini Bus run produced `Option B (in place
  of A1, A1, A2)`, because the refs were listed per alternative. Deduplicate, preserving
  order.
- **Load the Drive tool at Stage 0, not at the capture step** (2026-10-10). The capture
  runs after delivery, when the session is winding down, and a fresh connector load at
  that moment is the easiest thing in the flow to skip — three live sessions in a row
  ended with the capture written locally and never uploaded, one saying outright *"I
  didn't upload it because it needs the Google Drive connector, which I hadn't loaded."*
  It is loaded with the machine check instead, before any of the work.

## Deliverables
- The no-PDF fallback is the **`.print.html`** (the PDF's own source, identical when printed) — never the email HTML from `render_html.py`, which is a dark message body for a different purpose.
- **Verify before delivering.** `verify_document.py` exit 0 deliver · 1 fix and re-verify · 2 PARTIAL deliver but say it wasn't fully verified. `render_print.py` exit 3 = no PDF engine; deliver the HTML and say so.
- Render everything a format needs **before** replying; deliver in one message.
- Email is a copy-ready block in the chat plus the PDF via `present_files`. No mail connector, no attaching, no sending.
- Never put a binary in a tool call. Never read back a rendered artifact.
- CSMs are not technical: no install commands, file paths, scripts or Terminal instructions. Only ever "Print → Save as PDF", worded for their OS.

## Page fit
- **Anything rendered above the table spends that page's budget.** The intro note is
  written by the user and has no length limit; a flat first-page budget cut five rows off a
  client quote and printed them under the footer. `.page` is a fixed box with
  `overflow:hidden`, so overflow is silently *cut*, never pushed to the next page.
- **Measure wrapping in characters, not in items.** A route line's height depends on how
  long the stop names are, not how many there are: one European hotel name with a street
  address wraps to three lines.

## Capture
- **One per conversation**, after the feedback exchange concludes — not per render. The script overwrites the same slug.
- Upload exactly what the script's `upload` list names. A big capture stays local by design. **Never split a capture across uploads.**
- Feedback is ask → fix → log: "Anything you'd like changed?" → fix, re-render, re-verify, re-deliver → then capture with `--change` and `--fixed`.

## Pagination is an estimate, and estimates are a system
- **Never change one side of a calibrated pair.** The wrap estimate and the page budgets
  were tuned together; making the estimate accurate without re-tuning the budgets cost two
  fixtures a page each.
- **Measure the aggregate, not the median of a ratio.** Total characters ÷ total rendered
  lines gives the real wrap width; the median of chars÷lines per row is skewed by
  partially-filled last lines and was out by 1.5×.
- **A block that can outgrow a page must paginate.** `.page` is a fixed box with
  `overflow:hidden`, so anything too tall is *cut*, not pushed — and `pdftotext` still
  extracts the cut text, so every text-based check passes while the client sees nothing.
- **Prefer a wasted page to a possible clip.** The failure modes are not equal.

- **The full capture goes up on the render pass, not only after the feedback exchange**
  (2026-10-10). Holding it back kept that pass to one Drive call and made the richest
  artifact depend on a conversational step. On a live London/Sicily/Milan quote the step
  was skipped — the PDF was delivered, the snapshot uploaded, the feedback question never
  asked (`asked: false` in the record) — so the full capture sat in a container and
  reached the folder only because the user asked for it by name. Compressed it is ~8 KB.
  The two passes carry **different titles** (`.capture.snapshot.json.gz.b64` against
  `.capture.json.gz.b64`) because Drive's `create_file` always creates, and
  `unpack_capture.py` prefers the post-feedback copy while still reading a snapshot-only
  quote — which is the only record a session that ends at delivery leaves.
- **`~` is not the user's computer** (2026-10-10). On claude.ai the home directory is a
  cloud container reclaimed with the session; on a linked desktop the shell's home is an
  isolated VM and only a *connected folder* is really the user's disk. Two real captures —
  192 KB and 36 KB — were written to `~/.savoya-quoting/captures/`, reported as saved, and
  lost. The capture report now states `local_copy.durable` and says why not, and the
  instruction is to pass `--dir` inside a connected folder when the session has one. When
  it does not, Drive is the only durable destination and the upload is not optional.
- **The capture is always compressed, so there is no size at which it stays behind**
  (2026-10-10). The old rule kept the full capture local above 25 KB — so the richest
  sessions were exactly the ones that never arrived, and both big captures of that day
  failed the test. Measured on those files gzip gives 15x and base64 for Drive's
  textContent still leaves 17 KB. The envelope declares `encoding: gzip+base64` and
  `unpack_capture.py` reverses it.
- **Clearing the pending-upload marker is a flag, not `rm`** (2026-10-10). The delete was
  denied by the auto-mode classifier, so an upload that *had* succeeded still read as
  outstanding and the backlog line shown to the user stated a false number.
  `--mark-uploaded <slug> --file-id <id>` records it, and refuses without an id so the
  backlog cannot be tidied without an upload behind it.
- **`expected.pdf_pages` is measured or absent, never guessed** (2026-10-10). It was the
  literal `3` on every capture ever taken, while the real deliverables were 4, 5 and 8
  pages and the fixtures here run 3 to 9. A captured session promoted to a fixture
  therefore started red on a number nobody had measured, which invites correcting the
  expectation to match the output — the exact habit the sixteen-leg note warns against.
  Pass `--pdf`.
- **A malformed capture call leaves a record** (2026-10-10). The step is specified as
  silent, so argparse printing usage to stderr is a bug report that never happened: one
  session's first capture call passed `--dir` with no `--slug`, failed silently, and
  nothing was recorded until the user asked. A refused call now writes
  `capture-refused-*.json` alongside the failure records, and those filenames carry
  microseconds because two in one second used to collide and one replaced the other.

- **When Drive fails, ask — don't just mention it** (2026-10-10). A soft line the user
  could do nothing with in the moment is how three sessions in a row ended with the record
  stranded, the last one saying outright *"I didn't upload it because it needs the Google
  Drive connector, which I hadn't loaded."* The user is the only one who can switch the
  connector on, so the capture step now asks them while the session is still alive —
  *"I've turned it on, try again"* / *"Skip it this time"* — once, after the deliverable,
  never before it. A connector switched on but lacking Editor on the folder fails
  identically, and the same ask covers both. Still no paths, scripts or commands.

## Capture is the only channel
- **Capture hardest when the session went worst.** A session that patched something in a
  working copy or rebuilt a line by hand is the most valuable one of the week and the most
  likely to skip the step. `--workaround` is for exactly that.
- **A read-only plugin does not mean read-only feedback.** The capture writes to
  `~/.savoya-quoting/captures/` and Drive, neither of which is the plugin.
- **The capture cannot fail on you**, so there is no input bad enough to skip it:
  `--request` is optional, a missing handoff is noted, and an unexpected error still writes
  a failure record and exits 0.
- **Telling the user about a bug is not reporting it.** They are not the maintainer.

## Maps
- **A schematic and a street map are different claims.** When the mapping services are
  unreachable the map becomes an overview of stops in order with straight connecting
  lines. The document must title it differently and say the lines are not driving routes;
  a client reading them as roads is being misled by us, not by the network.
- **Tell the CSM which one went out.** They decide whether a schematic suits that client,
  and they can't see the PDF as the client will until it's sent.

## Setup can fail silently
- **A Drive connector that is switched on can still fail to write.** The upload goes as the
  CSM's own Google account; without Editor on the shared folder every upload fails and
  everything looks connected. Only writing a test entry proves it.
- **While Drive is unreachable, say so every session that delivers a document**, naming the
  backlog. Saying it once is how the tool ran for weeks with nothing reaching the folder.
- **"Is this working?" is a real question with a real answer** — run the setup check rather
  than reassuring them.

## Engine
- Quote on the exact path (`generate_quote_options` / `calculate_quote_units`). There is no
  approximate path and no estimates: a profile with no passenger prices normally (omit
  `passenger_id`), and no stored rate in the market means ask for a temporary rate or
  another vehicle, then `calculate_temporary_quote_units`. Never persisted — say so.
- Always send `commercial_tbd: true` on airport stops, even when the client gave a flight number; the engine needs a resolved airline id and nothing resolves one. Keep the number as a client-facing note.
- Never re-geocode a stop that already has coordinates; always qualify a geocode with the service area.
- **Core's `presentation` block is the CSM-facing view, and internal.** `render_presentation.py`
  prints it; it carries rate ids and rack-versus-effective rates, so **it never becomes client
  copy**. The client document is built from `quote.json` by this skill, as before. A
  presentation total that disagrees with the quote units is shown, both figures, never resolved
  silently.
- **A temporary rate is a base rate**: Core applies the client's contracted discount and
  fuel on top of whatever was supplied ($250.00/hr → $192.50/hr effective). Never present a
  supplied rate as the client's rate, and never treat the two as interchangeable.
- **Discounts are additive in basis points, not compounded.** 30% contracted + 10%
  temporary = `effective_discount_basis_points: 4000`, not 37%. Core returns
  `subtotal_amount`, `total_amount`, `temporary_discount_amount` and
  `temporary_discount_label` — standard → discount → net is Core's end to end, with nothing
  left to compute.
- **Exactly one Core warning is suppressed**: "No passenger was selected", and only on a unit
  that priced — we send no `passenger_id` unless the user named one, so Core attaching an
  eligible passenger is the expected path. Everything else Core sends surfaces, including a
  warning we don't recognise. Suppressing warnings wholesale, or only printing the shapes we
  recognise, is how a real one gets hidden. `regress.py` asserts all of this.
- **Never state a price Core did not return — including a comparison** (2026-10-09). Asked
  for the cheapest package with sourcing allowed, a session did rate-sheet arithmetic and
  answered "about $32,133, roughly $80 less". The exact quote was **$32,920.26**, or
  $707.18 *more*, because the estimate ignored the 5.25 hours of positioning drive time
  that sourcing exists to pay for. Flagging it as "my arithmetic, not a Savoya quote" did
  not help: it was still a number a CSM could repeat to a client. Price the candidates, or
  say a quote is needed.
- **"No service area" and "no service area reported" are different facts** (2026-10-10).
  A stop outside every Savoya market arrives as `location.service_area: null` — the key
  present, the value empty. An older or trimmed response carries no `location` at all,
  which means *unknown* and must never be read as *nowhere*: doing so marked three
  single-market fixtures as cross-market sourced, and the suite caught it. The same
  distinction decides whether a leg is treated as sourced at all, which is why
  `stop_has_no_service_area()` tests for the key before the value.
- **The expensive sourcing case reports `primary == source`** (2026-10-10). When no stop
  sits in a service area, Core prices the unit from whichever market owns the nearest
  fleet and that market is genuinely both its primary and its source — so
  `source != primary`, the test for a cross-market override, is **false** for it. It is
  also the costly case: a 36-minute Catania transfer came back as **14.75 hours** hourly
  out of Naples, $9,233.50, and $18,623 with its return against a $23,259 quote. It now
  earns the client-facing marker and an internal flag that states the hours and the money,
  so the CSM sees the number before anything is sent.
- **`service_area` on a leg means where the vehicle came from** (2026-10-10). Since
  sourcing, reading it for the document header put "San Diego, CA" on an Orange County
  event whose Mini Buses happened to be positioned from San Diego. `meta.service_area`
  reads `primary_service_area` — where the work is.

## 0.27.1 additions (2026-10-16)

- **Capture needs one consent answer per machine (R76).** Unasked: verify asks and writes nothing. Declined: verify skips silently. Granted: the capture runs as before. The answer and the user's name live in `~/.savoya-quoting/config.json`.
- **The printed document never clips (R77).** The renderer measures the layout in a browser and moves a totals block that does not fit onto its own page. Commission sits as a hero line under each option total.
- **The client-requests sentence appears once.** If the intro note already says it noted the request, the renderers do not add it, and the session does not write it twice.

## 0.27.2 additions (2026-10-17)

- **Pricing responses are saved by `handoff.py ingest`, never retyped (R78).** It stores the response exactly as given and rejects one that does not parse, has no priced units, or whose units do not add up to its own total. A session that cannot save the data stops and reports (`capture_session.py --blocked`); it never rebuilds a `raw_quote.json` by hand.
- **Separately priced packages become one document (R79).** `handoff.py write --package A --package B`: the first is Option A, the rest are alternatives, a unit priced the same in both is `--shared`. Each option keeps its own Core total. Never tell the user a single document with both scenarios is impossible.
- **A blocked session still reports (R80).** `capture_session.py --blocked "<reason>"` needs no `quote.json`; same consent rule as a delivered capture.
- **State the reading of each scenario before pricing (R81).** One yes from the user, then `--reading` carries it into the assumptions.
- **Commission is a badge (R82).** Under each option total in the PDF; in the email it sits directly under the totals beneath a COMMISSION heading. Still computed in code, still changes no total, still flat.

## 0.27.3 additions (2026-10-17)

- **A stop that will not resolve asks for an address (R83).** Never a substituted stop, never a deleted travel time. Every lookup is recorded with `--stop-note`; `write` refuses an unresolved one. As-directed queries spell out the state or province.
- **A headcount range is asked before pricing (R84).** `write` refuses a ranged request without `--headcount N`, and units priced without that `passenger_count`.
- **Deliver only what was asked (R85).** `verify_document.py` prints the deliverables; `draft_email.py` refuses a PDF-only job unless `--asked`.
- **A saved response is never edited (R78).** Colliding unit keys are namespaced by the merge; a response too large to paste uses `ingest --without-presentation`, which records what it left out.

## 0.27.4 additions (2026-10-17)

- **A split headcount is right; a duplicated one is not (R91).** 75 passengers priced as 50 on a coach plus 25 on two vans passes. `handoff.py write` requires a `passenger_count` on every unit and that the units serving one trip add up to `--headcount`. Never put the full headcount on every group: Core sizes the vehicle count from each group's number.
- **A refused step is never walked around (R92).** A refused write leaves `handoff/blocked.json`; `decide.py` and `normalize_quote.py` stop while it exists. Fix the cause and write again, or tell the user why not. Never build `intake.json`, keep decisions by hand, or call the scripts' internals to get past it.
- **Never ask the user about the product's own working (R93).** After the quote there is one question: customize it, go on to the client document, or just the quote. Every named scenario is priced, shown and written. With two or more options the same question also settles which go to the document, "both options" first (amended 0.27.5); there is no separate "which one in detail?" question.
- **A record carries the real files (R94).** Upload each file's text exactly; the byte count and SHA-256 are printed. The blocked record is uploaded packed, like the full capture.

## 0.27.5 additions (2026-10-17)

- **One question settles the options and the document (R93).** With two or more options on screen the post-quote picker leads with `Both options → client document` (all N past two), then each option alone, `Customize first` and `Just the quote`. "Both" writes every option with `--package`; one option writes only its saved package, with no new pricing call.
- **An options response is saved by `ingest` (R78).** `handoff.py ingest --name A` takes a `generate_quote_options` response, checks every option as its own package and saves `A_<option key>`; one failing option saves none. In the merge, an alternative pairs with the Option A unit that has the same key.
- **A quantity above inventory is extended by `extend-quantity` only (R95).** Never scale a unit by hand. It needs the shortfall message, the vendor statement and the approver; it is internal and never in a client document.
- **The record says whether the feedback question was reached (R96).** A snapshot is `pending` until the second pass; any reply that is not a change request is `no_changes`.
- **A client's time has a kind (R18, R34).** `--time-reading` records flight departure, pickup or airport arrival target. Pickup is the target minus Core's drive time, the unit must be priced at that pickup, and the document prints both times.
- **A dimension comes from the user (R35).** Print one only from `--fact`; `vehicle-types.md` is for internal screening and nothing in it is stated to a client.
- **What the client supplied is printed as supplied (R62, R74).** `--venue` keeps their venue name, `--flight` prints their flight, and a supplied flight is never a placeholder or reported as one. The fuel surcharge is whole-quote only: header and terms, never a leg, note or email line, and a request to show it per leg is neither asked nor printed.
- **Client requests Core cannot answer are asked, one each (R72, R73).** `decide.py` asks `request:<n>`: included, not included, extra cost, confirm, or the user's words. Tax, gratuity, cancellation and fuel display are boilerplate. A fit or luggage question is a request and is never answered as a fit. A greeter or meet-and-greet is asked once, through the greeter question.
- **A day block that overlaps an airport leg is a question (R97).** `--overlap BLOCK|TRANSFER|choice`, asked within one option only. Units on the same date, time and stops are one trip in parallel and are never asked about (R107).
- **The pickup is accepted inside an arrival window (R105).** The car reaches the airport 0 to 10 minutes before the target, using the drive time Core returned for the pickup priced. Outside it, re-price once at target minus drive time; still outside, ask the user to confirm the pickup.
- **Client requests are answered before the document is built (R108).** `decide.py` asks `request:<n>` first; `normalize_quote.py` refuses while any is open.
- **A held-open stop prints a neutral label (R98).** `--placeholder-stop UNIT|stop|label`; the resolved name or address never prints.
- **Notes collapse and totals come first (R99).** Identical notes print once, naming their legs; notes up to 70 characters print inline; the totals sit on the first summary page.
- **Guidance sits where the mistake happens (R101–R104).** One tip with the first client or stop question; a stand-in client for a client Savoya does not have (`--client-source stand-in --prospect`, refused when the quote carries a contracted discount, the document names the real client); the discount, greeter and temporary-rate questions say the figure is not stored in Savoya, and `decide.py --fyi` repeats what applies at delivery; a failed PDF or map is answered with the printable document or dropping the map, and a note to ask the product team to enable it.
- **A no-commission copy is a variant (R100).** `no_commission_copy.py` works on a copy, checks the total does not move and renders under a separate name.
