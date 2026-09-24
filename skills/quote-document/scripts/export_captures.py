#!/usr/bin/env python3
"""Zip everything in ~/.savoya-quoting/ for hand-off when Drive isn't connected.
Usage: export_captures.py [--out ~/Desktop]  → savoya-captures-<user>-<date>.zip"""
import argparse, datetime as dt, json, os, zipfile
ap = argparse.ArgumentParser(); ap.add_argument("--out", default=os.path.expanduser("~/Desktop")); a = ap.parse_args()
root = os.path.expanduser("~/.savoya-quoting")
try: user = json.load(open(os.path.join(root, "config.json"))).get("user", "unknown")
except Exception: user = "unknown"
user = "".join(c for c in user.lower() if c.isalnum()) or "unknown"
dest = os.path.join(a.out, f"savoya-captures-{user}-{dt.date.today()}.zip")
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f); z.write(p, os.path.relpath(p, root))
print(f"Wrote {dest}")
