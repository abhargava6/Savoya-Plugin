#!/usr/bin/env python3
"""What the user asked for (PRD R85): deliver exactly that.

The recorded `decisions.format` in handoff/intake.json is the answer. A session that was asked
for a PDF drafted and pasted two emails anyway, so the rule lives here as well as in the prose:
verify_document.py prints the deliverables, and draft_email.py refuses a PDF-only job unless the
user asked for an email (--asked).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

EMAIL_FORMATS = {"email", "email+pdf", "html"}


def find_intake(quote_path):
    base = os.path.dirname(os.path.abspath(quote_path))
    for d in (base, os.path.join(base, "handoff"), os.path.join(os.getcwd(), "handoff")):
        p = os.path.join(d, "intake.json")
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except ValueError:
                return None
    return None


def chosen_format(quote_path):
    """The normalized format the user chose, or None when nothing was recorded."""
    # decide.py runs as a script when imported, so its alias table is READ, not imported:
    # one table, no copy to drift.
    import ast
    src = open(os.path.join(HERE, "decide.py"), encoding="utf-8").read()
    node = next(n for n in ast.parse(src).body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FORMAT_ALIASES")
    aliases = ast.literal_eval(node.value)
    v = ((find_intake(quote_path) or {}).get("decisions") or {}).get("format")
    return aliases.get(v.strip().lower()) if isinstance(v, str) else None


def line_for(fmt):
    if fmt is None:
        return ""
    if fmt in EMAIL_FORMATS:
        return f"DELIVERABLES: {fmt}. Deliver exactly that."
    return (f"DELIVERABLES: {fmt} only. Do NOT run draft_email.py and do not write an email. "
            "After delivering, offer an email in one line (R85).")
