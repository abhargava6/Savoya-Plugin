#!/usr/bin/env python3
"""Drive the document-flow questions from handoff/intake.json → decisions.
  decide.py --next            → prints the next unanswered key and its question text
  decide.py <key> <value>     → records the answer, prints the next key
Keys, in order: discount_pct, request:<n> (one per operational client request, R72), commission_pct, cover, personalization, map, format.

The `fuel` question is gone (C3, 0.23.0). Fuel is market-scoped and engine-applied, and
nothing in the contract subtracts it: `temporary_discount` is additive and a surcharge is
not a discount. The old `waive` already told the CSM the booking needed the waiver applied
in Savoya, so it was never ours to give. Core applies it; we present it as Core applied
it."""
import argparse, datetime as dt, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_ORDER = ["discount_pct", "commission_pct", "cover", "personalization", "map", "format"]
GREETER_RE = re.compile(r"greeter|on-?site (staff|support|coordinat)|meet (and|&) greet|hostess", re.I)


# Which formats actually consume which answers.
#   cover — the audience cover page, built only by render_print (PDF and printable doc).
#           DOCX draws a cover only from personalization.cover_image_url / client_logo_url,
#           which is a different field, so the catalog question does nothing for it.
#   map   — route_page() in render_print is the only reader of quote.route_map anywhere.
# Asking either one for an email-only job wastes the user's time, and `map` also costs
# 10-20s of geocoding and routing to populate a field nothing will read.
PDF_LIKE = {"pdf", "email+pdf", "print"}
FORMAT_ALIASES = {
    "pdf": "pdf", "proposal": "pdf",
    "email+pdf": "email+pdf", "email copy + pdf": "email+pdf", "email and pdf": "email+pdf",
    "print": "print", "printable": "print", "printable document": "print", "web page": "print",
    "email": "email", "email copy": "email", "email only": "email", "email copy only": "email",
    "html": "html", "html email": "html",
    "docx": "docx", "word": "docx",
    "xlsx": "xlsx", "excel": "xlsx",
}


def normalize_format(v):
    if not isinstance(v, str):
        return None
    return FORMAT_ALIASES.get(v.strip().lower())


def order_for(intake):
    """Questions are fixed, except:
      - greeter_cost appears only when the client asked for one;
      - cover and map are dropped once the format is known not to use them. The user
        states the format up front often enough ("just draft the email") that asking
        about cover pages and route maps afterwards reads as not listening."""
    o = list(BASE_ORDER)
    # R72/R73: one question per operational client request that Core cannot answer. The
    # tax, gratuity and cancellation questions are answered by the terms block and never asked.
    sys.path.insert(0, HERE)
    from client_requests import request_keys
    o[o.index("discount_pct") + 1:o.index("discount_pct") + 1] = request_keys(intake.get("client_questions"))
    if any(GREETER_RE.search(q or "") for q in (intake.get("client_questions") or [])):
        o.insert(o.index("discount_pct") + 1, "greeter_cost")
    fmt = normalize_format((intake.get("decisions") or {}).get("format"))
    if fmt and fmt not in PDF_LIKE:
        o = [k for k in o if k not in ("cover", "map")]
    return o
QUESTIONS = {
  "discount_pct": "Any additional discount for this client? A whole percentage, or none. I'll re-quote it through Savoya rather than adjusting the number here.{engine} FYI: an extra discount is not stored in Savoya. The booking prices without it unless you also add it to the client's profile.",
  "commission_pct": "Does this client get a commission on this quote? No, 1%, 5%, or another percentage. It goes on the quote and in the email with its amount, which is computed for you \u2014 it changes none of the totals.",
  "greeter_cost": "The client asked about a greeter / on-site coordinator. How many hours? I'll price it through Savoya at the market rate. If this market has no greeter rate I'll come back and ask for a cost, or leave it off as arranged separately. FYI: a greeter cost you give me is not in Savoya either. Leave a note on the reservation for billing and operations so the booking carries it.",
  "cover": "Which cover?\n{covers}\n…or upload your own (PDF or image).",
  "personalization": "I'll use: event name \"{event}\", a two-line intro note from you, your contact card at the end, no client logo, no per-leg notes, no closing line. Confirm, or tell me what to change (logo URL, notes, closing line).",
  "map": "Add a route map with drive times? (about 15 seconds)",
  "format": "Email copy on its own, email copy + PDF, PDF, printable document (a web page that prints identically to the PDF), HTML email, Word, or Excel?",
}
ap = argparse.ArgumentParser(); ap.add_argument("key", nargs="?"); ap.add_argument("value", nargs="?")
ap.add_argument("--next", action="store_true"); ap.add_argument("--fyi", action="store_true"); ap.add_argument("--dir", default="handoff"); ap.add_argument("--quote", default="quote.json")
a = ap.parse_args()
b_ = os.path.join(a.dir, "blocked.json")
if os.path.exists(b_):
    try:
        r_ = json.load(open(b_, encoding="utf-8"))
    except (OSError, ValueError):
        r_ = {}
    sys.exit(f"The handoff write was refused ({r_.get('gate', '?')}): {r_.get('reason', 'see blocked.json')}\nFix: {r_.get('fix', 'fix the cause and write the handoff again')}\n"
             "Do not carry on by hand: no hand-built intake.json, no decisions kept in your head, no calling the scripts' internals. "
             "Fix the cause and write again, or stop and tell the user why (R92).")
p = os.path.join(a.dir, "intake.json")
if not os.path.exists(p):
    sys.exit(f"No {p} — fallback path; ask the questions in BASE_ORDER without persistence.")
d = json.load(open(p, encoding="utf-8"))
if a.key and a.value is not None:
    try: val = json.loads(a.value)
    except ValueError: val = a.value
    d.setdefault("decisions", {})[a.key] = val
    d.setdefault("log", []).append({"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "step": "doc", "note": f"{a.key} = {val!r}"[:120]})
    json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
def _amount(v):
    try: return float(str(v).strip().rstrip("%").lstrip("$").replace(",", ""))
    except ValueError: return 0.0
if a.fyi:
    # R103: money that exists only in this quote. Said once more at delivery, in plain words.
    dec = d.get("decisions") or {}
    out = []
    if _amount(dec.get("discount_pct")) > 0:
        out.append("The extra discount is not in Savoya. Add it to the client's profile, or the booking prices without it.")
    if d.get("temporary_pricing"):
        out.append("A custom rate or discount you supplied while quoting is not in Savoya. Add the rate in Savoya, or the discount to the client's profile, or the booking prices differently.")
    if _amount(dec.get("greeter_cost")) > 0:
        out.append("The greeter cost is not in Savoya. Leave a note on the reservation for billing and operations.")
    cl = d.get("client") or {}
    if cl.get("source") == "stand-in":
        out.append(f"This quote ran under a stand-in client. Book it under {cl.get('display_name') or 'the real client'}, not the stand-in.")
    print("\n".join(out) if out else "none")
    sys.exit(0)
nxt = next((k for k in order_for(d) if k not in d.get("decisions", {})), None)
if not nxt:
    print("all answered"); sys.exit(0)
# build the question text with context
q = None
try: q = json.load(open(a.quote, encoding="utf-8"))
except Exception: pass
ctx = {"engine": "", "covers": "",
       "event": (d.get("client", {}).get("name") or "Client") + " — Ground Transportation"}
if q:
    eng = [x for x in q.get("adjustments", []) if x.get("source") == "engine" and "discount" in x["label"].lower()]
    if eng: ctx["engine"] = f" (The engine already applied {abs(eng[0]['value']):g}% — this would be additional.)"
    ev = (q.get("personalization") or {}).get("event_name")
    if ev: ctx["event"] = ev
try:
    cat = json.load(open(os.path.join(HERE, "..", "assets", "covers", "catalog.json")))
    ctx["covers"] = "\n".join(f"  {i+1}. {c['key']} — {c['audience']}" for i, c in enumerate(cat["covers"]) if c["key"] != "custom")
except Exception:
    ctx["covers"] = "  (see assets/covers/catalog.json)"
# The email draft reads only account_manager and event_name. Offering an intro note,
# a client logo, per-leg notes and a closing line promises four things it will ignore.
if nxt == "personalization":
    fmt_now = normalize_format((d.get("decisions") or {}).get("format"))
    if fmt_now in ("email", "xlsx"):
        QUESTIONS["personalization"] = ('I\'ll use: event name "{event}" and your contact details at the sign-off. '
                                        "Confirm, or tell me what to change.")
if nxt.startswith("request:"):
    _qs = d.get("client_questions") or []
    _txt = _qs[int(nxt.split(":", 1)[1])]
    print(f"next: {nxt}\nThe client asked: \"{_txt}\". Savoya's pricing can't answer it. How should the document respond? "
          "included, not included, extra cost, confirm (we'll say it was noted and will be confirmed), or your own wording in a sentence. "
          "Never answer for the user."
          + (" This is a fit question: Savoya returns seat capacity but no luggage or interior dimensions. Never say it fits; use confirm, or the user's own wording with a figure they supply (R35)."
             if re.search(r"\bfit|carry-?on|luggage", _txt, re.I) else ""))
    sys.exit(0)
print(f"next: {nxt}\n{QUESTIONS[nxt].format(**ctx)}")
