#!/usr/bin/env python3
"""Render quote.json as a print-ready HTML and PDF (Savoya light print theme).

Usage: render_print.py quote.json out.pdf [--html out.html] [--no-cover]

Pages: (1) cover — brand + audience/value strip, (2) quote — hero total, line
table with refs, pricing breakdown, line notes, (3) rate card — standard vs net
rates, minimums, cancellation table, terms. Renders via Playwright/Chromium;
falls back to wkhtmltopdf if Playwright isn't available.
"""
import argparse
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys


def notes_of(leg):
    """client_notes is a LIST of strings. A bare string is a common authoring slip —
    and iterating it yields one character per item, which rendered the note as a
    vertical column of single letters down the page. Accept either shape."""
    n = leg.get("client_notes")
    if not n:
        return []
    if isinstance(n, str):
        return [n]
    return [str(x) for x in n if str(x).strip()]



INLINE_NOTE_MAX = 70      # a note this short prints under its route line (R99)


def _joined_refs(refs):
    return refs[0] if len(refs) == 1 else ", ".join(refs[:-1]) + " and " + refs[-1]


def prep_notes(legs):
    """R99. Identical notes collapse into one note that names every leg it covers; short notes
    print inline under the route; what remains is the notes block. Copies the legs: the quote
    is not changed, and every note's text still reaches the document."""
    legs = [dict(l) for l in legs]
    seen = {}
    for l in legs:
        for n in notes_of(l):
            seen.setdefault(" ".join(n.lower().split()), []).append(l)
    done = set()
    for l in legs:
        keep, inline = [], []
        for n in notes_of(l):
            k = " ".join(n.lower().split())
            holders = seen[k]
            if len(holders) > 1:
                if k in done:
                    continue                                   # said once already, on the first leg
                done.add(k)
                n = f"{_joined_refs([str(h.get('ref')) for h in holders])}: {n}"
            (inline if len(n) <= INLINE_NOTE_MAX else keep).append(n)
        l["client_notes"] = keep
        l["inline_notes"] = inline
    return legs


LOGO = "https://res.cloudinary.com/dctq8l4sp/image/upload/v1776808626/savoya-logo_dlhiha.png"
COPPER, COPPER_DARK, AMBER = "#B87333", "#8B4513", "#F59E0B"
INK, GRAY, MUTED, RULE, TINT = "#1A1A1A", "#5C5650", "#8A837C", "#E6E1DC", "#F7EDE4"


def e(s):
    return html.escape(str(s)) if s is not None else ""


def money(c):
    return f"${(c or 0)/100:,.2f}"


def day(iso, fmt="%a %m/%d/%Y"):
    try:
        return dt.datetime.fromisoformat(iso).strftime(fmt)
    except (ValueError, TypeError):
        return iso or ""


def clock12(hhmm):
    try:
        return dt.datetime.strptime(hhmm, "%H:%M").strftime("%-I:%M %p")
    except (TypeError, ValueError):
        return ""


def time_of(iso):
    try:
        return dt.datetime.fromisoformat(iso).strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return ""


def hrs(h):
    return f"{h:g} hr" if h is not None else "—"


def global_pct(q, negative):
    """Sum of global percent adjustments that are discounts (negative) or surcharges."""
    tot = 0.0
    for a in q.get("adjustments", []):
        if a["type"] == "percent" and not a.get("applies_to") and not a.get("waived"):
            if (a["value"] < 0) == negative:
                tot += a["value"]
    return tot


def pct_suffix(a):
    """The " (35%)" the adjustment table appends -- unless the label already says it.

    Core's own discount labels sometimes carry the figure ("Additional 5% discount"),
    and appending unconditionally printed "Additional 5% discount (5%)" in a client
    PDF on 10 Oct 2026. The label is left untouched (normalize_quote.client_label
    explains why mangling it is worse); the suffix is what gives way.
    """
    if a.get("type") != "percent":
        return ""
    if "%" in (a.get("label") or ""):
        return ""
    return " (" + format(abs(a["value"]), "g") + "%)"


def net_rate(rate_cents, disc_pct, sur_pct):
    v = rate_cents * (1 + disc_pct / 100.0)
    v = v * (1 + sur_pct / 100.0)
    return int(round(v))


COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "covers")


def cover_choice(q, cli):
    """Resolve which cover to use: CLI flag > personalization.cover > 'general'."""
    key = cli or (q.get("personalization") or {}).get("cover") or "general"
    if key in ("custom", "generated"):
        return "custom", None
    cat = json.load(open(os.path.join(COVERS_DIR, "catalog.json"), encoding="utf-8"))
    entry = next((c for c in cat["covers"] if c["key"] == key), None)
    if not entry or not entry.get("file"):
        sys.exit(f"Unknown cover '{key}'. Options: " + ", ".join(c["key"] for c in cat["covers"]))
    path = os.path.join(COVERS_DIR, entry["file"])
    if not os.path.exists(path):
        sys.exit(f"Cover image missing: {path} — run scripts/make_covers.py <covers-src> to pre-render it")
    return key, path


def cover_asset_page(cover_img):
    """Place a pre-rendered marketing cover (JPEG from scripts/make_covers.py) on a black Letter page.
    Chromium emits one single-origin PDF — no merged content streams (macOS Preview breaks on those),
    and no rasterization at quote time (that costs ~20s cold)."""
    import base64
    ext = os.path.splitext(cover_img)[1].lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    b64 = base64.b64encode(open(cover_img, "rb").read()).decode()
    return (f'<section class="page blank" style="background:#000;display:flex;align-items:center;justify-content:center;">'
            f'<img src="data:image/{mime};base64,{b64}" style="height:11in;width:auto;max-width:8.5in;display:block;"></section>')


def blank_black_page():
    return '<section class="page blank" style="background:#000;"></section>'


# ---------------------------------------------------------------- pages
def cover_page(q):
    pz = q.get("personalization", {})
    hero = pz.get("cover_image_url")
    bg = (f"background:linear-gradient(180deg,rgba(15,15,15,.55),rgba(15,15,15,.92)),url('{e(hero)}') center/cover;"
          if hero else "background:radial-gradient(1200px 600px at 30% 10%,#2a1f16 0%,#0F0F0F 60%);")
    client_logo = (f"<img src='{e(pz['client_logo_url'])}' style='height:34px;margin-left:18px;vertical-align:middle;filter:brightness(1.1);'>"
                   if pz.get("client_logo_url") else "")
    event = pz.get("event_name") or q["meta"].get("title")
    dates = sorted({day(l["date"], "%B %-d, %Y") for l in q["legs"] if l.get("date")})
    date_line = " · ".join(dates[:3]) + (" …" if len(dates) > 3 else "")
    return f"""
<section class="page cover" style="{bg}">
  <div class="cover-top"><img src="{LOGO}" style="height:34px;">{client_logo}</div>
  <div class="cover-mid">
    <div class="eyebrow">Ground transportation proposal</div>
    <h1>{e(event)}</h1>
    <div class="cover-sub">Prepared for <b>{e(q['meta']['client'])}</b></div>
    <div class="cover-tag">The trusted ground transportation partner for your organization.</div>
    <div class="cover-dates">{e(date_line)}</div>
  </div>
  <div class="cover-grid">
    <div><b>Complete visibility</b><span>Monitor active trips, travelers, and activity from one platform.</span></div>
    <div><b>Consistent experience</b><span>The same dependable service regardless of destination or schedule changes.</span></div>
    <div><b>Global reach</b><span>350+ markets worldwide with one process and one standard.</span></div>
    <div><b>A team behind you</b><span>Every reservation backed by people solving problems before they reach you.</span></div>
  </div>
  <div class="cover-foot"><span>866.916.3081</span><span>savoya.com</span><span>inquiries@savoya.com</span></div>
</section>"""


def passenger_total(legs):
    """How many people this quote moves, for the document header.

    `max()` across legs was wrong and printed a wrong number on a client PDF: a
    1,000-passenger job came out as 656, the largest single vehicle group, because
    the party was split across 16 Mini Buses and 27 Sprinters on the same trip.
    Plain `sum()` is wrong the other way — a three-day itinerary would treble, and
    on the wedding fixture it reports 132 people for a 120-guest wedding.

    A leg's `passenger_count` is that leg's share, not the whole party. Two 13-seat
    Sprinters carrying 6 each are 12 people, not 6. So: legs that are the same
    movement — same pickup datetime, same stop sequence — are one party and sum;
    separate movements do not add, and the largest wins.

    What counts as "the same movement" is the whole question, and an exact stop
    sequence was too strict. The World Cup quote ran four shuttles on one date from
    White Plains, Grand Central, Newark Penn and Mineola, each carrying ten people to
    MetLife Stadium and back. Four different sequences, so four movements, so the
    header read **10** for a date on which forty guests travelled. Shuttles converging
    on one place on one day are one movement (decided 2026-10-10).

    But the destination alone is too loose, and the wedding fixture proves it: its two
    Sprinters run Hilton -> Stonehurst while its Mini Buses run Hilton -> Stonehurst ->
    Hilton, same day and same destination, and summing those reports **132** people for
    a 120-guest wedding. The structural difference between them is real -- one way
    versus a round trip -- so the key keeps the trip's SHAPE and drops only the origin:

        (calendar date, one-way or round trip, where it goes)

    For a round trip "where it goes" is the turnaround, not the last stop, which is the
    origin again. That one change makes the four World Cup shuttles one movement of 40
    while leaving the wedding at 120, the Irvine day at 80 (its two legs run opposite
    ways, so they are different movements), and the London itinerary at 5.

    Cross-market sourcing makes this matter more, not less: one movement now routinely
    splits across allocations from different markets.
    """
    def shape(l):
        names = [str(s.get("label") or s.get("address") or "") for s in l.get("stops") or []]
        if len(names) >= 3 and names[0] == names[-1]:
            # a round trip: the turnaround is the destination, and the stops between
            # origin and return identify it
            return ("round", tuple(names[1:-1]))
        return ("oneway", tuple(names[1:]))

    movements = {}
    for l in legs or []:
        if l.get("alternative_of"):
            continue              # Option B units are the same people, priced twice
        sig = (str(l.get("date"))[:10], shape(l))
        movements[sig] = movements.get(sig, 0) + (l.get("passenger_count") or 0)
    return max(movements.values(), default=0)


# Set by main() when the measured layout shows the totals block running past the footer.
# The paginator below works in estimated cost units, and no estimate covers every combination
# of intro length, header fields, adjustment lines and leg notes. The Yerdle quote of
# 16 Oct 2026 (long intro, seven header fields, three adjustment lines, two sourced legs)
# came out 103px past the footer with its total invisible. Estimates stay as the first
# guess; the browser is the check, and a clipped totals block moves onto its own page.
FORCE_OWN_SUMMARY = 0      # 0 = trust the estimate, 1 = Option A's totals on their own page, 2 = both


def quote_page(q):
    m, pz = q["meta"], q.get("personalization", {})
    disc, sur = global_pct(q, True), global_pct(q, False)
    meta_cells = [
        ("Prepared for", m.get("client")),
        ("Prepared by", m.get("prepared_by")),
        ("Travel coordinator", m.get("travel_coordinator")),
        ("Service area", m.get("service_area")),
        ("Passengers", str(passenger_total(q["legs"])) if q["legs"] and passenger_total(q["legs"]) else None),
        ("Date", day(m.get("prepared_on"), "%m/%d/%Y")),
        ("Valid until", day(m.get("valid_until"), "%m/%d/%Y")),
        ("Discount", f"{abs(disc):g}%" if disc else None),
        ("Fuel surcharge", f"{sur:g}%" if sur else None),
        # No commission cell here: the rate and the amount sit under each option's total
        # (hero_comm in quote_page_for), where the figure it relates to is. R59, 2026-10-16.
    ]
    meta_html = "".join(f"<div><label>{e(k)}</label><span>{e(v)}</span></div>" for k, v in meta_cells if v)

    return quote_page_for(q, [l for l in q["legs"] if not l.get("alternative_of")], meta_html, pz, m, "Group travel quote", option=None)


def option_page(q):
    alts = [l for l in q["legs"] if l.get("alternative_of")]
    if not alts:
        return ""
    ob = q.get("option_b") or {}
    return quote_page_for(q, alts, "", q.get("personalization", {}), q["meta"], "Option B", option=ob)


def quote_page_for(q, legs_in, meta_html, pz, m, bar_label, option):
    legs_in = prep_notes(legs_in)
    # group legs by date
    groups = {}
    for l in legs_in:
        groups.setdefault(day(l.get("date"), "%A — %m/%d/%Y") or "Date to be confirmed", []).append(l)

    def row_html(l):
            p, v = l["pricing"], l["vehicle"]
            route = " → ".join(e(s["label"]) for s in l["stops"])
            when = time_of(l.get("date"))
            if l.get("airport_target") and when:   # R34: the pickup and the airport arrival are different times
                when = f"Pickup {when} &middot; airport arrival {clock12(l['airport_target'])}"
            basis = "Hourly" if p["method"] == "hourly" else "Transfer"
            _ev = p.get("special_event") or {}
            ev = ("<div class='ev'>&#9888; Event pricing &mdash; "
                  f"{e(_ev['name'])}</div>" if _ev.get("name")
                  else "<div class='ev'>&#9888; Event pricing in effect</div>" if _ev
                  else "")
            rt = l.get("route")
            if rt:
                bits = []
                if rt.get("distance_mi"):
                    bits.append(f"~{rt['distance_mi']:g} mi")
                if rt.get("drive_min"):
                    bits.append(f"~{rt['drive_min']} min drive")
                drive = f" <span class='cap'>· {' / '.join(bits)}</span>" if bits else ""
            else:
                drive = ""
            tbd = "<div class='tbd'>Flight details to be confirmed</div>" if any(s.get("kind") == "airport" and s.get("flight", {}).get("tbd") for s in l["stops"]) else ""
            if l.get("flight_supplied"):
                tbd = f"<div class='tbd'>Flight {e(l['flight_supplied'])}</div>"   # R74: as the client gave it
            # Cross-market sourcing (R51). The separate line already exists, because
            # Core returns one source market per unit and each unit is its own leg —
            # so the same vehicle type legitimately appears twice, at two different
            # line totals. Without a marker that reads as a duplicate or a mistake.
            # Soft wording on purpose: a client is told where the car comes from, not
            # that their own market ran short.
            src = ""
            if l.get("sourced_from_other_market") and l.get("service_area"):
                src = (f"<div class='sourced'>Positioned from our "
                       f"{e(l['service_area'])} partners &middot; additional drive time "
                       f"included in the rate</div>")
            inl = "".join(f"<div class='inl'>{e(n)}</div>" for n in (l.get("inline_notes") or []))
            return f"""<tr>
  <td class='ref'>{e(l.get('ref'))}</td>
  <td class='svc'><b>{e(v['name'])}</b> <span class='cap'>({v.get('capacity')} pax)</span>
      <div class='route'>{when}{' · ' if when else ''}{route}{drive}</div>{ev}{src}{tbd}{inl}</td>
  <td class='num'>{e(basis)}</td>
  <td class='num'>{hrs(p.get('minimum_hours')) if p['method']=='hourly' else '—'}</td>
  <td class='num'>{v['quantity']}</td>
  <td class='num'>{hrs(p.get('billable_hours')) if p['method']=='hourly' else '—'}</td>
  <td class='num'>{money(p['rate_cents']) if p['method']=='hourly' else money(p['per_vehicle_cents'])}</td>
  <td class='num tot'>{money(p['line_total_cents'])}</td></tr>"""

    # --- pagination by estimated height, not leg count. A leg with three long client_notes
    # occupies several times the space of a bare one; counting legs clipped real quotes.
    # Recalibrated in 0.23.9, after 0.23.5 shipped a regression that --pdf caught and the
    # ordinary suite could not: access-tca-wedding rendered 4 pages against 3 and
    # sixteen-leg-route-map 9 against 8, each wasting a near-empty page.
    #
    # The cause was not a wrong number. 0.23.5 added an accurate character-based wrap
    # estimate ON TOP of budgets that had been tuned against the old, deliberately
    # pessimistic count-of-stops estimate. The two were one calibrated system and only one
    # side was changed, so every leg was costed twice over. Measured in a browser, the
    # .svc column fits ~44 characters per line at 9pt, so the character estimate was about
    # right -- the budgets were what no longer matched it.
    #
    # The safe band is 58-62 / 69-74; at 66/78 six-leg-heavy-notes loses a page, which
    # means over-packing and real clipping. These sit at the low end, furthest from that.
    FIRST_BUDGET, CONT_BUDGET = 58, 69
    GROUP_COST = 4                          # a date header + its subtotal row
    ROUTE_CHARS = 48                        # measured: ~44 chars/line in the .svc column
    INTRO_CHARS = 95                        # chars per wrapped line in the full-width intro

    # The intro note sits ABOVE the table on the first page, so it spends part of that
    # page's budget. FIRST_BUDGET used to be a flat constant, so an intro note longer than
    # about two lines pushed the table down while the budget still believed it had the
    # whole page: the last rows were cut by the page break and the text ran into the
    # footer. The note is written by the user at question 4, so its length is not bounded.
    # The carried-client-requests line (R73) is deliberately NOT rendered here. It lives in
    # the email copy and the HTML email, which do not paginate. Added to this intro on
    # 16 Oct 2026 it pushed the Yerdle quote's page 2 52px past the footer (a two-page
    # document already at 100% of the box), and a larger budget cost the nine- and
    # sixteen-leg fixtures a page each. The PDF carries the terms; the email carries the ask.
    intro_text = (pz.get("intro_note") or "") if option is None else ""
    intro_cost = (2 + 2 * (len(intro_text) // INTRO_CHARS)) if intro_text else 0
    first_budget = max(16, FIRST_BUDGET - intro_cost)

    def leg_cost(l):
        # client_notes render in their own block below, not in the leg row
        c = 7                               # route line, vehicle line, cancellation
        # Two estimates of how far the route line wraps, and we take the pessimistic one.
        # Counting stops alone assumes every stop name is short: "Four Seasons Hotel Milano,
        # Via Gesu 6/8" is three wrapped lines on its own, and a leg of those overflowed a
        # page that the stop count said would fit. notes_cost already measures length this
        # way; the route line was the one place still counting items instead of characters.
        # Characters, not stop count: two stops named "Four Seasons Hotel Milano, Via Gesu
        # 6/8, 20121 Milano MI" wrap further than five short ones. Character length
        # subsumes the stop count, so taking the max of both just costs every leg twice.
        stops = l.get("stops") or []
        route_chars = sum(len(str(s.get("label") or "")) + 3 for s in stops)
        c += 2 * max(0, -(-route_chars // ROUTE_CHARS) - 1)
        if (l.get("pricing") or {}).get("special_event"):
            c += 2
        if l.get("sourced_from_other_market") and l.get("service_area"):
            c += 2                          # the "Positioned from our ... partners" line wraps to two
        if any(s.get("kind") == "airport" and (s.get("flight") or {}).get("tbd") for s in (l.get("stops") or [])):
            c += 1
        c += sum(1 + len(str(n)) // 60 for n in (l.get("inline_notes") or []))   # R99 inline notes
        return c

    # Measured in a browser: the notes column is 326px wide and fits ~23 characters per
    # line, not the 60 this assumed -- a 2.6x underestimate of how far a note wraps. That
    # is why a 16-leg summary page overflowed by 115px with a note cut across the footer
    # even after the block was split across pages. One constant, used by both the
    # "does the block fit" decision and the per-page chunking, so the two cannot disagree.
    # One cost unit is one rendered line, ~15px. Derived rather than guessed: the 16-leg
    # fixture's notes occupy 1176px = 78 line-equivalents, of which ~62 are text across
    # 1864 characters, so the column takes ~34 characters per line. An earlier attempt
    # used 23, which was the median of chars/lines on multi-line rows -- skewed by
    # partially-filled last lines, and a 1.5x overestimate that cost three extra pages.
    NOTE_CHARS = 34
    NOTES_ROWS_BUDGET = 53          # ~796px of free height on a notes page, at ~15px/line
    NOTES_HEADING_COST = 4

    def note_cost(l):
        # one line of row padding, plus however far the text wraps
        return sum(1 + -(-len(str(n)) // NOTE_CHARS) for n in notes_of(l))

    def notes_cost(legs_with_notes):
        # Deliberately the ORIGINAL, looser estimate. This feeds one decision only --
        # whether the summary block shares the last leg page or takes its own -- and that
        # decision was calibrated against these budgets and works. Swapping in the
        # accurate per-line measure made it fire more often and cost two fixtures a page
        # each for no benefit: nothing was clipping there. Accuracy belongs where it
        # prevents clipping (the chunking below), not where it only shifts a page break.
        c = NOTES_HEADING_COST if legs_with_notes else 0
        for l in legs_with_notes:
            for n in notes_of(l):
                c += 2 + len(str(n)) // 60
        return c

    leg_rows = [(g, l) for g in groups for l in groups[g]]
    pages_of_legs, cur, used, last_g = [], [], 0, None
    budget = first_budget
    for g, l in leg_rows:
        cost = leg_cost(l) + (GROUP_COST if g != last_g else 0)
        if cur and used + cost > budget:
            pages_of_legs.append(cur)
            cur, used, last_g, budget = [], 0, None, CONT_BUDGET
            cost = leg_cost(l) + GROUP_COST
        cur.append((g, l)); used += cost; last_g = g
    if cur:
        pages_of_legs.append(cur)
    if not pages_of_legs:
        pages_of_legs = [[]]

    def rows_for(chunk, subtotals_for_completed_groups):
        out, last = [], None
        for gname, l in chunk:
            if gname != last:
                out.append(f"<tr class='group'><td colspan='8'>{e(gname)}</td></tr>"); last = gname
            out.append(row_html(l))
            if len(groups) > 1 and l is groups[gname][-1]:
                gsub = sum((x["pricing"]["line_total_cents"] or 0) for x in groups[gname])
                out.append(f"<tr class='gsub'><td colspan='7'>{e(gname)} subtotal</td><td class='num'>{money(gsub)}</td></tr>")
        return out

    if option is None:
        adj_rows = "".join(
            f"<tr><td>{e(a['label'])}{pct_suffix(a)}"
            f"{(' — '+e(next((l.get('ref') for l in q['legs'] if l['key']==a.get('applies_to')),''))) if a.get('applies_to') else ''}</td>"
            f"<td class='num'>{'−' if a['amount_cents']<0 else ''}{money(abs(a['amount_cents']))}</td></tr>"
            for a in q.get("adjustments", []) if not a.get("waived"))
        sub_cents, tot_cents, tot_label = q["engine_subtotal_cents"], q["total_cents"], "Estimated group total"
    else:
        # Option B: same global adjustments recomputed on this option's subtotal
        adj_rows, run = "", option["subtotal_cents"]
        if option.get("carried_refs"):
            adj_rows += (f"<tr><td class='cap'>Option B lines</td><td class='num cap'>{money(option['alt_subtotal_cents'])}</td></tr>"
                         f"<tr><td class='cap'>Unchanged from Option A ({e(', '.join(option['carried_refs']))})</td><td class='num cap'>{money(option['carried_subtotal_cents'])}</td></tr>")
        for a in q.get("adjustments", []):
            if a.get("applies_to") or a.get("waived"):
                continue
            amt = round(run * a["value"] / 100.0) if a["type"] == "percent" else round(a["value"] * 100)
            run += amt
            adj_rows += (f"<tr><td>{e(a['label'])}{pct_suffix(a)}</td>"
                         f"<td class='num'>{'−' if amt<0 else ''}{money(abs(amt))}</td></tr>")
        sub_cents, tot_cents, tot_label = option["subtotal_cents"], option["total_cents"], "Option B program total"

    # Per-leg rows kept separable, because on a 16-leg quote the notes are taller than a
    # page and used to be emitted as one block inside a fixed-height, overflow:hidden box:
    # A12 collided with the footer, A13 was cut across it, and A14-A16 were clipped away
    # entirely. The totals were right and every check passed -- pdftotext still extracts
    # clipped text -- so a client simply never saw those notes.
    note_rows = [(l, f"<tr><td class='ref'>{e(l.get('ref'))}</td>"
                     f"<td>{'<br>'.join(e(n) for n in notes_of(l))}</td></tr>")
                 for l in legs_in if notes_of(l)]
    notes = "".join(h for _, h in note_rows)
    notes_html = f"<h3>Line notes</h3><table class='notes'>{notes}</table>" if notes else ""
    intro = f"<p class='intro'>{e(pz['intro_note'])}</p>" if (option is None and pz.get("intro_note")) else ""
    # The commission, quietly, under the total it belongs to. The amount is COPIED from
    # quote.json (apply_adjustments.py computed it); this renderer works out nothing. A
    # quote with no per-option amount (hand-assembled) states the rate alone.
    def hero_comm(which):
        if not q.get("commission_pct"):
            return ""
        amt = (q.get("commission_amounts") or {}).get(which)
        txt = f"{float(q['commission_pct']):g}% commission" + (f" &middot; {money(amt)}" if amt is not None else "")
        return f"<div class='hero-comm'>{txt}</div>"
    primary_ref = ""
    if option is not None:
        pr = {l["key"]: l.get("ref") for l in q["legs"]}
        pairs = ", ".join(f"{l.get('ref')} replaces {pr.get(l.get('alternative_of'),'?')}" for l in legs_in)
        head = f"""<div class="head"><div class="head-l"><h2>Option B <span class='cap'>· alternative vehicle plan</span></h2>
      <div class='sub'>Same dates and routing as Option A; {e(pairs)}. Choose either option — totals are not additive.</div></div>
      <div class="hero"><label>Option B program total</label><div class="amt">{money(tot_cents)}</div>
      <div class="hero-sub">vs. Option A {money(q['total_cents'])}</div>{hero_comm('b')}</div></div>"""
    else:
        head = f"""<div class="head">
    <div class="head-l">
      <h2>{e(m.get('title'))}</h2>
      {f"<div class='sub'>{e(pz['event_name'])}</div>" if pz.get('event_name') else ''}
      <div class="meta">{meta_html}</div>
    </div>
    <div class="hero"><label>Estimated total{' · Option A' if q.get('option_b') else ''}</label><div class="amt">{money(q['total_cents'])}</div>
      <div class="hero-sub">{len(legs_in)} line item{'s' if len(legs_in)!=1 else ''} · all rates in USD{' · Option B on the next page' if q.get('option_b') else ''}</div>{hero_comm('a')}</div>
  </div>"""

    thead = "<thead><tr><th>Ref</th><th>Service</th><th class='num'>Basis</th><th class='num'>Min</th><th class='num'>Qty</th><th class='num'>Hrs / veh</th><th class='num'>Rate</th><th class='num'>Total</th></tr></thead>"
    footer = '<footer class="pf"><span>Savoya · Confidential · Group travel quote</span><span class="pn"></span></footer>'
    breakdown_html = f"""<table class="breakdown">
      <tr><td>Transportation subtotal</td><td class='num'>{money(sub_cents)}</td></tr>
      {adj_rows}
      <tr class='total'><td>{e(tot_label)}</td><td class='num'>{money(tot_cents)}</td></tr>
    </table>"""

    def split_block(rows_html, heading, with_breakdown):
        nh = (f"<h3>Line notes{'' if heading else ' · continued'}</h3>"
              f"<table class='notes'>{rows_html}</table>") if rows_html else ""
        return (f'<div class="split"><div>{nh}</div>'
                f'{breakdown_html if with_breakdown else ""}</div>')

    split = split_block(notes, True, True)
    out = []
    n = len(pages_of_legs)
    # the notes + breakdown block needs room: if the last page is more than half full, give it its own page
    # the notes + breakdown block needs room; give it its own page when it won't fit
    legs_with_notes = [l for l in legs_in if notes_of(l)]
    block_cost = notes_cost(legs_with_notes) + 12          # + the breakdown table
    last_used = sum(leg_cost(l) for _, l in pages_of_legs[-1]) + GROUP_COST * len({g for g, _ in pages_of_legs[-1]})
    room = (first_budget if n == 1 else CONT_BUDGET) - last_used
    summary_own_page = block_cost > room or FORCE_OWN_SUMMARY >= (1 if option is None else 2)
    for idx, chunk in enumerate(pages_of_legs):
        first, last = idx == 0, idx == n - 1
        table = f"<table class='lines'>{thead}<tbody>{''.join(rows_for(chunk, True))}</tbody></table>"
        out.append(f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>{e(bar_label)}{'' if first else ' · continued'}</span></header>
  {head if first else ''}
  {intro if first else ''}
  {table}
  {split if (last and not summary_own_page) else ''}
  {footer}
</section>""")
    if summary_own_page:
        # Paginate the notes instead of trusting them to fit. A note's cost is measured
        # the same way notes_cost does it, so the two cannot disagree.
        # Filling each page to the brim before starting the next leaves the last one
        # with whatever is left over: six legs of notes came out as a 71%-full page
        # followed by a 16%-full one, which reads as a mistake in a document a client
        # is looking at. The number of pages is fixed by the total either way, so
        # spread the notes evenly across the pages they need.
        costs = [note_cost(l) for l, _ in note_rows]
        total_cost = sum(costs)
        npages = max(1, -(-total_cost // NOTES_ROWS_BUDGET)) if NOTES_ROWS_BUDGET else 1
        target = total_cost / npages if npages else total_cost
        chunks, cur, used = [], [], 0
        for (l, html), c in zip(note_rows, costs):
            if cur and (used + c > NOTES_ROWS_BUDGET
                        or (len(chunks) < npages - 1 and used + c / 2 > target)):
                chunks.append(cur)
                cur, used = [], 0
            cur.append(html)
            used += c
        if cur:
            chunks.append(cur)
        if not chunks:
            chunks = [[]]

        for i, rows_html in enumerate(chunks):
            out.append(f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>{e(bar_label)} · summary{'' if i == 0 else ' · continued'}</span></header>
  {split_block("".join(rows_html), i == 0, i == 0)}
  {footer}
</section>""")
    return "".join(out)


def route_page(q):
    rm = q.get("route_map")
    if not rm or not os.path.exists(rm.get("png", "")):
        return ""
    import base64
    b64 = base64.b64encode(open(rm["png"], "rb").read()).decode()
    rows = []
    for l in q["legs"]:
        if l.get("alternative_of"):
            continue
        rt = l.get("route") or {}
        stops = " → ".join(f"<b>{s.get('marker','')}</b> {e(s['label'])}" if s.get("marker") else e(s["label"]) for s in l["stops"])
        rows.append(f"<tr><td class='ref'>{e(l.get('ref'))}</td><td>{day(l.get('date'))}<div class='route'>{stops}</div></td>"
                    f"<td class='num'>{str(rt.get('distance_mi')) + ' mi' if rt.get('distance_mi') else '—'}</td><td class='num'>{('~'+str(rt['drive_min'])+' min') if rt else '—'}</td></tr>")
    # paginate: the map takes roughly half the first page
    FIRST_R, CONT_R = 6, 16
    chunks, i = [], 0
    while i < len(rows):
        cap = FIRST_R if not chunks else CONT_R
        chunks.append(rows[i:i + cap]); i += cap
    if not chunks:
        chunks = [[]]
    thead = "<thead><tr><th>Ref</th><th>Route</th><th class='num'>Distance</th><th class='num'>Drive time</th></tr></thead>"
    # A schematic and a street map are different claims and must not look alike. The
    # offline overview shows stops in true relative position joined in order -- it is not
    # a driving route, and a client reading straight lines as roads is being misled by us,
    # not by the network that caused it. The only disclosure used to be the attribution
    # string tacked onto the end of this sentence, which nobody reads as a caveat.
    offline = rm.get("style") == "offline"
    map_title = "Itinerary overview" if offline else "Itinerary map"
    map_sub = ("stops in order — not a driving route" if offline
               else "numbered stops match the table")
    schematic = ("<b>This overview shows the stops in order and their positions relative to "
                 "one another; the connecting lines are not driving routes.</b> " if offline else "")
    legend = (f"<p class='legend'>{schematic}Drive times are typical-traffic estimates for planning; "
              f"garage-to-garage billing and wait time follow the terms. {e(rm.get('attribution',''))}.</p>")
    out = []
    for idx, chunk in enumerate(chunks):
        first, last = idx == 0, idx == len(chunks) - 1
        img = (f'<img src="data:image/png;base64,{b64}" style="width:100%;border:1px solid {RULE};'
               f'border-radius:8px;margin:10pt 0 14pt;">') if first else ""
        out.append(f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>Route overview{'' if first else ' · continued'}</span></header>
  {('<h2 class="rc">' + map_title + ' <span class="cap">· ' + map_sub + '</span></h2>') if first else ''}
  {img}
  <table class="lines small">{thead}<tbody>{''.join(chunk)}</tbody></table>
  {legend if last else ''}
  <footer class="pf"><span>Savoya · Confidential · Group travel quote</span><span class="pn"></span></footer>
</section>""")
    return "".join(out)


def ratecard_page(q):
    disc, sur = global_pct(q, True), global_pct(q, False)
    seen, rows, cx_rows = {}, [], []
    for l in q["legs"]:
        p, v = l["pricing"], l["vehicle"]
        k = (v["name"], p["method"], p["rate_cents"], p.get("special_event", {}) and p["special_event"].get("name"))
        if k in seen:
            continue
        seen[k] = True
        rate = p["rate_cents"] if p["method"] == "hourly" else p["per_vehicle_cents"]
        net = net_rate(rate, disc, sur)
        minimum = p.get("minimum_hours") if p["method"] == "hourly" else None
        min_total = rate * minimum if minimum else rate
        net_min = net_rate(min_total, disc, sur)
        _ev = p.get("special_event") or {}
        tag = (f" <span class='cap'>&middot; {e(_ev['name'])} event rate</span>"
               if _ev.get("name") else
               " <span class='cap'>&middot; event rate</span>" if _ev else "")
        rows.append(f"""<tr><td><b>{e(v['name'])}</b> <span class='cap'>({v.get('capacity')} pax)</span>{tag}</td>
          <td class='num'>{'Hourly' if p['method']=='hourly' else 'Transfer'}</td>
          <td class='num'><div>{money(rate)}</div><div class='net'>{money(net)}</div></td>
          <td class='num'>{hrs(minimum) if minimum else '—'}</td>
          <td class='num'><div>{money(min_total)}</div><div class='net'>{money(net_min)}</div></td>
          <td class='num'>{p.get('cancellation_hours')} hr</td></tr>""")
        cx_rows.append(f"<tr><td>{e(v['name'])} ({v.get('capacity')} pax)</td><td class='num'>{p.get('cancellation_hours')} hr</td><td class='num'>{hrs(minimum) if minimum else '—'}</td></tr>")
    legend = []
    if disc:
        legend.append(f"{abs(disc):g}% group discount")
    if sur:
        legend.append(f"{sur:g}% fuel surcharge")
    legend_txt = ("Upper figure is the standard rate. Lower figure is net of the " + " and ".join(legend) + ".") if legend else "Standard rates shown."
    terms = "".join(f"<li>{e(t)}</li>" for t in q.get("terms", []))
    am = (q.get("personalization") or {}).get("account_manager") or {}
    contact = ""
    if am.get("name"):
        bits = " · ".join(e(x) for x in [am.get("title"), am.get("email"), am.get("phone")] if x)
        contact = f"<div class='contact'><label>Your Savoya contact</label><b>{e(am['name'])}</b><span>{bits}</span></div>"
    closing = f"<p class='closing'>{e(q['personalization']['closing_note'])}</p>" if (q.get("personalization") or {}).get("closing_note") else ""

    return f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>Group rate card</span></header>
  <h2 class="rc">Rate card <span class="cap">· all rates in USD</span></h2>
  <p class="legend">{e(legend_txt)}</p>
  <table class="lines rc">
    <thead><tr><th>Vehicle</th><th class='num'>Basis</th><th class='num'>Rate</th><th class='num'>Minimum</th><th class='num'>Minimum total</th><th class='num'>Cancellation</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <div class="split">
    <div><h3>Cancellation policy &amp; minimums</h3>
      <table class="lines small"><thead><tr><th>Vehicle</th><th class='num'>Notice</th><th class='num'>Minimum</th></tr></thead><tbody>{''.join(cx_rows)}</tbody></table>
    </div>
    <div>{closing}{contact}</div>
  </div>
  <h3>Terms</h3>
  <ul class="terms">{terms}</ul>
  <footer class="pf"><span>Savoya · Confidential · Group travel quote</span><span class="pn"></span></footer>
</section>"""


CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
@page {{ size: Letter; margin: 0; }}

/* ---- on screen this file is the deliverable: show it as a stack of pages ---- */
@media screen {{
  body {{ background:#EDEAE6; padding:0 0 40px; }}
  .page {{ margin:0 auto 22px; box-shadow:0 2px 14px rgba(0,0,0,.16); }}
  .printbar {{
    position:sticky; top:0; z-index:99; background:#141414; color:#FAF8F5;
    padding:13px 20px; display:flex; gap:14px; align-items:center; justify-content:center;
    font-size:13.5px; border-bottom:3px solid {COPPER};
  }}
  .printbar b {{ color:{COPPER}; font-weight:600; letter-spacing:.04em; }}
  .printbar button {{
    font:inherit; color:#141414; background:{COPPER}; border:0; border-radius:7px;
    padding:6px 14px; cursor:pointer; font-weight:600;
  }}
  .printbar span.tip {{ color:#A09890; }}
}}
@media print {{
  .printbar {{ display:none !important; }}
  body {{ background:#fff; padding:0; }}
  .page {{ margin:0; box-shadow:none; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: DM Sans, Arial, Helvetica, sans-serif; color:{INK}; font-size:10.5pt; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:8.5in; height:11in; padding:.55in .6in .5in; position:relative; page-break-after:always; overflow:hidden; background:#fff; }}
.page:last-child {{ page-break-after:auto; }}
h1,h2,.amt {{ font-family: Georgia, Times New Roman, serif; font-weight:400; margin:0; }}
h2 {{ font-size:22pt; line-height:1.15; }}
h3 {{ font-size:9pt; letter-spacing:.14em; text-transform:uppercase; color:{COPPER}; margin:18pt 0 6pt; font-weight:600; }}
.cap {{ color:{MUTED}; font-weight:400; font-size:9pt; }}
.bar {{ display:flex; align-items:center; gap:16px; background:#141414; margin:-.55in -.6in 18pt; padding:14pt .6in; border-bottom:3px solid {COPPER}; }}
.bar span {{ color:{COPPER}; font-size:9pt; letter-spacing:.14em; text-transform:uppercase; }}
.head {{ display:flex; gap:24pt; align-items:flex-start; margin-bottom:14pt; }}
.head-l {{ flex:1; }}
.sub {{ color:{GRAY}; margin-top:3pt; }}
.meta {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8pt 16pt; margin-top:12pt; }}
.meta label {{ display:block; font-size:7.5pt; letter-spacing:.12em; text-transform:uppercase; color:{MUTED}; }}
.meta span {{ font-size:10pt; }}
.hero {{ background:#141414; color:#fff; border-radius:12px; padding:16pt 20pt; min-width:2.6in; border-top:3px solid {COPPER}; }}
.hero label {{ font-size:7.5pt; letter-spacing:.14em; text-transform:uppercase; color:{COPPER}; }}
.hero .amt {{ font-size:30pt; margin-top:4pt; }}
.hero-sub {{ font-size:8.5pt; color:#A09890; margin-top:4pt; }}
.hero-comm {{ display:inline-block; margin-top:9pt; padding:4pt 11pt; border:1.2pt solid {COPPER}; border-radius:999px; background:rgba(184,115,51,.18); color:#fff; font-size:10pt; font-weight:700; letter-spacing:.02em; }}
.intro {{ color:{GRAY}; line-height:1.55; margin:0 0 14pt; }}
table.lines {{ width:100%; border-collapse:collapse; }}
table.lines th {{ font-size:7.5pt; letter-spacing:.1em; text-transform:uppercase; color:{MUTED}; text-align:left; padding:6pt 6pt; border-top:2px solid {COPPER}; border-bottom:1px solid {RULE}; font-weight:600; }}
table.lines td {{ padding:8pt 6pt; border-bottom:1px solid {RULE}; vertical-align:top; }}
table.lines .num, table.breakdown .num {{ text-align:right; white-space:nowrap; }}
table.lines .ref {{ color:{COPPER}; font-weight:600; width:.4in; }}
table.lines .tot {{ font-weight:600; }}
table.lines tr.group td {{ background:{TINT}; font-weight:600; font-size:9.5pt; padding:6pt; }}
table.lines tr.gsub td {{ font-weight:600; background:#FBF8F5; }}
table.lines .route {{ color:{GRAY}; font-size:9pt; margin-top:3pt; }}
table.lines .ev {{ color:{AMBER}; font-size:8.5pt; margin-top:3pt; }}
table.lines .inl {{ color:{GRAY}; font-size:8.5pt; margin-top:2pt; }}
table.lines .tbd {{ color:{MUTED}; font-size:8.5pt; font-style:italic; margin-top:2pt; }}
table.lines .sourced {{ color:{COPPER}; font-size:8.5pt; margin-top:2pt; }}
table.lines.small td, table.lines.small th {{ padding:5pt 6pt; font-size:9.5pt; }}
table.lines.rc .net {{ color:{COPPER}; font-weight:600; }}
.split {{ display:grid; grid-template-columns:1.2fr 1fr; gap:24pt; margin-top:6pt; }}
table.notes {{ width:100%; border-collapse:collapse; font-size:9.5pt; }}
table.notes td {{ padding:5pt 6pt; border-bottom:1px solid {RULE}; vertical-align:top; color:{GRAY}; }}
table.notes .ref {{ color:{COPPER}; font-weight:600; width:.4in; }}
table.breakdown {{ width:100%; border-collapse:collapse; margin-top:20pt; align-self:start; }}
table.breakdown td {{ padding:5pt 6pt; color:{GRAY}; }}
table.breakdown tr.total td {{ border-top:2px solid {COPPER}; padding-top:8pt; color:{INK}; font-weight:700; font-size:11.5pt; }}
h2.rc {{ font-size:18pt; }}
.legend {{ color:{GRAY}; font-size:9.5pt; margin:4pt 0 12pt; }}
ul.terms {{ margin:0; padding-left:14pt; color:{GRAY}; font-size:8.5pt; line-height:1.5; }}
ul.terms li {{ margin-bottom:3pt; }}
.contact {{ border:1px solid {RULE}; border-left:3px solid {COPPER}; border-radius:8px; padding:10pt 12pt; margin-top:22pt; font-size:9.5pt; }}
.contact label {{ display:block; font-size:7.5pt; letter-spacing:.12em; text-transform:uppercase; color:{COPPER}; margin-bottom:3pt; }}
.contact b {{ display:block; font-size:11pt; }}
.contact span {{ color:{GRAY}; }}
.closing {{ color:{GRAY}; line-height:1.5; margin-top:22pt; }}
.pf {{ position:absolute; left:.6in; right:.6in; bottom:.4in; display:flex; justify-content:space-between; font-size:7.5pt; letter-spacing:.1em; text-transform:uppercase; color:{MUTED}; border-top:1px solid {RULE}; padding-top:6pt; }}
/* cover */
.cover {{ color:#fff; display:flex; flex-direction:column; padding:.6in .7in .55in; }}
.cover-top {{ display:flex; align-items:center; }}
.cover-mid {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
.eyebrow {{ font-size:9pt; letter-spacing:.3em; text-transform:uppercase; color:{COPPER}; margin-bottom:14pt; }}
.cover h1 {{ font-size:36pt; line-height:1.15; max-width:6.2in; }}
.cover-sub {{ font-size:14pt; color:#D8D2CB; margin-top:16pt; }}
.cover-sub b {{ color:#fff; font-weight:600; }}
.cover-tag {{ font-size:11pt; color:#A09890; margin-top:26pt; letter-spacing:.02em; }}
.cover-dates {{ font-size:11pt; color:#A09890; margin-top:6pt; }}
.cover-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12pt 20pt; margin:26pt 0 22pt; }}
.cover-grid div {{ border-top:1px solid rgba(184,115,51,.45); padding-top:8pt; }}
.cover-grid b {{ display:block; font-size:10.5pt; margin-bottom:3pt; }}
.cover-grid span {{ font-size:9pt; color:#A09890; line-height:1.45; }}
.cover-foot {{ display:flex; justify-content:space-between; font-size:9pt; color:#fff; background:linear-gradient(90deg,{COPPER},{COPPER_DARK}); margin:0 -.7in -.55in; padding:12pt .7in; }}
"""


def render_html(q, cover="custom", cover_pdf=None):
    """cover: 'custom' (generated), 'none', or 'asset' (rasterized marketing cover from cover_pdf)."""
    first = cover_page(q) if cover == "custom" else (cover_asset_page(cover_pdf) if cover == "asset" and cover_pdf else "")
    pages = first + quote_page(q) + option_page(q) + route_page(q) + ratecard_page(q)
    has_cover = cover != "none"
    total = pages.count('class="pn"') + (1 if has_cover else 0)
    n = 1 if has_cover else 0
    while '<span class="pn"></span>' in pages:
        n += 1
        pages = pages.replace('<span class="pn"></span>', f'<span>Page {n} of {total}</span>', 1)
    bar = ("<div class='printbar'>"
           "<b>To save this as a PDF:</b>"
           "<span id='how'>press Ctrl/&#8984;+P, then choose Save as PDF</span>"
           "<button onclick='window.print()'>Print / Save as PDF</button>"
           "<span class='tip'>set margins to <b>None</b> and turn off headers &amp; footers</span>"
           "</div>"
           "<script>(function(){var m=navigator.platform||'';var h=document.getElementById('how');"
           "if(/Mac/i.test(m)){h.innerHTML='press \\u2318+P, then open the PDF menu (bottom-left) and choose Save as PDF';}"
           "else if(/Win/i.test(m)){h.innerHTML='press Ctrl+P, then set Destination to Microsoft Print to PDF';}})();</script>")
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{e(q['meta'].get('title'))} — Savoya</title><style>{CSS}</style></head><body>{bar}{pages}</body></html>"


def to_pdf(html_path, pdf_path):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto("file://" + os.path.abspath(html_path), wait_until="load")
            try:
                pg.wait_for_load_state("networkidle", timeout=2500)  # web fonts; falls back to system fonts
            except Exception:
                pass
            pg.pdf(path=pdf_path, format="Letter", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            b.close()
        return "playwright"
    except Exception as ex:  # noqa
        if shutil.which("wkhtmltopdf"):
            subprocess.run(["wkhtmltopdf", "-q", "--page-size", "Letter", "-T", "0", "-B", "0", "-L", "0", "-R", "0",
                            "--enable-local-file-access", html_path, pdf_path], check=True)
            return "wkhtmltopdf"
        return None  # caller reports the degradation; the HTML is already on disk


def clipped_pages(html_path):
    """Page numbers whose content runs past the footer, measured in the real browser.

    Returns [] when no browser is available (the wkhtmltopdf fallback, a locked-down
    machine): the estimate then stands alone, as it always did.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from measure_pages import measure_html
        res = measure_html([("doc", html_path)])["doc"]
    except Exception:
        return []
    return [r["page"] for r in res if not r.get("blank") and (r.get("overflow_px") or 0) > 4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("pdf")
    ap.add_argument("--html", default=None)
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--cover", default=None, help="cover key from assets/covers/catalog.json, or 'custom'")
    ap.add_argument("--cover-file", default=None, help="user-uploaded cover (PDF or image); rasterized once for this quote")
    a = ap.parse_args()
    with open(a.quote, encoding="utf-8") as f:
        q = json.load(f)
    for l in q["legs"]:
        for s in l["stops"]:
            if s.get("needs_label"):
                print(f"WARNING: {l['key']} has unlabeled stop '{s['label']}'", file=sys.stderr)
    for p in q.get("internal", {}).get("placeholders", []):
        print("PLACEHOLDER: " + p, file=sys.stderr)
    html_path = a.html or (os.path.splitext(a.pdf)[0] + ".print.html")
    if a.no_cover:
        mode, cover_path, key = "none", None, "none"
    elif a.cover_file:
        import subprocess, tempfile
        src = a.cover_file
        if src.lower().endswith(".pdf"):
            if not shutil.which("pdftoppm"):
                sys.exit("Uploaded cover is a PDF but pdftoppm isn't installed on this machine "
                         "(brew install poppler). Ask the user for an image version, or pick a catalog cover.")
            stem = os.path.join(tempfile.gettempdir(), "savoya-uploaded-cover")
            subprocess.run(["pdftoppm", "-r", "170", "-png", "-singlefile", "-f", "1", "-l", "1", src, stem], check=True)
            try:
                from PIL import Image
                Image.open(stem + ".png").convert("RGB").save(stem + ".jpg", "JPEG", quality=84, optimize=True)
                src = stem + ".jpg"
            except ImportError:
                src = stem + ".png"  # larger, but works
        mode, cover_path, key = "asset", src, "uploaded"
    else:
        key, cover_path = cover_choice(q, a.cover)
        mode = "custom" if cover_path is None else "asset"
    global FORCE_OWN_SUMMARY
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(q, cover=mode, cover_pdf=cover_path))
    # Escalate only as far as needed: Option A's totals first, then Option B's as well.
    for level in (1, 2):
        if not clipped_pages(html_path):
            break
        FORCE_OWN_SUMMARY = level
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(render_html(q, cover=mode, cover_pdf=cover_path))
        print(f"NOTE: a totals block did not fit its page; layout level {level} applied", file=sys.stderr)
    eng = to_pdf(html_path, a.pdf)
    if eng is None:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import importlib
            pf = importlib.import_module("preflight_helpers")
            hint = pf.print_to_pdf_hint()
        except Exception:
            hint = "open it in your browser, then Print → Save as PDF"
        print("PDF output isn't set up on this computer.")
        print(f"Full document written as a web page: {html_path}")
        print(f"  → deliver that file and tell the user: {hint} — it produces the same document.")
        print("  → do NOT show install commands to the user; PDF setup is a one-time IT task (see SETUP.md).")
        sys.exit(3)
    print(f"Wrote {a.pdf} via {eng}, cover={key} (html: {html_path})")


if __name__ == "__main__":
    main()
