#!/usr/bin/env python3
"""A no-commission copy of a quote's documents, from the same session (PRD R100).

Usage: no_commission_copy.py quote.json [--pdf out.pdf] [--email out.txt] [--dir handoff]

The user wants one version for the agent (commission shown) and one for the client (no
commission line anywhere). This copies quote.json, removes the commission through the same
adjustment step that recorded it, checks that the total did not move (a commission is
stated, never charged), and renders the copy under a separate file name. The original is
not touched. The handoff log records both files.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--email", default=None)
    ap.add_argument("--dir", default="handoff")
    a = ap.parse_args()
    base = os.path.splitext(a.quote)[0]
    copy = base + ".no-commission.json"
    shutil.copy(a.quote, copy)
    r = subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), copy, "--commission-pct", "none"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"could not remove the commission: {(r.stderr or r.stdout).strip()[:300]}")
    before, after = (json.load(open(x, encoding="utf-8")) for x in (a.quote, copy))
    for key in ("commission_pct", "commission_amounts", "commission_line"):
        if after.get(key):
            sys.exit(f"the copy still carries {key}; nothing was written for the client")
    if before.get("total_cents") != after.get("total_cents"):
        sys.exit(f"the total moved ({before.get('total_cents')} -> {after.get('total_cents')}); a commission is stated, never charged. Copy discarded.")
    made = [copy]
    if a.pdf:
        r = subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"), copy, a.pdf], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"render failed: {(r.stderr or r.stdout).strip()[:300]}")
        made.append(a.pdf)
    if a.email:
        out = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), copy], capture_output=True, text=True)
        if out.returncode:
            sys.exit(f"email draft failed: {(out.stderr or out.stdout).strip()[:300]}")
        open(a.email, "w", encoding="utf-8").write(out.stdout)
        made.append(a.email)
    ip = os.path.join(a.dir, "intake.json")
    if os.path.exists(ip):
        d = json.load(open(ip, encoding="utf-8"))
        d.setdefault("log", []).append({"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "step": "doc",
                                        "note": "no-commission copy: " + ", ".join(os.path.basename(x) for x in made)})
        json.dump(d, open(ip, "w", encoding="utf-8"), indent=2)
    print("no-commission copy: " + ", ".join(made))


if __name__ == "__main__":
    main()
