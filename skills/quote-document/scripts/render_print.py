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


def quote_page(q):
    m, pz = q["meta"], q.get("personalization", {})
    disc, sur = global_pct(q, True), global_pct(q, False)
    meta_cells = [
        ("Prepared for", m.get("client")),
        ("Prepared by", m.get("prepared_by")),
        ("Travel coordinator", m.get("travel_coordinator")),
        ("Service area", m.get("service_area")),
        ("Passengers", str(max((l.get("passenger_count") or 0) for l in q["legs"])) if q["legs"] else None),
        ("Date", day(m.get("prepared_on"), "%m/%d/%Y")),
        ("Valid until", day(m.get("valid_until"), "%m/%d/%Y")),
        ("Discount", f"{abs(disc):g}%" if disc else None),
        ("Fuel surcharge", f"{sur:g}%" if sur else None),
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
    # group legs by date
    groups = {}
    for l in legs_in:
        groups.setdefault(day(l.get("date"), "%A — %m/%d/%Y") or "Date to be confirmed", []).append(l)

    def row_html(l):
            p, v = l["pricing"], l["vehicle"]
            route = " → ".join(e(s["label"]) for s in l["stops"])
            when = time_of(l.get("date"))
            basis = "Hourly" if p["method"] == "hourly" else "Transfer"
            ev = f"<div class='ev'>&#9888; Event pricing — {e(p['special_event']['name'])}</div>" if p.get("special_event") else ""
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
            return f"""<tr>
  <td class='ref'>{e(l.get('ref'))}</td>
  <td class='svc'><b>{e(v['name'])}</b> <span class='cap'>({v.get('capacity')} pax)</span>
      <div class='route'>{when}{' · ' if when else ''}{route}{drive}</div>{ev}{tbd}</td>
  <td class='num'>{e(basis)}</td>
  <td class='num'>{hrs(p.get('minimum_hours')) if p['method']=='hourly' else '—'}</td>
  <td class='num'>{v['quantity']}</td>
  <td class='num'>{hrs(p.get('billable_hours')) if p['method']=='hourly' else '—'}</td>
  <td class='num'>{money(p['rate_cents']) if p['method']=='hourly' else money(p['per_vehicle_cents'])}</td>
  <td class='num tot'>{money(p['line_total_cents'])}</td></tr>"""

    # --- pagination by estimated height, not leg count. A leg with three long client_notes
    # occupies several times the space of a bare one; counting legs clipped real quotes.
    FIRST_BUDGET, CONT_BUDGET = 54, 64      # units calibrated against the fixture renders
    GROUP_COST = 4                          # a date header + its subtotal row
    ROUTE_CHARS = 48                        # chars per wrapped line in the 9pt .svc column
    INTRO_CHARS = 95                        # chars per wrapped line in the full-width intro

    # The intro note sits ABOVE the table on the first page, so it spends part of that
    # page's budget. FIRST_BUDGET used to be a flat constant, so an intro note longer than
    # about two lines pushed the table down while the budget still believed it had the
    # whole page: the last rows were cut by the page break and the text ran into the
    # footer. The note is written by the user at question 4, so its length is not bounded.
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
        stops = l.get("stops") or []
        by_stops = 2 * max(0, len(stops) - 2)
        route_chars = sum(len(str(s.get("label") or "")) + 3 for s in stops)
        by_chars = 2 * max(0, -(-route_chars // ROUTE_CHARS) - 1)
        c += max(by_stops, by_chars)
        if (l.get("pricing") or {}).get("special_event"):
            c += 2
        if any(s.get("kind") == "airport" and (s.get("flight") or {}).get("tbd") for s in (l.get("stops") or [])):
            c += 1
        return c

    def notes_cost(legs_with_notes):
        c = 4 if legs_with_notes else 0     # the "Line notes" heading
        for l in legs_with_notes:
            for n in notes_of(l):
                c += 2 + len(str(n)) // 60  # notes wrap hard in a narrow column
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
            f"<tr><td>{e(a['label'])}{(' ('+format(abs(a['value']),'g')+'%)') if a['type']=='percent' else ''}"
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
            adj_rows += (f"<tr><td>{e(a['label'])}{(' ('+format(abs(a['value']),'g')+'%)') if a['type']=='percent' else ''}</td>"
                         f"<td class='num'>{'−' if amt<0 else ''}{money(abs(amt))}</td></tr>")
        sub_cents, tot_cents, tot_label = option["subtotal_cents"], option["total_cents"], "Option B program total"

    notes = "".join(f"<tr><td class='ref'>{e(l.get('ref'))}</td><td>{'<br>'.join(e(n) for n in notes_of(l))}</td></tr>"
                    for l in legs_in if notes_of(l))
    notes_html = f"<h3>Line notes</h3><table class='notes'>{notes}</table>" if notes else ""
    intro = f"<p class='intro'>{e(pz['intro_note'])}</p>" if (option is None and pz.get("intro_note")) else ""
    primary_ref = ""
    if option is not None:
        pr = {l["key"]: l.get("ref") for l in q["legs"]}
        pairs = ", ".join(f"{l.get('ref')} replaces {pr.get(l.get('alternative_of'),'?')}" for l in legs_in)
        head = f"""<div class="head"><div class="head-l"><h2>Option B <span class='cap'>· alternative vehicle plan</span></h2>
      <div class='sub'>Same dates and routing as Option A; {e(pairs)}. Choose either option — totals are not additive.</div></div>
      <div class="hero"><label>Option B program total</label><div class="amt">{money(tot_cents)}</div>
      <div class="hero-sub">vs. Option A {money(q['total_cents'])}</div></div></div>"""
    else:
        head = f"""<div class="head">
    <div class="head-l">
      <h2>{e(m.get('title'))}</h2>
      {f"<div class='sub'>{e(pz['event_name'])}</div>" if pz.get('event_name') else ''}
      <div class="meta">{meta_html}</div>
    </div>
    <div class="hero"><label>Estimated total{' · Option A' if q.get('option_b') else ''}</label><div class="amt">{money(q['total_cents'])}</div>
      <div class="hero-sub">{len(legs_in)} line item{'s' if len(legs_in)!=1 else ''} · all rates in USD{' · Option B on the next page' if q.get('option_b') else ''}</div></div>
  </div>"""

    thead = "<thead><tr><th>Ref</th><th>Service</th><th class='num'>Basis</th><th class='num'>Min</th><th class='num'>Qty</th><th class='num'>Hrs / veh</th><th class='num'>Rate</th><th class='num'>Total</th></tr></thead>"
    footer = '<footer class="pf"><span>Savoya · Confidential · Group travel quote</span><span class="pn"></span></footer>'
    split = f"""<div class="split">
    <div>{notes_html}</div>
    <table class="breakdown">
      <tr><td>Transportation subtotal</td><td class='num'>{money(sub_cents)}</td></tr>
      {adj_rows}
      <tr class='total'><td>{e(tot_label)}</td><td class='num'>{money(tot_cents)}</td></tr>
    </table>
  </div>"""
    out = []
    n = len(pages_of_legs)
    # the notes + breakdown block needs room: if the last page is more than half full, give it its own page
    # the notes + breakdown block needs room; give it its own page when it won't fit
    legs_with_notes = [l for l in legs_in if notes_of(l)]
    block_cost = notes_cost(legs_with_notes) + 12          # + the breakdown table
    last_used = sum(leg_cost(l) for _, l in pages_of_legs[-1]) + GROUP_COST * len({g for g, _ in pages_of_legs[-1]})
    room = (first_budget if n == 1 else CONT_BUDGET) - last_used
    summary_own_page = block_cost > room
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
        out.append(f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>{e(bar_label)} · summary</span></header>
  {split}
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
    legend = (f"<p class='legend'>Drive times are typical-traffic estimates for planning; garage-to-garage billing "
              f"and wait time follow the terms. {e(rm.get('attribution',''))}.</p>")
    out = []
    for idx, chunk in enumerate(chunks):
        first, last = idx == 0, idx == len(chunks) - 1
        img = (f'<img src="data:image/png;base64,{b64}" style="width:100%;border:1px solid {RULE};'
               f'border-radius:8px;margin:10pt 0 14pt;">') if first else ""
        out.append(f"""
<section class="page">
  <header class="bar"><img src="{LOGO}" style="height:26px;"><span>Route overview{'' if first else ' · continued'}</span></header>
  {'<h2 class="rc">Itinerary map <span class="cap">· numbered stops match the table</span></h2>' if first else ''}
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
        tag = f" <span class='cap'>· {e(p['special_event']['name'])} event rate</span>" if p.get("special_event") else ""
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
table.lines .tbd {{ color:{MUTED}; font-size:8.5pt; font-style:italic; margin-top:2pt; }}
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
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(q, cover=mode, cover_pdf=cover_path))
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
