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
