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
  boilerplate   process wording ("send flight details", "invoice")   -> not named
"""
import re

OPERATIONAL = re.compile(
    r"\b(pa\b|p\.a\.|speaker|microphone|mic\b|sign(age|s)?\b|banner|decal|placard|water|snack|"
    r"beverage|cooler|wi-?fi|charging|wheelchair|ada\b|lift|car seat|booster|child seat|"
    r"greeter|meet and greet|decorat|branding|wrap|tv\b|screen|music|audio|"
    r"luggage|cargo|trailer|ski|golf bag|bike)", re.I)
DATA_ANSWERED = re.compile(
    r"\b(pick-?up|drop-?off|what time|how many|inventory|available|availability|capacity|"
    r"seats?|vehicle count|how long|duration|distance)\b", re.I)
BOILERPLATE = re.compile(
    r"\b(flight details?|send (over|us)|invoice|receipt|payment|deposit|contract|terms|"
    r"cancel|confirm(ation)?|call me|email me|follow up)\b", re.I)

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


def carry(strings):
    out, seen = [], set()
    for s in strings or []:
        s = (s or "").strip()
        if not s or s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append({"text": s, "kind": classify(s)})
    return out


def requests_line(quote):
    """One neutral sentence, or '' when there is nothing operational to name."""
    items = [r["text"] for r in (quote.get("client_requests") or []) if r.get("kind") == "operational"]
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
