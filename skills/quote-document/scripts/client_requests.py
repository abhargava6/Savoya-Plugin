#!/usr/bin/env python3
"""Client requests carried from intake (R73).

A request such as "PA system on the bus" or "signage in the windows" is not something the
pricing system answers. The session must neither claim it is included nor claim it is
excluded or "arranged separately": it does not know. This module classifies the carried
strings and builds ONE neutral sentence that states the request was noted and will be
confirmed. Confirmation of the actual answer happens before send (R72, confirm_items.py).

Classes:
  operational   a service or amenity request Core cannot answer      -> named in the line
  data_answered the quote data already answers it (pickup time, counts) -> not named
  boilerplate   process wording ("send flight details", "invoice"), and fuel: the surcharge is whole-quote only (R62) -> not named
"""
import re

OPERATIONAL = re.compile(
    r"\b(pa\b|p\.a\.|speaker|microphone|mic\b|sign(age|s)?\b|banner|decal|placard|water|snack|"
    r"beverage|cooler|wi-?fi|charging|wheelchair|ada\b|lift|car seat|booster|child seat|"
    r"greeter|meet and greet|decorat|branding|wrap|tv\b|screen|music|audio|"
    r"luggage|carry-?ons?|fit(s)?\\b|cargo|trailer|ski|golf bag|bike)", re.I)
# A greeter or meet-and-greet is answered by decide.py's greeter_cost question, so it is never asked twice.
GREETER = re.compile(r"greeter|on-?site (staff|support|coordinat)|meet (and|&) greet|hostess", re.I)
DATA_ANSWERED = re.compile(
    r"\b(pick-?up|drop-?off|what time|how many|inventory|available|availability|capacity|"
    r"seats?|vehicle count|how long|duration|distance)\b", re.I)
BOILERPLATE = re.compile(
    r"\b(flight details?|send (over|us)|invoice|receipt|payment|deposit|contract|terms|"
    r"cancel\w*|confirmations?|confirm (the )?(flight|booking|reservation|receipt|payment|invoice|details?)|"
    r"call me|email me|follow up|fuel|"
    r"tax(es)?|gratuity|tips?|tipping)\b", re.I)   # tax, gratuity and cancellation are answered by the terms block (R72)

# Words that would assert an answer the session does not have.
FORBIDDEN = re.compile(
    r"\b(not included|isn'?t included|is included|are included|included in|excluded|"
    r"arranged separately|separately arranged|at no (extra )?(cost|charge)|complimentary|"
    r"not part of)\b", re.I)


def classify(text):
    t = text or ""
    if BOILERPLATE.search(t):
        return "boilerplate"
    if OPERATIONAL.search(t):
        return "operational"
    if DATA_ANSWERED.search(t):
        return "data_answered"
    return "operational"  # unknown: surface it rather than lose it


# What the user can answer for a request Core cannot (R72/R73). The key is what decide.py
# stores; anything else the user types is used as their own wording.
ANSWERS = {
    "included": "Yes, we can provide this.",
    "not included": "We are not able to provide this.",
    "extra cost": "Available at additional cost; we will confirm the amount.",
    "confirm": None,   # no answer yet: falls back to the noted-and-will-confirm sentence
}


def answer_for(value):
    """(key, sentence). sentence None means 'still to be confirmed'."""
    v = (value or "").strip()
    if not v:
        return None, None
    k = v.lower()
    if k in ANSWERS:
        return k, ANSWERS[k]
    return "custom", v.rstrip() if v.endswith((".", "!", "?")) else v + "."


def request_keys(strings):
    """decide.py keys, one per operational request, by position in intake's client_questions."""
    return [f"request:{i}" for i, s in enumerate(strings or []) if (s or "").strip() and classify(s) == "operational" and not GREETER.search(s)]


def carry(strings, decisions=None):
    out, seen = [], set()
    decisions = decisions or {}
    for i, s in enumerate(strings or []):
        s = (s or "").strip()
        if not s or s.lower() in seen:
            continue
        seen.add(s.lower())
        item = {"text": s, "kind": classify(s)}
        if item["kind"] == "operational" and not GREETER.search(s):
            key, sentence = answer_for(decisions.get(f"request:{i}"))
            if key:
                item["answer"] = key
                item["answer_text"] = sentence
        out.append(item)
    return out


def requests_line(quote):
    """The client's operational requests, answered where the user answered and noted where not.

    A request the user answered prints their answer next to the request. The rest stay in one
    neutral sentence that says they were noted and will be confirmed; that sentence never
    asserts an answer (FORBIDDEN applies to it only)."""
    ops = [r for r in (quote.get("client_requests") or []) if r.get("kind") == "operational"]
    answered = [r for r in ops if r.get("answer_text")]
    pending = _pending_line([r["text"] for r in ops if not r.get("answer_text")], quote)
    lines = [f"Re: {r['text'].rstrip('. ?')} \u2014 {r['answer_text']}" for r in answered]
    return " ".join(lines + ([pending] if pending else []))


def _pending_line(items, quote):
    if not items:
        return ""
    # The intro note may already say it (the session wrote it from the request): never twice.
    if re.search(r"noted your request", str(((quote.get("personalization") or {}).get("intro_note")) or ""), re.I):
        return ""
    items = [i.rstrip(". ") for i in items]
    if len(items) == 1:
        body = items[0]
    elif len(items) == 2:
        body = items[0] + " and " + items[1]
    else:
        body = "; ".join(items[:-1]) + "; and " + items[-1]
    return f"We've noted your requests ({body}) and will confirm each with you."
