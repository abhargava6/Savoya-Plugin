#!/usr/bin/env python3
"""Set the personalization fields on quote.json, without hand-editing it.

`decide.py` asks the personalization question and records the answer in
handoff/intake.json. Nothing then wrote it into quote.json, and no setter existed, so
every session edited the file by hand -- reported in two of the three live sessions on
10 Oct 2026, where `event_name` and `intro_note` "stayed null and had to be set
manually".

Hand-editing a client document is how wrong claims get in. In the Irvine session the
intro note went in asserting that tax and driver gratuity were included; the terms on
the final page of the same PDF say the opposite, and it was caught and corrected only
because someone re-read it before rendering. So this writes the fields AND refuses the
contradictions it can recognise.

Usage:
  set_personalization.py quote.json --event-name "Yerdle — World Cup 2027" \
      --intro-note "…" [--cover event-planners] [--closing-note "…"]
      [--am-name "…"] [--am-title "…"] [--am-email "…"] [--am-phone "…"]
      [--pull-quote "…" --pull-quote-attribution "…"] [--client-logo-url URL]
      [--from-handoff handoff/intake.json]   # take event_name from the recorded decision
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS = os.path.join(HERE, "..", "references", "terms.md")

# Each is a claim the standard terms contradict. The terms are the contract; a friendly
# sentence at the top of the document does not get to override them, and a client who
# reads both sees us disagreeing with ourselves about what they owe.
_CONTRADICTIONS = [
    (re.compile(r"\b(gratuit|tip)\w*\b[^.]{0,40}\b(includ|cover)", re.I),
     "says gratuity is included; the terms say drivers are well compensated and "
     "additional gratuity is not expected, which is not the same promise"),
    (re.compile(r"\b(tax|taxes)\b[^.]{0,40}\b(includ|cover)", re.I),
     "says tax is included; the terms bill state taxes at cost as incurred"),
    (re.compile(r"\b(toll|parking|airport fee)\w*\b[^.]{0,40}\b(includ|cover)", re.I),
     "says parking, tolls or airport fees are included; the terms bill them at cost"),
    (re.compile(r"\b(final|guaranteed)\b[^.]{0,30}\b(price|pricing|quote)\b", re.I),
     "calls the figure final or guaranteed; the terms say this is not a final price "
     "nor guaranteed pricing"),
    (re.compile(r"\bno (additional|extra|hidden) (charge|fee|cost)s?\b", re.I),
     "promises no additional charges; the terms list several billed at cost"),
]


def check_note(text):
    return [why for rx, why in _CONTRADICTIONS if rx.search(text or "")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("--event-name"); ap.add_argument("--intro-note")
    ap.add_argument("--cover"); ap.add_argument("--client-logo-url")
    ap.add_argument("--pull-quote"); ap.add_argument("--pull-quote-attribution")
    ap.add_argument("--closing-note")
    ap.add_argument("--am-name"); ap.add_argument("--am-title")
    ap.add_argument("--am-email"); ap.add_argument("--am-phone")
    ap.add_argument("--from-handoff", default=None,
                    help="read the recorded personalization decision from intake.json "
                         "so the answer the user actually gave reaches the document")
    ap.add_argument("--force", action="store_true",
                    help="write an intro note that contradicts the terms anyway. There is "
                         "no good reason; the terms are the contract.")
    a = ap.parse_args()

    try:
        q = json.load(open(a.quote, encoding="utf-8"))
    except (OSError, ValueError) as ex:
        sys.exit(f"Cannot read {a.quote}: {ex}")

    event = a.event_name
    if not event and a.from_handoff:
        d = {}
        try:
            d = json.load(open(a.from_handoff, encoding="utf-8")) or {}
        except (OSError, ValueError):
            pass
        rec = (d.get("decisions") or {}).get("personalization")
        if isinstance(rec, str):
            m = re.search(r"event_name\s*=\s*(.+?)(?:;|$)", rec)
            if m:
                event = m.group(1).strip()

    if a.intro_note and not a.force:
        bad = check_note(a.intro_note)
        if bad:
            sys.exit("Refusing to write this intro note — it contradicts the terms on the "
                     "final page of the same document:\n"
                     + "\n".join(f"  - it {b}" for b in bad)
                     + "\nSay what IS true (gratuity is not expected; variable fees are "
                       "billed at cost) or pass --force.")

    p = q.setdefault("personalization", {})
    changed = []
    for key, val in (("event_name", event), ("intro_note", a.intro_note),
                     ("cover", a.cover), ("client_logo_url", a.client_logo_url),
                     ("pull_quote", a.pull_quote),
                     ("pull_quote_attribution", a.pull_quote_attribution),
                     ("closing_note", a.closing_note)):
        if val is not None:
            p[key] = val
            changed.append(key)
    am = {k: v for k, v in (("name", a.am_name), ("title", a.am_title),
                            ("email", a.am_email), ("phone", a.am_phone)) if v is not None}
    if am:
        p.setdefault("account_manager", {}).update(am)
        changed.append("account_manager(" + ",".join(sorted(am)) + ")")

    if not changed:
        sys.exit("Nothing to set. Pass at least one field.")
    json.dump(q, open(a.quote, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"{a.quote}: set {', '.join(changed)}")
    if a.pull_quote and not a.pull_quote_attribution:
        print("  NOTE: a pull quote with no attribution renders unattributed.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
