#!/usr/bin/env python3
"""Explode one or more *.capture.json files into regression fixture directories.
Run from Claude Code during the weekly pass after downloading captures from Drive.

Usage: unpack_capture.py <capture.json|dir> [...] --fixtures evals/fixtures
Each becomes <fixtures>/<slug>/{request.md, raw_quote.json|quote.json, expected.json, capture-meta.json}.
Review expected.json (tighten contains/not_contains) before running regress.py.
"""
import argparse, glob, json, os
ap = argparse.ArgumentParser(); ap.add_argument("paths", nargs="+"); ap.add_argument("--fixtures", required=True)
a = ap.parse_args()
files, fb_only = [], []
for p in a.paths:
    if os.path.isdir(p):
        files += sorted(glob.glob(os.path.join(p, "*.capture.json")))
        caps = {os.path.basename(f).replace(".capture.json", "") for f in files}
        fb_only += [f for f in sorted(glob.glob(os.path.join(p, "*.feedback.json")))
                    if os.path.basename(f).replace(".feedback.json", "") not in caps]
    else:
        files.append(p)
for f in files:
    c = json.load(open(f, encoding="utf-8"))
    d = os.path.join(a.fixtures, c["slug"]); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "request.md"), "w", encoding="utf-8").write(c["request"])
    if c.get("raw_quote"):
        json.dump(c["raw_quote"], open(os.path.join(d, "raw_quote.json"), "w"), indent=1)
    else:
        json.dump(c["quote"], open(os.path.join(d, "quote.json"), "w"), indent=2)
    json.dump(c["expected"], open(os.path.join(d, "expected.json"), "w"), indent=2)
    meta = {k: c.get(k) for k in ("ts", "user", "client", "deliverable", "feedback", "placeholders", "plugin_version", "version")}
    json.dump(meta, open(os.path.join(d, "capture-meta.json"), "w"), indent=2)
    fb = c.get("feedback") or {}
    flag = " ← has feedback" if fb.get("change") else ""
    if fb.get("fixed"):
        flag += " (fixed in session)"
    print(f"  {c['slug']}  ({c.get('user') or 'anon'}, {c.get('deliverable')}){flag}")

for f in fb_only:
    c = json.load(open(f, encoding="utf-8"))
    fb = c.get("feedback") or {}
    note = " ← has feedback" if fb.get("change") else ""
    if fb.get("fixed"):
        note += " (fixed in session)"
    loc = (c.get("full_capture") or {}).get("path")
    print(f"  {c.get('slug')}  [feedback only{', full capture at ' + loc if loc else ''}]{note}")
