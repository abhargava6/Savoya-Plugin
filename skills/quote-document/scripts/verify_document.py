#!/usr/bin/env python3
"""Verify a rendered deliverable against quote.json before it goes to the user.

Catches the failures that have actually happened: a leg dropped by page overflow,
a missing date, internal vocabulary leaking through, totals that don't reconcile,
an unlabeled stop, a cover that didn't render.

Usage:
  verify_document.py quote.json --pdf out.pdf [--email draft.txt] [--strict]

Exit 0 = clean (warnings may still print). Exit 1 = at least one FAIL.
Run it after rendering and before replying. If it fails, fix and re-render —
do not deliver and do not describe the problem as if the user should fix it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

INTERNAL = [
    "rate_id", "rate_record_type", "basis_points", "basis points", "bps",
    "hourly fallback", "No transfer rate found", "label needed", "Stop (label",
    "custom_discount", "temporary_rate_used", "travel_coordination_profile_id",
    "passenger_id", "market_vehicle_count", "estimate_type", "quoteable",
    "value_option", "elevated_option", "aggregate_total", "None", "null",
]
TERMS_SENTINEL = "This is a quoting tool"


def money(c):
    return f"${(c or 0)/100:,.2f}"


def pdf_text(path):
    if not shutil.which("pdftotext"):
        return None
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout


def pdf_pages(path):
    if not shutil.which("pdfinfo"):
        return None
    out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[-1])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--email", default=None)
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    a = ap.parse_args()

    q = json.load(open(a.quote, encoding="utf-8"))
    fails, warns, checks, skipped = [], [], 0, []

    def fail(m):
        fails.append(m)

    def warn(m):
        warns.append(m)

    # ---- quote.json self-consistency
    checks += 1
    sub = sum((l["pricing"]["line_total_cents"] or 0) for l in q["legs"] if not l.get("alternative_of"))
    if sub != q.get("engine_subtotal_cents"):
        fail(f"subtotal mismatch in quote.json: legs sum {money(sub)} vs engine_subtotal {money(q.get('engine_subtotal_cents'))}")
    running = q.get("engine_subtotal_cents") or 0
    for adj in q.get("adjustments", []):
        if adj.get("waived"):
            continue
        running += adj.get("amount_cents") or 0
    checks += 1
    if running != q.get("total_cents"):
        fail(f"total mismatch in quote.json: computed {money(running)} vs total_cents {money(q.get('total_cents'))}")

    checks += 1
    for l in q["legs"]:
        if not l.get("date"):
            warn(f"{l.get('ref') or l.get('key')}: no date — document will show 'Date to be confirmed'")
        for s in l.get("stops", []):
            if s.get("needs_label") or "label needed" in str(s.get("label", "")):
                fail(f"{l.get('ref')}: unlabeled stop '{s.get('label')}' — set it from the resolve result")
        # A bare string here iterates character by character, which printed one letter
        # per line down the whole page and overflowed it. The renderers now tolerate it;
        # this still fails so the quote.json gets corrected rather than quietly patched.
        cn = l.get("client_notes")
        if isinstance(cn, str):
            fail(f"{l.get('ref')}: client_notes is a string, not a list — wrap it: "
                 f'["{cn[:40]}…"]. As a string it renders one character per line.')
        elif cn is not None and not isinstance(cn, list):
            fail(f"{l.get('ref')}: client_notes must be a list of strings, got {type(cn).__name__}")

    # ---- route map and drive times
    # Both of these shipped to a client before: a blank basemap that still embedded,
    # and a drive time silently replaced by a public router that had lost a stop.
    checks += 1
    for l in q["legs"]:
        r = l.get("route") or {}
        if not r:
            continue
        dm = r.get("drive_min")
        stops = [s for s in l.get("stops", []) if not s.get("as_directed")]
        if dm is not None and dm < 1 and len(stops) >= 2:
            fail(f"{l.get('ref')}: drive time of {dm} min across {len(stops)} stops — "
                 f"a stop almost certainly failed to resolve; re-run the route map or drop the times")
        segs = r.get("segments")
        if segs is not None and len(stops) >= 2 and segs < len(stops) - 1:
            fail(f"{l.get('ref')}: route covers {segs} segment(s) but the leg has {len(stops)} stops — "
                 f"the drive time understates the itinerary")

    # Every check above is per leg, and a leg with no distance is individually fine —
    # so a document where half the rows carry miles and half carry an em dash passed
    # all of them. It reached a client that way on a 16-leg job: the public router
    # refused 8 calls, and the defect existed only in the comparison between legs,
    # which nothing was looking at. route_map.py now drops the column rather than
    # half-fill it; this is the backstop for a quote that got here another way.
    checks += 1
    routable = [l for l in q["legs"]
                if not l.get("alternative_of")
                and len([s for s in l.get("stops", []) if not s.get("as_directed")]) >= 2]
    with_dist = [l for l in routable if (l.get("route") or {}).get("distance_mi") is not None]
    if with_dist and len(with_dist) < len(routable):
        missing = [l.get("ref") for l in routable if l not in with_dist]
        fail(f"distance is printed for {len(with_dist)} of {len(routable)} routable legs but "
             f"missing on {', '.join(str(m) for m in missing[:6])}"
             f"{' …' if len(missing) > 6 else ''} — a half-filled distance column reads as a "
             f"broken document. Re-run the route map, or drop distance from every leg.")

    rm = (q.get("route_map") or {}).get("png")
    if rm and rm != "ROUTE_MAP_PNG":
        checks += 1
        if not os.path.exists(rm):
            fail(f"route map missing on disk: {rm}")
        elif (q.get("route_map") or {}).get("style") == "offline":
            # the schematic overview is mostly background by design — that is not the
            # blank-basemap failure, so the uniformity test doesn't apply to it
            pass
        else:
            try:
                from PIL import Image
                im = Image.open(rm).convert("RGB")
                top = max(im.getcolors(maxcolors=10 ** 7))[0]
                share = top / float(im.size[0] * im.size[1])
                if share > 0.80:
                    fail(f"route map is {share:.0%} a single colour — the basemap tiles didn't load; "
                         f"drop the map rather than sending a blank panel")
            except ImportError:
                warn("Pillow unavailable — could not check the route map for a blank basemap")

    # ---- PDF
    if a.pdf:
        if not os.path.exists(a.pdf):
            fail(f"PDF not found: {a.pdf}")
        else:
            pages = pdf_pages(a.pdf)
            txt = pdf_text(a.pdf)
            size = os.path.getsize(a.pdf)
            checks += 1
            if size < 50_000:
                warn(f"PDF is only {size//1024} KB — cover may not have rendered")
            if txt is None:
                skipped.append("PDF text checks (pdftotext not installed — brew install poppler)")
            else:
                flat = re.sub(r"\s+", " ", txt)
                checks += 1
                if money(q["total_cents"]) not in flat:
                    fail(f"total {money(q['total_cents'])} does not appear in the PDF")
                checks += 1
                for l in q["legs"]:
                    if l.get("alternative_of"):
                        continue
                    lt = money(l["pricing"]["line_total_cents"])
                    if lt not in flat:
                        fail(f"{l.get('ref')} line total {lt} missing from the PDF — likely dropped by page overflow")
                checks += 1
                refs = [l.get("ref") for l in q["legs"] if l.get("ref") and not l.get("alternative_of")]
                for r in refs:
                    if not re.search(rf"\b{re.escape(r)}\b", flat):
                        fail(f"reference {r} missing from the PDF")
                checks += 1
                if TERMS_SENTINEL not in flat:
                    fail("terms block missing from the PDF")
                checks += 1
                # The surcharge is market-scoped — 5% in most, 10% in London and others —
                # and terms.md templates the live figure. Matching a hardcoded "5%" here
                # false-failed every 10% market on a perfectly correct document.
                fuel_adj = next((x for x in q.get("adjustments", [])
                                 if "fuel" in (x.get("label") or "").lower() and not x.get("waived")), None)
                fuel_line = fuel_adj is not None
                fuel_bullet = re.search(r"fuel surcharge of\s*([\d.]+)\s*%", flat, re.I)
                if fuel_line and not fuel_bullet:
                    fail("a fuel surcharge is on the quote but the fuel terms bullet is missing")
                if fuel_bullet and not fuel_line:
                    fail("the fuel terms bullet appears but no fuel line is on the quote")
                if fuel_line and fuel_bullet:
                    want = fuel_adj.get("value")
                    got = float(fuel_bullet.group(1))
                    if want is not None and abs(float(want) - got) > 0.01:
                        fail(f"fuel terms bullet says {got}% but the quote's fuel line is {want}%")
                checks += 1
                for bad in INTERNAL:
                    if bad in ("None", "null"):
                        if re.search(rf"\b{bad}\b", flat):
                            warn(f"the literal '{bad}' appears in the PDF — a field rendered empty")
                        continue
                    if bad.lower() in flat.lower():
                        fail(f"internal vocabulary in the PDF: '{bad}'")
                # route page: if a map was requested, every leg must appear in the route table too
                if q.get("route_map"):
                    checks += 1
                    after = flat.split("Itinerary map", 1)[-1] if "Itinerary map" in flat else ""
                    for l in q["legs"]:
                        if l.get("alternative_of") or not l.get("ref"):
                            continue
                        if not re.search(rf"\b{re.escape(l['ref'])}\b", after):
                            fail(f"{l['ref']} missing from the route table — the route page is clipping rows")
                checks += 1
                for l in q["legs"]:
                    if any(s.get("kind") == "airport" and (s.get("flight") or {}).get("tbd") for s in l.get("stops", [])):
                        if "to be confirmed" not in flat.lower():
                            fail(f"{l.get('ref')} has a TBD flight but the PDF doesn't say so")
                        break
            checks += 1
            if pages and pages > 6:
                warn(f"PDF is {pages} pages — check it reads well")

    # ---- email
    if a.email and os.path.exists(a.email):
        body = open(a.email, encoding="utf-8").read()
        checks += 1
        if money(q["total_cents"]) not in body:
            fail(f"total {money(q['total_cents'])} does not appear in the email copy")
        checks += 1
        for bad in INTERNAL:
            if bad in ("None", "null"):
                continue
            if bad.lower() in body.lower():
                fail(f"internal vocabulary in the email: '{bad}'")

    for w in warns:
        print(f"  ⚠ {w}")
    for f in fails:
        print(f"  ✗ {f}")
    for s_ in skipped:
        print(f"  – skipped: {s_}")
    ok = not fails and (not warns or not a.strict)
    if not ok:
        verdict, code = "FAIL", 1
    elif skipped:
        verdict, code = "PARTIAL", 2
    else:
        verdict, code = "PASS", 0
    print(f"{verdict} — {checks} checks run, {len(fails)} failure(s), {len(warns)} warning(s), {len(skipped)} group(s) skipped")
    if code == 2:
        print("  PARTIAL means the document could not be fully verified — say so when you deliver it.")
    sys.exit(code)


if __name__ == "__main__":
    main()
