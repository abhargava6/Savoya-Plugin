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
- **A reconciling total does not mean a correct breakdown.** C4 and C5 guarantee the total
  by construction, which is exactly why they cannot catch a line mislabelled as its
  opposite. A line stating a positive percentage must never carry a negative amount.

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
- **Operational** (greeter, on-site staff, signage, PA, luggage vehicle) — the document flow asks the user for a cost; an amount becomes a line, no amount becomes a "arranged separately, not in vehicle pricing" note.
- **Data-answered** (pickup times, drive times, vehicle counts, how long the vehicle is held) — the quote holds the answer implicitly. Surface it as an explicit callout at the top of the PDF **and** the email. Never make a client decode sixteen timestamps.

## Flow
- Every enumerable question uses `ask_user_input_v0`, **one per turn**, never bare prose. Labels: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/asking-questions.md`.
- The document flow's questions are driven by `decide.py --next` — post what it prints, record, repeat. Never skip, merge, or reorder.
- Alternatives are Option A / Option B with program totals, never a price folded into a note.

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
