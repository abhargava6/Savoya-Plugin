#!/usr/bin/env python3
"""List everything the user must confirm before a quote is sent (PRD R72).

Usage: confirm_items.py quote.json [--json]

Items come from quote.internal.placeholders and quote.client_requests:
  service_area   every "NO SAVOYA SERVICE AREA" placeholder, grouped into ONE item
  placeholder    each other placeholder (pickup time, inventory note, ...), one each
  client_request each operational request the user has not answered (R73), one each; an answered request is in the document already

The session asks one question per item (Right / Wrong). It is a gate only: a "Wrong"
answer stops the send and asks for the corrected value. Nothing is written to the
document from the answer. Exit code 0 always; the list may be empty.
"""
import json
import re
import sys

AREA = re.compile(r"NO SAVOYA SERVICE AREA", re.I)


def items(q):
    out, areas = [], []
    for p in (q.get("internal") or {}).get("placeholders") or []:
        if AREA.search(p):
            areas.append(p.split(":", 1)[0].strip())
        else:
            for part in [x.strip() for x in p.split(";") if x.strip()]:
                out.append({"kind": "placeholder", "text": part})
    res = []
    if areas:
        res.append({"kind": "service_area",
                    "text": f"{len(areas)} leg(s) have no Savoya service area at any stop: "
                            + ", ".join(areas) + ". Core priced them from the nearest market."})
    res += out
    for r in q.get("client_requests") or []:
        if r.get("kind") == "operational" and not r.get("answer_text"):
            res.append({"kind": "client_request",
                        "text": f"Client asked: {r['text']}. The document says it was noted and will be confirmed."})
    for i, it in enumerate(res, 1):
        it["id"] = i
    return res


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    q = json.load(open(sys.argv[1], encoding="utf-8"))
    res = items(q)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        print(f"{len(res)} item(s) to confirm before send")
        for it in res:
            print(f"  {it['id']}. [{it['kind']}] {it['text']}")


if __name__ == "__main__":
    main()
