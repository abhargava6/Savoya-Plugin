#!/usr/bin/env python3
"""Produce the house-style quote email (subject + body) for the user to copy into their own mail client.

Usage: draft_email.py quote.json [--to client@x.com] [--attachment boston.pdf] [--json out.json]
Prints subject/body; --json also writes {"to","subject","body","attachment"} for reference. The skill posts this text in the chat — it does not create drafts or attach files.
The body is deliberately short — the PDF carries the detail.
"""

import argparse, datetime as dt, json, sys


def money(c):
    return "—" if c is None else f"${c/100:,.2f}"


def day(iso, fmt="%A, %B %-d"):
    try:
        return dt.datetime.fromisoformat(iso).strftime(fmt)
    except (ValueError, TypeError):
        return iso or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("--to", default=None)
    ap.add_argument("--attachment", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    q = json.load(open(a.quote, encoding="utf-8"))
    m, pz = q["meta"], q.get("personalization", {})
    am = pz.get("account_manager") or {}
    event = pz.get("event_name") or m.get("title")
    iso = sorted({l["date"][:10] for l in q["legs"] if l.get("date")})
    dates = [day(d, "%b %-d") for d in iso]
    date_txt = (
        " – ".join([dates[0], dates[-1]])
        if len(dates) > 1
        else (dates[0] if dates else "")
    )
    if event and any(
        x in event
        for x in (
            "20",
            "June",
            "Jun",
            "Sept",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jul",
            "Aug",
        )
    ):
        date_txt = ""  # event name already carries the dates
    primaries = q["legs"]

    def line(l):
        route = " → ".join(s["label"] for s in l["stops"])
        if len(l["stops"]) >= 2 and l["stops"][0]["label"] == l["stops"][-1]["label"]:
            route = (
                l["stops"][0]["label"]
                + " (round trip"
                + (", " + l["stops"][1]["label"] if len(l["stops"]) > 2 else "")
                + ")"
            )
        return f"  • {l.get('ref','')} {day(l.get('date'),'%a %-m/%-d')} — {l['vehicle']['quantity']} × {l['vehicle']['name']}, {route}"

    legs_txt = "\n".join(line(l) for l in primaries)
    tbd = [p for p in q.get("internal", {}).get("placeholders", [])]
    subject = f"Savoya quote — {event}" + (f" ({date_txt})" if date_txt else "")
    tc = (
        (m.get("travel_coordinator") or "").split(" (")[0].split()[0]
        if m.get("travel_coordinator")
        else None
    )
    greet = f"Hi {tc}," if tc else "Hi there,"
    title = (am.get("title") or "").lower()
    register = "sales" if "sales" in title or "vp" in title else "csm"
    adjustments = q.get("adjustments") or {}
    discount_bps = adjustments.get(
        "temporary_discount_basis_points"
    ) or adjustments.get("discount_basis_points")
    fuel_bps = adjustments.get("fuel_surcharge_basis_points")

    def block(l, n=None, prefix=""):
        p, v = l["pricing"], l["vehicle"]
        when = day(l.get("date"), "%A, %B %-d")
        hdr = f"{prefix}{l.get('ref','')} – {when} – {v['quantity']} × {v['name']}" + (
            f" ({l['label']})" if l.get("label") and len(l["label"]) < 60 else ""
        )
        lines = [
            hdr,
            f"Vehicle type: {v['name']} (max capacity: {v.get('capacity')} passengers)",
        ]
        cx = p.get("cancellation_hours")
        if cx:
            lines.append(
                f"Cancellation policy*: {cx} hours"
                + (
                    " (1 week)"
                    if cx == 168
                    else " (72 hours = 3 days)" if cx == 72 else ""
                )
            )
        if p["method"] == "hourly":
            if p.get("minimum_hours"):
                lines.append(f"Minimum hours: {p['minimum_hours']:g} hours")
            lines.append(
                f"Quoted time: {p.get('billable_hours'):g} hours"
                + (" per vehicle" if v["quantity"] > 1 else "")
            )
            lines.append(f"Client Hourly Rate: {money(p['effective_rate_cents'])}")
        else:
            lines.append(
                f"Type: Transfer – {money(p['per_vehicle_cents'])}"
                + (" per vehicle" if v["quantity"] > 1 else "")
            )
        if p.get("special_event"):
            lines.append(
                f"Special event: {p['special_event']['name']} rates are in effect on this date and availability is limited."
            )
        if v["quantity"] > 1:
            lines.append(
                f"Estimated Total for 1 {v['name']}: {money(p['per_vehicle_cents'])}"
            )
        lines.append(f"Estimated Total: {money(p['line_total_cents'])}")
        return "\n".join(lines)

    blocks = "\n\n".join(block(l) for l in primaries)
    cxs = sorted(
        {
            l["pricing"].get("cancellation_hours")
            for l in q["legs"]
            if l["pricing"].get("cancellation_hours")
        }
    )
    cx_note = ""
    if cxs:
        cx_txt = " & ".join(str(c) for c in cxs)
        cx_note = (
            f"*Please note, {'these cancellation policies mean these trips are' if len(cxs)>1 else 'this cancellation policy means this reservation is'} "
            f"billable once {cx_txt} hours prior to the scheduled pickup time{'s are' if len(cxs)>1 else ' is'} reached. "
            f"Modifications or cancellations made within {'these windows' if len(cxs)>1 else 'this window'} may result in fees."
        )

    opener = (
        f"Thanks so much again for the opportunity to support {event}!"
        if register == "sales"
        else f"Thank you for sending these details over{(' for ' + date_txt) if date_txt else ''}! Please find the quote below"
    )
    incl_bits = ([f"a {discount_bps / 100:g}% discount"] if discount_bps else []) + (
        [f"the {fuel_bps / 100:g}% fuel surcharge"] if fuel_bps else []
    )
    if incl_bits:
        what = " and ".join(incl_bits)
        opener += (
            f" — I've incorporated {what} into the pricing for you."
            if register == "sales"
            else f", which includes {what}."
        )
    elif register == "csm":
        opener += "."
    total_line = f"That brings the program to {money(q['total_cents'])}."
    incl = (
        "Our pricing includes all charges other than variable fees (parking, tolls, airport fees), which are passed along at cost if incurred"
        + (
            f", and the {fuel_bps / 100:g}% fuel surcharge is included in the figures above"
            if fuel_bps
            else ""
        )
        + ". Our drivers are well compensated and additional gratuity is not expected."
    )
    tbd_line = (
        "Send over the flight details when you have them and we'll lock in the timing."
        if tbd
        else ""
    )
    closer = (
        "We'll be standing by at your service!"
        if register == "sales"
        else "As always, let us know if you have any questions! We are happy to help."
    )
    signoff = "Warm Regards," if register == "sales" else "All the best,"
    body = "\n\n".join(
        x
        for x in [
            greet,
            opener,
            blocks,
            cx_note,
            total_line
            + " The full line items, rate card, and terms are in the attached PDF, and the pricing holds through "
            + day(m.get("valid_until"), "%B %-d")
            + ".",
            incl,
            tbd_line,
            closer,
            signoff
            + "\n"
            + (am.get("name") or m.get("prepared_by") or "Savoya")
            + ("\n" + am["title"] if am.get("title") else "")
            + ("\n" + am["email"] if am.get("email") else ""),
        ]
        if x
    )
    out = {"to": a.to, "subject": subject, "body": body, "attachment": a.attachment}
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), indent=2)
    print("Subject: " + subject + "\n\n" + body)


if __name__ == "__main__":
    main()
