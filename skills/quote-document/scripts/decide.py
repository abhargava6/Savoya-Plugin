#!/usr/bin/env python3
"""Drive the document-flow questions from handoff/intake.json → decisions.
  decide.py --next            → prints the next unanswered key and its question text
  decide.py <key> <value>     → records the answer, prints the next key
Keys, in order: discount_pct, cover, personalization, map, format.

The discount answer triggers an MCP re-quote; this script never changes money.
Fuel and greeter price overrides are intentionally unsupported."""

import argparse, datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_ORDER = ["discount_pct", "cover", "personalization", "map", "format"]


# Which formats actually consume which answers.
#   cover — the audience cover page, built only by render_print (PDF and printable doc).
#           DOCX draws a cover only from personalization.cover_image_url / client_logo_url,
#           which is a different field, so the catalog question does nothing for it.
#   map   — route_page() in render_print is the only reader of quote.route_map anywhere.
# Asking either one for an email-only job wastes the user's time, and `map` also costs
# 10-20s of geocoding and routing to populate a field nothing will read.
PDF_LIKE = {"pdf", "email+pdf", "print"}
FORMAT_ALIASES = {
    "pdf": "pdf",
    "proposal": "pdf",
    "email+pdf": "email+pdf",
    "email copy + pdf": "email+pdf",
    "email and pdf": "email+pdf",
    "print": "print",
    "printable": "print",
    "printable document": "print",
    "web page": "print",
    "email": "email",
    "email copy": "email",
    "email only": "email",
    "email copy only": "email",
    "html": "html",
    "html email": "html",
    "docx": "docx",
    "word": "docx",
    "xlsx": "xlsx",
    "excel": "xlsx",
}


def normalize_format(v):
    if not isinstance(v, str):
        return None
    return FORMAT_ALIASES.get(v.strip().lower())


def order_for(intake):
    """Questions are fixed, except cover and map are dropped once the format is known not to use them. The user
    states the format up front often enough ("just draft the email") that asking
    about cover pages and route maps afterwards reads as not listening."""
    o = list(BASE_ORDER)
    fmt = normalize_format((intake.get("decisions") or {}).get("format"))
    if fmt and fmt not in PDF_LIKE:
        o = [k for k in o if k not in ("cover", "map")]
    return o


QUESTIONS = {
    "discount_pct": "Any additional whole-percentage discount for this client, or none?{engine}",
    "cover": "Which cover?\n{covers}\n…or upload your own (PDF or image).",
    "personalization": 'I\'ll use: event name "{event}", a two-line intro note from you, your contact card at the end, no client logo, no per-leg notes, no closing line. Confirm, or tell me what to change (logo URL, notes, closing line).',
    "map": "Add a route map with drive times? (about 15 seconds)",
    "format": "Email copy on its own, email copy + PDF, PDF, printable document (a web page that prints identically to the PDF), HTML email, Word, or Excel?",
}
ap = argparse.ArgumentParser()
ap.add_argument("key", nargs="?")
ap.add_argument("value", nargs="?")
ap.add_argument("--next", action="store_true")
ap.add_argument("--dir", default="handoff")
ap.add_argument("--quote", default="quote.json")
a = ap.parse_args()
p = os.path.join(a.dir, "intake.json")
if not os.path.exists(p):
    sys.exit(
        f"No {p} — fallback path; ask the six questions in order without persistence."
    )
d = json.load(open(p, encoding="utf-8"))
if a.key and a.value is not None:
    try:
        val = json.loads(a.value)
    except ValueError:
        val = a.value
    d.setdefault("decisions", {})[a.key] = val
    d.setdefault("log", []).append(
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "step": "doc",
            "note": f"{a.key} = {val!r}"[:120],
        }
    )
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
nxt = next((k for k in order_for(d) if k not in d.get("decisions", {})), None)
if not nxt:
    print("all answered")
    sys.exit(0)
# build the question text with context
q = None
try:
    q = json.load(open(a.quote, encoding="utf-8"))
except Exception:
    pass
# No fuel line on the quote: ask whether to add one, without naming a rate. The figure is
# market-scoped (5% in most, 10% in London and others) and guessing it in the question put
# a wrong number in front of the user.
ctx = {
    "engine": "",
    "covers": "",
    "event": (d.get("client", {}).get("name") or "Client") + " — Ground Transportation",
}
if q:
    eng = [
        x
        for x in q.get("adjustments", [])
        if x.get("source") == "engine" and "discount" in x["label"].lower()
    ]
    if eng:
        ctx["engine"] = (
            f" (The engine already applied {abs(eng[0]['value']):g}% — this would be additional.)"
        )
    temp = [
        ((leg.get("adjustments") or {}).get("temporary_discount_basis_points"))
        for leg in q.get("legs", [])
    ]
    temp = [value for value in temp if value is not None]
    if temp and len(set(temp)) == 1:
        ctx["engine"] = f" (The current temporary discount is {temp[0] / 100:g}%.)"
    ev = (q.get("personalization") or {}).get("event_name")
    if ev:
        ctx["event"] = ev
try:
    cat = json.load(open(os.path.join(HERE, "..", "assets", "covers", "catalog.json")))
    ctx["covers"] = "\n".join(
        f"  {i+1}. {c['key']} — {c['audience']}"
        for i, c in enumerate(cat["covers"])
        if c["key"] != "custom"
    )
except Exception:
    ctx["covers"] = "  (see assets/covers/catalog.json)"
# The email draft reads only account_manager and event_name. Offering an intro note,
# a client logo, per-leg notes and a closing line promises four things it will ignore.
if nxt == "personalization":
    fmt_now = normalize_format((d.get("decisions") or {}).get("format"))
    if fmt_now in ("email", "xlsx"):
        QUESTIONS["personalization"] = (
            'I\'ll use: event name "{event}" and your contact details at the sign-off. '
            "Confirm, or tell me what to change."
        )
print(f"next: {nxt}\n{QUESTIONS[nxt].format(**ctx)}")
