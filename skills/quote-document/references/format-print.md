# PDF / print format (default client deliverable)

`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/render_print.py quote.json out.pdf [--html out.print.html] [--no-cover]` renders three pages and converts with Chromium (Playwright) or wkhtmltopdf. Read `client-safe-rules.md` before hand-editing the print HTML.

## Benchmark
This format was designed against a CSM-built quote (Access TCA wedding, Hartford, Aug 2026). Keep what that document got right — line refs with notes, hero total, standard-vs-net rate card, explicit cancellation table — and fix what it got wrong: flat gray type with no hierarchy, pricing buried at the foot of the page, a half-empty page, the marketing cover competing with the quote.

## Pages
1. **Cover** — one of the marketing audience covers from `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/covers/` (`personalization.cover` or `--cover key`), stitched in front of the body with pypdf. `custom` draws the generated cover instead: Savoya logo (+ client logo), event name headline, "Prepared for [client]", dates, value-prop tiles, contact footer, with `cover_image_url` as a full-bleed photo. Skip with `--no-cover` for quick revisions.
2. **Quote** — dark header bar. Title + event subtitle; meta grid (prepared for/by, travel coordinator, service area, passengers, date, valid until, discount %, fuel surcharge %); **hero estimated total** top right; intro note; line table grouped by day (Ref · Service with route/time · Basis · Min · Qty · Hrs/veh · Rate · Total) with per-day subtotals when there's more than one day; line notes left, pricing breakdown right.
3. **Option B** (only when `--alternative` was used) — same layout as the quote page for the swapped lines, with a breakdown that adds the unchanged Option A lines back in so the hero shows a *program* total the client can compare directly against Option A. Page count becomes 4.
4. **Route overview** (only when `route_map.py` was run) — static OpenStreetMap map with numbered stops, plus a Ref · Route · Distance · Drive time table. Drive times come from OSRM and are labeled as planning estimates. Attribution is rendered automatically.
5. **Rate card** — one row per vehicle type used: standard rate over net rate (copper), minimum, minimum total (standard over net), cancellation. Legend explains what "net" means. Cancellation-policy table, closing note + account-manager card, terms verbatim.

Page numbers and the confidential footer are automatic.

## Where things come from
| Document element | quote.json field |
|---|---|
| Hero total | `total_cents` |
| Discount % / Fuel surcharge % in header | global `percent` adjustments (negative = discount) |
| Net rates on rate card | standard × global discount × global surcharge |
| Line notes | `legs[].client_notes` |
| Event pricing flag on a line | `legs[].pricing.special_event` |
| "Flight details to be confirmed" | any stop with `flight.tbd` |
| Travel coordinator, service area | `meta.travel_coordinator`, `meta.service_area` |

## Hand-edit triggers
- More than ~7 lines on the quote page: the table will overflow the fixed 11in page. Split by day into two quote pages (duplicate the `<section class="page">` block) before converting.
- Multi-market quotes: set `meta.service_area` to something like "Orlando · Los Angeles · New York" — the normalizer only picks the first.
- Wave-based group moves (e.g. 3:00pm and 3:15pm outbound, 11:00pm return) belong in the line note, with the continuous-charter rationale spelled out the way the CSM did: "single 6-hr minimum per vehicle instead of two blocks."

## Email copy
`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/draft_email.py quote.json --json draft.json` writes the house-style email: greeting, opener naming any discount/surcharge, one quote block per leg (Vehicle type · Cancellation policy* · Minimum hours · Quoted time · Adjusted Client Hourly Rate · Estimated Total), the asterisked cancellation note, program total, inclusions, a TBD nudge if any placeholder exists, closer, sign-off. Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/email-voice/README.md` and two samples, then adjust the opener, recommendation sentence, and closer; keep the numbers block exactly.

Deliver it **in the chat**, like this:

```
Subject: Savoya quote — Yerdle Leadership Offsite (Sep 16 – 18)

Hi Desiree,
…
```

followed by `present_files` with the PDF in the same reply. The user copies the text into Gmail/Outlook themselves and drags the PDF in. Nothing else — no connector drafts, no attachments, no sending. That keeps the deliverable one paste and one drag for the user, and keeps the PDF out of tool calls entirely.

## The printable document (`.print.html`)
`render_print.py` always writes this alongside the PDF, and **it is the PDF's source** — same layout, same theme, same pages. Printing it from a browser with margins set to None yields a byte-equivalent file (verified: identical page count, page size and text).

It is an **offered format**, not only a fallback — choose it when the user wants a page to open in a browser rather than a PDF reader. It is a deliverable in its own right, not an intermediate:
- On screen it renders as a stack of pages on a grey backdrop, with a sticky print bar at the top that explains how to save it as a PDF (worded for macOS or Windows by a small inline script).
- The bar is `display:none` in print, so the saved PDF is clean.
- Hand it over whenever the machine has no PDF engine, or whenever a user wants something they can open without a PDF reader.

**Sharing it.** It's a file. There is no hosted URL for quote documents yet, so "send them a link" isn't available — attaching it works, but many corporate mail systems quarantine `.html` attachments, so the PDF is the safer external send. Say that plainly if asked rather than implying a link exists.

**Do not confuse it with `render_html.py`**, which is the dark-themed *email body*. Different design, different purpose; the two are not interchangeable.
