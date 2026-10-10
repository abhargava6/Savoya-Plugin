#!/usr/bin/env python3
"""Explode one or more *.capture.json files into regression fixture directories.
Run from Claude Code during the weekly pass after downloading captures from Drive.

Usage: unpack_capture.py <capture.json|dir> [...] --fixtures evals/fixtures
Each becomes <fixtures>/<slug>/{request.md, raw_quote.json|quote.json, expected.json, capture-meta.json}.
Review expected.json (tighten contains/not_contains) before running regress.py.
"""
import argparse, base64, glob, gzip, json, os, re
ap = argparse.ArgumentParser(); ap.add_argument("paths", nargs="+"); ap.add_argument("--fixtures", required=True)
a = ap.parse_args()
files, fb_only = [], []
for p in a.paths:
    if os.path.isdir(p):
        files += sorted(glob.glob(os.path.join(p, "*.capture.json")))
        # Since 0.25 the full capture is uploaded compressed, so the Drive folder holds
        # `<slug>.capture.json.gz.b64` and usually no plain `.capture.json` at all. A
        # glob that misses it would silently fall back to the small feedback file and
        # drop the raw engine response -- the whole reason a capture exists.
        plain = {os.path.basename(f)[:-len(".capture.json")] for f in files}
        for f in sorted(glob.glob(os.path.join(p, "*.capture.json.gz.b64"))):
            if os.path.basename(f)[:-len(".capture.json.gz.b64")] not in plain:
                files.append(f)
        caps = {re.sub(r"\.capture\.json(\.gz\.b64)?$", "", os.path.basename(f))
                for f in files}
        # Three kinds of record can be in the folder for one quote, in decreasing
        # richness: the full capture, the post-feedback `<slug>.feedback.json`, and the
        # delivery-time `<slug>.feedback.snapshot.json`. Take the best one per slug and
        # ignore the rest. The snapshot must be considered rather than skipped — it is
        # uploaded for every delivered document, so a quote whose session never came
        # back for feedback exists in the folder *only* as a snapshot, and a glob for
        # `*.feedback.json` does not match it.
        best = {}
        for f in sorted(glob.glob(os.path.join(p, "*.feedback*.json"))):
            b = os.path.basename(f)
            if b.endswith(".feedback.snapshot.json"):
                slug, rank = b[:-len(".feedback.snapshot.json")], 1
            elif b.endswith(".feedback.json"):
                slug, rank = b[:-len(".feedback.json")], 2
            else:
                continue
            if slug in caps:
                continue
            if rank >= best.get(slug, (0, None))[0]:
                best[slug] = (rank, f)
        fb_only += [f for _, f in sorted(best.values(), key=lambda t: t[1])]
    else:
        files.append(p)
def read_capture(path):
    """A capture file, plain or compressed.

    The envelope is JSON so the weekly pass can read the header without decompressing;
    `data` is the gzipped capture, base64'd because Drive's create_file takes text.
    """
    c = json.load(open(path, encoding="utf-8"))
    if c.get("encoding") == "gzip+base64":
        inner = json.loads(gzip.decompress(base64.b64decode(c["data"])).decode("utf-8"))
        raw = c.get("raw_bytes")
        if raw and len(json.dumps(inner, separators=(",", ":"), ensure_ascii=False).encode()) < raw * 0.5:
            print(f"  WARNING: {os.path.basename(path)} decompressed to much less than "
                  f"the {raw} bytes it claims; it may be truncated")
        return inner
    return c


for f in files:
    c = read_capture(f)
    d = os.path.join(a.fixtures, c["slug"]); os.makedirs(d, exist_ok=True)
    # `--request` is deliberately optional on the capture: node K's documented fallback
    # (a quote brought in from elsewhere) has no handoff and therefore no request at all,
    # and making it mandatory used to crash the capture exactly when a session had most
    # to report. The unpacker has to tolerate the same absence, or it crashes on the
    # captures that matter most instead.
    open(os.path.join(d, "request.md"), "w", encoding="utf-8").write(
        c.get("request") or f"<!-- no request recorded: {c.get('request_missing') or 'unknown'} -->\n")
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
