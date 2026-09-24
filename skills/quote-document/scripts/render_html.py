#!/usr/bin/env python3
"""Render quote.json as a client-facing HTML email (Savoya dark brand theme).

Usage: render_html.py quote.json out.html
Warnings about unlabeled stops or placeholders go to stderr.
"""
import datetime as dt
import html
import json
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

BG, CARD, BORDER = "#0F0F0F", "#1A1A1A", "#2A2A2A"
COPPER, COPPER_LIGHT, AMBER = "#B87333", "#D4956B", "#F59E0B"
WHITE, GRAY, MUTED = "#FAF8F5", "#A09890", "#6B6560"
SERIF = "Georgia, Times New Roman, serif"
SANS = "DM Sans, Arial, Helvetica, sans-serif"


def e(s):
    return html.escape(str(s)) if s is not None else ""


def money(cents):
    return f"${(cents or 0)/100:,.2f}"


def fmt_date(iso):
    if not iso:
        return ""
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.strftime("%A, %B %-d, %Y · %-I:%M %p")
    except ValueError:
        return iso


def fmt_day(iso):
    try:
        return dt.date.fromisoformat(iso).strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        return iso or ""


def hours_txt(h):
    if h is None:
        return ""
    return f"{h:g} hour" + ("" if h == 1 else "s")


def leg_card(leg):
    p = leg["pricing"]
    v = leg["vehicle"]
    rows = []
    for i, s in enumerate(leg["stops"]):
        marker = "●" if i in (0, len(leg["stops"]) - 1) else "◆"
        line = f"<span style='color:{COPPER};'>{marker}</span>&nbsp; <span style='color:{WHITE};'>{e(s['label'])}</span>"
        if s.get("address"):
            line += f" <span style='color:{MUTED};'>· {e(s['address'])}</span>"
        if s.get("kind") == "airport" and s.get("flight", {}).get("tbd"):
            line += f" <span style='color:{AMBER};font-size:11px;'>&#9432; Flight details to be confirmed</span>"
        if s.get("wait_hours"):
            line += f"<br><span style='color:{MUTED};font-size:12px;padding-left:18px;'>{'As directed — ' if s.get('as_directed') else 'Wait on site — approx. '}{hours_txt(s['wait_hours'])}</span>"
        rows.append(f"<tr><td style='padding:4px 0;font-size:13px;line-height:1.5;color:{GRAY};font-family:{SANS};'>{line}</td></tr>")
    stops_html = "".join(rows)

    veh = f"{v['quantity']} × {e(v['name'])}" + (f" ({v['capacity']} passengers each)" if v.get("capacity") else "")
    pax = f"{leg['passenger_count']} passengers" if leg.get("passenger_count") else ""

    if p["method"] == "hourly":
        basis = f"{hours_txt(p['billable_hours'])} × {money(p['rate_cents'])}/hr"
        if p.get("minimum_hours"):
            basis += f" ({p['minimum_hours']:g}-hour minimum)"
        if v["quantity"] > 1:
            basis += f" · {money(p['per_vehicle_cents'])} per vehicle"
    else:
        basis = f"Transfer · {money(p['per_vehicle_cents'])}" + (" per vehicle" if v["quantity"] > 1 else "")

    cancel = f"Cancellation: {p['cancellation_hours']} hours' notice" if p.get("cancellation_hours") is not None else ""

    callout = ""
    if p.get("special_event"):
        callout = (f"<tr><td style='padding:10px 0 0;'><table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
                   f"<td style='background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px 12px;"
                   f"font-family:{SANS};font-size:12px;color:{AMBER};'>&#9888;&nbsp; Event pricing in effect for {e(p['special_event']['name'])}"
                   + (f": {p['minimum_hours']:g}-hour minimum" if p.get("minimum_hours") else "")
                   + (f", {p['cancellation_hours']}-hour cancellation" if p.get("cancellation_hours") else "")
                   + ".</td></tr></table></td></tr>")

    notes = ""
    if notes_of(leg):
        items = "".join(f"<div style='padding:2px 0;'><span style='color:{COPPER};'>&#9679;</span>&nbsp; {e(n)}</div>" for n in notes_of(leg))
        notes = f"<tr><td style='padding:10px 0 0;font-family:{SANS};font-size:12px;color:{GRAY};'>{items}</td></tr>"

    opt_badge = ""
    if leg.get("alternative_of"):
        opt_badge = f"<span style='font-family:{SANS};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER_LIGHT};'>Option</span><br>"

    return f"""
<tr><td style="padding:0 0 24px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};border:1px solid {BORDER};border-radius:14px;">
<tr><td style="padding:20px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td style="font-family:{SANS};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER};padding-bottom:6px;">{opt_badge}{e(fmt_date(leg.get('date')))}</td></tr>
    <tr><td style="font-family:{SERIF};font-size:20px;color:{WHITE};padding-bottom:12px;">{e(leg['label'])}</td></tr>
    {stops_html}
    <tr><td style="padding-top:12px;font-family:{SANS};font-size:13px;color:{GRAY};">{e(pax)}{' · ' if pax else ''}{veh}</td></tr>
    <tr><td style="padding-top:4px;font-family:{SANS};font-size:13px;color:{GRAY};">{basis}</td></tr>
    <tr><td style="padding-top:4px;font-family:{SANS};font-size:12px;color:{MUTED};">{e(cancel)}</td></tr>
    {callout}
    {notes}
    <tr><td style="padding-top:14px;border-top:1px solid {BORDER};margin-top:14px;" align="right">
      <span style="font-family:{SANS};font-size:11px;color:{MUTED};">Leg total&nbsp;&nbsp;</span>
      <span style="font-family:{SERIF};font-size:22px;color:{WHITE};">{money(p['line_total_cents'])}</span>
    </td></tr>
  </table>
</td></tr></table>
</td></tr>"""


def totals_card(q):
    rows = [f"<tr><td style='font-family:{SANS};font-size:13px;color:{GRAY};padding:4px 0;'>Transportation subtotal</td>"
            f"<td align='right' style='font-family:{SANS};font-size:13px;color:{WHITE};padding:4px 0;'>{money(q['engine_subtotal_cents'])}</td></tr>"]
    for a in q.get("adjustments", []):
        if a.get("waived"):
            continue
        label = a["label"]
        if a["type"] == "percent":
            label += f" ({a['value']:g}%)"
        amt = a["amount_cents"]
        txt = ("−" if amt < 0 else "") + money(abs(amt))
        rows.append(f"<tr><td style='font-family:{SANS};font-size:13px;color:{GRAY};padding:4px 0;'>{e(label)}</td>"
                    f"<td align='right' style='font-family:{SANS};font-size:13px;color:{WHITE};padding:4px 0;'>{txt}</td></tr>")
    rows.append(f"<tr><td colspan='2' style='padding-top:10px;'><table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
                f"<td style='height:1px;background:linear-gradient(90deg,{COPPER},transparent);font-size:1px;line-height:1px;'>&nbsp;</td></tr></table></td></tr>")
    rows.append(f"<tr><td style='font-family:{SANS};font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER};padding-top:10px;'>Total{' · Option A' if q.get('option_b') else ''}</td>"
                f"<td align='right' style='font-family:{SERIF};font-size:30px;color:{WHITE};padding-top:6px;'>{money(q['total_cents'])}</td></tr>")
    return f"""
<tr><td style="padding:0 0 24px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};border:1px solid rgba(184,115,51,0.2);border-radius:14px;">
<tr><td style="padding:20px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{''.join(rows)}</table></td></tr>
</table></td></tr>"""


def render(q):
    m, pz = q["meta"], q.get("personalization", {})
    warn = []
    for leg in q["legs"]:
        for s in leg["stops"]:
            if s.get("needs_label"):
                warn.append(f"{leg['key']}: unlabeled stop '{s['label']}'")
    for p in q.get("internal", {}).get("placeholders", []):
        warn.append(p)
    for w in warn:
        print("WARNING: " + w, file=sys.stderr)

    header_right = (f"<td align='right'><img src='{e(pz['client_logo_url'])}' height='32' alt='' style='display:block;height:32px;'></td>"
                    if pz.get("client_logo_url") else "")
    cover = (f"<tr><td style='padding:0 0 24px;'><img src='{e(pz['cover_image_url'])}' width='600' alt='' style='display:block;width:100%;max-width:600px;border-radius:14px;'></td></tr>"
             if pz.get("cover_image_url") else "")
    subtitle_bits = [x for x in [pz.get("event_name"), m.get("client")] if x]
    intro = (f"<tr><td style='padding:0 0 24px;font-family:{SANS};font-size:14px;line-height:1.6;color:{GRAY};'>{e(pz['intro_note'])}</td></tr>"
             if pz.get("intro_note") else "")
    quote_block = ""
    if pz.get("pull_quote"):
        quote_block = (f"<tr><td style='padding:0 0 24px;'><table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
                       f"<td style='border-left:3px solid {COPPER};padding:6px 16px;font-family:{SERIF};font-size:17px;line-height:1.5;color:{WHITE};font-style:italic;'>"
                       f"&ldquo;{e(pz['pull_quote'])}&rdquo;"
                       + (f"<div style='font-family:{SANS};font-size:12px;color:{MUTED};font-style:normal;padding-top:6px;'>— {e(pz['pull_quote_attribution'])}</div>" if pz.get("pull_quote_attribution") else "")
                       + "</td></tr></table></td></tr>")
    am = pz.get("account_manager") or {}
    contact = ""
    if am.get("name"):
        lines = [x for x in [am.get("title"), am.get("email"), am.get("phone")] if x]
        contact = (f"<tr><td style='padding:0 0 24px;'><table role='presentation' cellpadding='0' cellspacing='0' style='background:{CARD};border:1px solid {BORDER};border-radius:12px;'>"
                   f"<tr><td style='padding:14px 18px;font-family:{SANS};font-size:13px;color:{GRAY};'>"
                   f"<div style='font-family:{SANS};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER};padding-bottom:4px;'>Your Savoya contact</div>"
                   f"<div style='color:{WHITE};font-size:15px;'>{e(am['name'])}</div>"
                   + "".join(f"<div>{e(x)}</div>" for x in lines) + "</td></tr></table></td></tr>")
    closing = (f"<tr><td style='padding:0 0 24px;font-family:{SANS};font-size:14px;line-height:1.6;color:{GRAY};'>{e(pz['closing_note'])}</td></tr>"
               if pz.get("closing_note") else "")
    terms = "".join(f"<div style='padding:3px 0;'><span style='color:{COPPER};'>&#9679;</span>&nbsp; {e(t)}</div>" for t in q.get("terms", []))

    primaries = [l for l in q["legs"] if not l.get("alternative_of")]
    alts = [l for l in q["legs"] if l.get("alternative_of")]
    legs_html = "".join(leg_card(l) for l in primaries)
    option_html = ""
    if alts and q.get("option_b"):
        ob = q["option_b"]
        option_html = (f"<tr><td style='padding:8px 0 12px;font-family:{SANS};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER};'>Option B — alternative vehicle plan</td></tr>"
                       f"<tr><td style='padding:0 0 16px;font-family:{SANS};font-size:13px;color:{GRAY};'>Same dates and routing. Choose either option — totals are not additive.</td></tr>"
                       + "".join(leg_card(l) for l in alts)
                       + f"<tr><td style='padding:0 0 24px;' align='right'><span style='font-family:{SANS};font-size:11px;color:{MUTED};'>Option B program total&nbsp;&nbsp;</span>"
                         f"<span style='font-family:{SERIF};font-size:24px;color:{WHITE};'>{money(ob['total_cents'])}</span></td></tr>")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(m.get('title'))} — Savoya</title>
<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');</style>
</head>
<body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="padding:40px 24px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">

<tr><td style="padding:0 0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
  <td><img src="{LOGO}" width="142" height="32" alt="Savoya" style="display:block;width:142px;height:32px;"></td>{header_right}
</tr></table></td></tr>

{cover}

<tr><td style="font-family:{SERIF};font-size:34px;line-height:1.2;color:{WHITE};padding-bottom:6px;">{e(m.get('title'))}</td></tr>
<tr><td style="font-family:{SANS};font-size:15px;color:{GRAY};padding-bottom:20px;">{e(' · '.join(subtitle_bits))}</td></tr>

<tr><td style="padding:0 0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};border:1px solid {BORDER};border-radius:12px;"><tr>
  <td style="padding:14px 18px;font-family:{SANS};font-size:12px;color:{GRAY};line-height:1.7;">
    <span style="color:{MUTED};">Prepared for</span> <span style="color:{WHITE};">{e(m.get('client'))}</span>
    {('&nbsp;&nbsp;·&nbsp;&nbsp;<span style="color:' + MUTED + ';">Prepared by</span> <span style="color:' + WHITE + ';">' + e(m.get('prepared_by')) + '</span>') if m.get('prepared_by') else ''}
    <br><span style="color:{MUTED};">Date</span> <span style="color:{WHITE};">{e(fmt_day(m.get('prepared_on')))}</span>
    &nbsp;&nbsp;·&nbsp;&nbsp;<span style="color:{MUTED};">Valid until</span> <span style="color:{WHITE};">{e(fmt_day(m.get('valid_until')))}</span>
  </td></tr></table></td></tr>

{intro}
{legs_html}
{quote_block}
{totals_card(q)}
{option_html}
{closing}
{contact}

<tr><td style="padding:16px 0 32px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
  <td style="height:1px;background:linear-gradient(90deg,transparent,rgba(184,115,51,0.25),transparent);font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td></tr>

<tr><td style="font-family:{SANS};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:{COPPER};padding-bottom:8px;">Terms</td></tr>
<tr><td style="font-family:{SANS};font-size:12px;line-height:1.6;color:{MUTED};padding-bottom:40px;">{terms}</td></tr>

<tr><td style="font-family:{SANS};font-size:12px;color:{MUTED};font-style:italic;padding-bottom:40px;">Savoya · Corporate ground transportation</td></tr>

</table></td></tr></table></td></tr></table>
</body></html>"""


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: render_html.py quote.json out.html")
    with open(sys.argv[1], encoding="utf-8") as f:
        q = json.load(f)
    out = render(q)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()
