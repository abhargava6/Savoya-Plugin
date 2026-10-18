#!/usr/bin/env python3
"""Produce the house-style quote email (subject + body) for the user to copy into their own mail client.

Usage: draft_email.py quote.json [--to client@x.com] [--attachment boston.pdf] [--json out.json]
Prints subject/body; --json also writes {"to","subject","body","attachment"} for reference. The skill posts this text in the chat — it does not create drafts or attach files.
The body is deliberately short — the PDF carries the detail.
"""
import argparse, datetime as dt, json, sys

def money(c): return f"${(c or 0)/100:,.2f}"
def day(iso, fmt="%A, %B %-d"):
    try: return dt.datetime.fromisoformat(iso).strftime(fmt)
    except (ValueError, TypeError): return iso or ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote"); ap.add_argument("--to", default=None)
    ap.add_argument("--short", action="store_true"); ap.add_argument("--attachment", default=None); ap.add_argument("--json", default=None)
    ap.add_argument("--asked", action="store_true", help="the user asked for an email even though the recorded format is PDF-only")
    a = ap.parse_args()
    from deliverables import chosen_format, EMAIL_FORMATS
    fmt = chosen_format(a.quote)
    if fmt and fmt not in EMAIL_FORMATS and not a.asked:
        sys.exit(f"The user chose {fmt!r}, not an email. Do not draft or paste one (R85); offer it in one line. "
                 "If they have since asked for one, re-run with --asked.")
    q = json.load(open(a.quote, encoding="utf-8"))
    m, pz = q["meta"], q.get("personalization", {})
    am = pz.get("account_manager") or {}
    event = pz.get("event_name") or m.get("title")
    iso = sorted({l["date"][:10] for l in q["legs"] if l.get("date")})
    dates = [day(d, "%b %-d") for d in iso]
    date_txt = (" – ".join([dates[0], dates[-1]]) if len(dates) > 1 else (dates[0] if dates else ""))
    if event and any(x in event for x in ("20", "June", "Jun", "Sept", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jul", "Aug")):
        date_txt = ""  # event name already carries the dates
    primaries = [l for l in q["legs"] if not l.get("alternative_of")]
    alts = [l for l in q["legs"] if l.get("alternative_of")]
    def route_of(l, join=" → "):
        stops = l.get("stops") or []
        labels = [s.get("label") or s.get("address") or "" for s in stops]
        if len(labels) >= 2 and labels[0] == labels[-1]:
            return labels[0] + " (round trip" + (", " + labels[1] if len(labels) > 2 else "") + ")"
        return join.join(labels)

    def line(l):
        return f"  • {l.get('ref','')} {day(l.get('date'),'%a %-m/%-d')} — {l['vehicle']['quantity']} × {l['vehicle']['name']}, {route_of(l)}"
    legs_txt = "\n".join(line(l) for l in primaries)
    if alts:
        legs_txt += "\n  Option B swaps " + "; ".join(f"{l.get('ref')} for {next((p.get('ref') for p in primaries if p['key']==l.get('alternative_of')),'?')} ({l['vehicle']['quantity']} × {l['vehicle']['name']}, {l['pricing'].get('billable_hours') or ''} hrs)" for l in alts)
    # Asked for ONLY when a flight is actually outstanding: an airport stop whose flight is
    # TBD. This used to key off ANY placeholder, so a 9:00 AM pickup placeholder on a coach
    # hire with no flights made the email ask the client to "send over the flight details"
    # (Yerdle, 15 Oct 2026; PRD R74).
    flight_tbd = any(s.get("kind") == "airport" and (s.get("flight") or {}).get("tbd") and not l.get("flight_supplied")
                     for l in q["legs"] for s in (l.get("stops") or []))
    subject = f"Savoya quote — {event}" + (f" ({date_txt})" if date_txt else "")
    tc = (m.get("travel_coordinator") or "").split(" (")[0].split()[0] if m.get("travel_coordinator") else None
    greet = f"Hi {tc}," if tc else "Hi there,"
    title = (am.get("title") or "").lower()
    register = "sales" if "sales" in title or "vp" in title else "csm"
    ob = q.get("option_b")
    primaries = [l for l in q["legs"] if not l.get("alternative_of")]
    alts = [l for l in q["legs"] if l.get("alternative_of")]
    # Every negative percent adjustment, SUMMED — not multiplied. Core adds discounts in
    # basis points (3000 + 500 -> effective 3500), so a product of factors is a different
    # and larger number. See `net_of` below for what this cost.
    discs = [a for a in q.get("adjustments", [])
             if a["type"] == "percent" and a["value"] < 0
             and not a.get("applies_to") and not a.get("waived")]
    disc_pct = sum(a["value"] for a in discs)
    disc = dict(discs[0], value=disc_pct) if discs else None
    fuel = next((a for a in q.get("adjustments", []) if "fuel" in a["label"].lower() and not a.get("waived")), None)

    def net_of(l, cents_key, units=1):
        """Core's own net figure, divided only by Core's own unit count.

        This used to build one multiplicative factor over every percent adjustment and
        apply it to the STANDARD rate. With a single discount that happens to agree with
        Core exactly (0.70 x 1.10 = 0.77 either way), so it looked right for months. With
        two it does not: 0.70 x 0.95 = 0.665 against Core's additive 0.65. On a real
        16-leg World Cup quote every one of the 16 lines came out high and the email
        totalled $26,145.63 against the $25,556 the PDF and Savoya showed — $589.72 of
        invented money, in the document the CSM pastes to the client.

        The PDF never had the bug because render_print sums the percentages. The fix here
        is stronger than summing: take the line total Core returned and divide by the
        hours or vehicles Core billed. The plugin states no price Core did not return.
        """
        net = l.get("engine_net_line_cents")
        if net is None:                      # pre-0.23 quote.json, no engine fields
            return None
        return int(round(net / units)) if units else net

    def line_net(l):
        return net_of(l, "engine_net_line_cents")

    def unit_net(l):
        """Per-vehicle (transfer) or per-hour (hourly) net, from Core's granularity."""
        qty = (l.get("vehicle") or {}).get("quantity") or 1
        units = qty * (l.get("engine_rate_units") or 1)
        return net_of(l, "engine_net_line_cents", units)

    def block(l, n=None, prefix=""):
        p, v = l["pricing"], l["vehicle"]
        # Day, CLOCK TIME, route and headcount — the four things a CSM adds by hand
        # otherwise. On a live Irvine quote every heading in the draft was rewritten
        # before sending, because this said only "A1 – Saturday, March 20 – 2 × Mini
        # Bus": no pickup time, and the route only when the leg's label happened to be
        # under 60 characters. The PDF has carried all of it for months; the email is
        # the copy the client actually reads first.
        when = day(l.get("date"), "%A, %B %-d")
        clock = day(l.get("date"), "%-I:%M%p").lower()
        route = route_of(l, " to ")
        pax = l.get("passenger_count")
        if l.get("airport_target") and clock:
            from datetime import datetime as _d
            try:
                clock = f"{clock} pickup, airport arrival {_d.strptime(l['airport_target'], '%H:%M').strftime('%-I:%M%p').lower()}"
            except ValueError:
                pass
        hdr = (f"{prefix}{l.get('ref','')} – {when}"
               + (f", {clock}" if clock and clock != when else "")
               + (f" – {route}" if route else "")
               + (f" – flight {l['flight_supplied']}" if l.get("flight_supplied") else "")
               + (f" ({pax} guests)" if pax else "")
               + f" – {v['quantity']} × {v['name']}")
        lines = [hdr, f"Vehicle type: {v['name']} (max capacity: {v.get('capacity')} passengers)"]
        # R51: say why the same vehicle type appears as two separate lines.
        if l.get("sourced_from_other_market") and l.get("service_area"):
            lines.append(f"Positioned from our {l['service_area']} partners — "
                         f"additional drive time included in the rate")
        cx = p.get("cancellation_hours")
        if cx:
            lines.append(f"Cancellation policy*: {cx} hours" + (" (1 week)" if cx == 168 else " (72 hours = 3 days)" if cx == 72 else ""))
        per_unit, net_line = unit_net(l), line_net(l)
        if per_unit is None or net_line is None:
            sys.exit(f"{l.get('ref') or l.get('key')}: quote.json carries no engine_net_line_cents, "
                     f"so the email cannot state a net price Core returned. Re-run normalize_quote.py.")
        if p["method"] == "hourly":
            if p.get("minimum_hours"): lines.append(f"Minimum hours: {p['minimum_hours']:g} hours")
            lines.append(f"Quoted time: {p.get('billable_hours'):g} hours" + (" per vehicle" if v["quantity"] > 1 else ""))
            lines.append(f"Adjusted Client Hourly Rate: {money(per_unit)}")
        else:
            lines.append(f"Type: Transfer – {money(per_unit)}" + (" per vehicle" if v["quantity"] > 1 else ""))
        if p.get("special_event") and p["special_event"].get("name"):
            lines.append(f"Special event: {p['special_event']['name']} rates are in effect on this date and availability is limited.")
        elif p.get("special_event"):
            lines.append("Special event rates and minimums are in effect on this date and availability is limited.")
        if v["quantity"] > 1:
            lines.append(f"Estimated Total for 1 {v['name']}: {money(per_unit * (l.get('engine_rate_units') or 1))}")
        lines.append(f"Estimated Total: {money(net_line)}")
        return "\n".join(lines)

    blocks = "\n\n".join(block(l) for l in primaries)
    if alts:
        # One entry per REPLACED leg, not per alternative. Two alternatives standing in
        # for the same primary leg used to name it twice: a live Irvine quote where 12
        # SUVs and a Sprinter together replaced one Mini Bus run produced "Option B (in
        # place of A1, A1, A2)", and the CSM rewrote the heading by hand before sending.
        replaced_refs = []
        for l in alts:
            ref = next((p.get("ref") for p in primaries
                        if p["key"] == l.get("alternative_of")), "?")
            if ref not in replaced_refs:
                replaced_refs.append(ref)
        blocks += ("\n\nOption B (in place of " + ", ".join(replaced_refs) + "):\n"
                   + "\n\n".join(block(l) for l in alts))
    cxs = sorted({l["pricing"].get("cancellation_hours") for l in q["legs"] if l["pricing"].get("cancellation_hours")})
    cx_note = ""
    if cxs:
        cx_txt = " & ".join(str(c) for c in cxs)
        cx_note = (f"*Please note, {'these cancellation policies mean these trips are' if len(cxs)>1 else 'this cancellation policy means this reservation is'} "
                   f"billable once {cx_txt} hours prior to the scheduled pickup time{'s are' if len(cxs)>1 else ' is'} reached. "
                   f"Modifications or cancellations made within {'these windows' if len(cxs)>1 else 'this window'} may result in fees.")

    opener = (f"Thanks so much again for the opportunity to support {event}!" if register == "sales"
              else f"Thank you for sending these details over{(' for ' + date_txt) if date_txt else ''}! Please find the quote below")
    incl_bits = ([f"a {abs(disc['value']):g}% discount"] if disc else []) + ([f"the {fuel['value']:g}% fuel surcharge"] if fuel else [])
    if incl_bits:
        what = " and ".join(incl_bits)
        opener += (f" — I've incorporated {what} into the pricing for you." if register == "sales"
                   else f", which includes {what}.")
    elif register == "csm":
        opener += "."
    total_line = f"That brings the program to {money(q['total_cents'])}" + (f" for Option A, or {money(ob['total_cents'])} with Option B" if ob else "") + "."
    incl = ("Our pricing includes all charges other than variable fees (parking, tolls, airport fees), which are passed along at cost if incurred"
            + (f", and the {fuel['value']:g}% fuel surcharge is included in the figures above" if fuel else "")
            + ". Our drivers are well compensated and additional gratuity is not expected.")
    # One plain sentence, on its own, after the inclusions and before the close. It is
    # kept deliberately flat and names no beneficiary: the commission may be earned by
    # the client or by an agency acting for them, and this is a note on the arrangement
    # rather than something to sell. The amount is COPIED from quote.json, where
    # apply_adjustments.py computed it; this script computes nothing.
    commission = q.get("commission_pct")
    commission_line = (q.get("commission_line")
                       or (f"A {float(commission):g}% commission applies to this program."
                           if commission else ""))
    # R82: the commission is the figure that helps sell the quote, so it sits directly under
    # the totals under its own heading, not after the inclusions paragraph. Still flat.
    commission_block = ("COMMISSION\n" + commission_line) if commission_line else ""
    tbd_line = "Send over the flight details when you have them and we'll lock in the timing." if flight_tbd else ""
    closer = ("We'll be standing by at your service!" if register == "sales" else "As always, let us know if you have any questions! We are happy to help.")
    signoff = "Warm Regards," if register == "sales" else "All the best,"
    from client_requests import requests_line
    body = "\n\n".join(x for x in [greet, opener, requests_line(q), blocks, cx_note, total_line + " The full line items, rate card, and terms are in the attached PDF, and the pricing holds through " + day(m.get('valid_until'), '%B %-d') + ".", commission_block, incl, tbd_line, closer, signoff + "\n" + (am.get('name') or m.get('prepared_by') or 'Savoya') + ("\n" + am['title'] if am.get('title') else "") + ("\n" + am['email'] if am.get('email') else "")] if x)
    # R71: the short email. Option and leg totals, the discount, the commission amount and a
    # pointer to the PDF. Every figure is COPIED from quote.json (Core's engine_net_line_cents,
    # total_cents, option_b.total_cents, commission_line); this script computes none.
    def short_line(l):
        net = l.get("engine_net_line_cents")
        return f"  \u2022 {l.get('ref','')} {day(l.get('date'),'%a %-m/%-d')}, {l['vehicle']['quantity']} \u00d7 {l['vehicle']['name']}" + (f": {money(net)}" if net is not None else "")
    short_bits = ["Option A:\n" + "\n".join(short_line(l) for l in primaries)]
    if ob and alts:
        short_bits.append("Option B (in place of " + ", ".join(replaced_refs) + "):\n" + "\n".join(short_line(l) for l in alts))
    short_totals = f"Option A comes to {money(q['total_cents'])}" + (f" and Option B to {money(ob['total_cents'])}" if ob else "") + "."
    disc_short = (f" That includes a {abs(disc['value']):g}% discount" + (f" and the {fuel['value']:g}% fuel surcharge" if fuel else "") + ".") if disc else (f" That includes the {fuel['value']:g}% fuel surcharge." if fuel else "")
    short_body = "\n\n".join(x for x in [
        greet,
        f"Here is the quote for {event}.",
        "\n\n".join(short_bits),
        short_totals + disc_short,
        commission_block, requests_line(q), tbd_line,
        f"The full line items and terms are in the attached PDF. Pricing holds through {day(m.get('valid_until'), '%B %-d')}.",
        signoff + "\n" + (am.get('name') or m.get('prepared_by') or 'Savoya')] if x)
    out = {"to": a.to, "subject": subject, "body": body, "short_body": short_body, "attachment": a.attachment}
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), indent=2)
    if a.short:
        print("Subject: " + subject + "\n\n" + short_body)
    else:
        print("Subject: " + subject + "\n\n" + body + "\n\n=== SHORT VERSION ===\n\n" + short_body)

if __name__ == "__main__":
    main()
