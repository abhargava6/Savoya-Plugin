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
    "rate_id",
    "rate_record_type",
    "basis_points",
    "basis points",
    "bps",
    "hourly fallback",
    "No transfer rate found",
    "label needed",
    "Stop (label",
    "custom_discount",
    "temporary_rate_used",
    "travel_coordination_profile_id",
    "passenger_id",
    "market_vehicle_count",
    "estimate_type",
    "quoteable",
    "value_option",
    "elevated_option",
    "aggregate_total",
    "None",
    "null",
]
TERMS_SENTINEL = "This is a quoting tool"


def money(c):
    return f"${(c or 0)/100:,.2f}"


def pdf_text(path):
    if not shutil.which("pdftotext"):
        return None
    return subprocess.run(
        ["pdftotext", "-layout", path, "-"], capture_output=True, text=True
    ).stdout


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
    ap.add_argument(
        "--raw",
        default=None,
        help="authoritative raw_quote.json; defaults to quote.internal.raw_quote_path",
    )
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

    # ---- compare presentation values directly with the authoritative Core result.
    # Core owns aggregate arithmetic; line totals are deliberately not summed here.
    raw_path = a.raw or (q.get("internal") or {}).get("raw_quote_path")
    checks += 1
    if not raw_path or not os.path.exists(raw_path):
        fail("authoritative raw_quote.json is unavailable for monetary verification")
    else:
        raw = json.load(open(raw_path, encoding="utf-8"))
        if q.get("total_cents") != raw.get("aggregate_total"):
            fail(
                f"aggregate total changed: document {money(q.get('total_cents'))} vs Core {money(raw.get('aggregate_total'))}"
            )
        raw_units = {unit.get("key"): unit for unit in raw.get("quote_units") or []}
        if set(raw_units) != {leg.get("key") for leg in q.get("legs") or []}:
            fail("document units do not exactly match raw_quote.json")
        for leg in q.get("legs") or []:
            unit = raw_units.get(leg.get("key")) or {}
            comparisons = {
                "quantity": (
                    (leg.get("vehicle") or {}).get("quantity"),
                    unit.get("quantity"),
                ),
                "unit total": (
                    (leg.get("pricing") or {}).get("unit_total_cents"),
                    unit.get("unit_total"),
                ),
                "line total": (
                    (leg.get("pricing") or {}).get("line_total_cents"),
                    unit.get("line_total"),
                ),
                "vehicle": (
                    (leg.get("vehicle") or {}).get("id"),
                    (unit.get("vehicle_type") or {}).get("id"),
                ),
            }
            for label, (shown, authoritative) in comparisons.items():
                if shown != authoritative:
                    fail(
                        f"{leg.get('key')} {label} changed: document {shown!r} vs Core {authoritative!r}"
                    )

    checks += 1
    for l in q["legs"]:
        if not l.get("date"):
            warn(
                f"{l.get('ref') or l.get('key')}: no date — document will show 'Date to be confirmed'"
            )
        for s in l.get("stops", []):
            if s.get("needs_label") or "label needed" in str(s.get("label", "")):
                fail(
                    f"{l.get('ref')}: unlabeled stop '{s.get('label')}' — set it from the resolve result"
                )
        # A bare string here iterates character by character, which printed one letter
        # per line down the whole page and overflowed it. The renderers now tolerate it;
        # this still fails so the quote.json gets corrected rather than quietly patched.
        cn = l.get("client_notes")
        if isinstance(cn, str):
            fail(
                f"{l.get('ref')}: client_notes is a string, not a list — wrap it: "
                f'["{cn[:40]}…"]. As a string it renders one character per line.'
            )
        elif cn is not None and not isinstance(cn, list):
            fail(
                f"{l.get('ref')}: client_notes must be a list of strings, got {type(cn).__name__}"
            )

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
            fail(
                f"{l.get('ref')}: drive time of {dm} min across {len(stops)} stops — "
                f"a stop almost certainly failed to resolve; re-run the route map or drop the times"
            )
        segs = r.get("segments")
        if segs is not None and len(stops) >= 2 and segs < len(stops) - 1:
            fail(
                f"{l.get('ref')}: route covers {segs} segment(s) but the leg has {len(stops)} stops — "
                f"the drive time understates the itinerary"
            )

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
                top = max(im.getcolors(maxcolors=10**7))[0]
                share = top / float(im.size[0] * im.size[1])
                if share > 0.80:
                    fail(
                        f"route map is {share:.0%} a single colour — the basemap tiles didn't load; "
                        f"drop the map rather than sending a blank panel"
                    )
            except ImportError:
                warn(
                    "Pillow unavailable — could not check the route map for a blank basemap"
                )

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
                skipped.append(
                    "PDF text checks (pdftotext not installed — brew install poppler)"
                )
            else:
                flat = re.sub(r"\s+", " ", txt)
                checks += 1
                if money(q["total_cents"]) not in flat:
                    fail(f"total {money(q['total_cents'])} does not appear in the PDF")
                checks += 1
                for l in q["legs"]:
                    lt = money(l["pricing"]["line_total_cents"])
                    if lt not in flat:
                        fail(
                            f"{l.get('ref')} line total {lt} missing from the PDF — likely dropped by page overflow"
                        )
                checks += 1
                refs = [l.get("ref") for l in q["legs"] if l.get("ref")]
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
                fuel_bps = (q.get("adjustments") or {}).get(
                    "fuel_surcharge_basis_points"
                )
                fuel_line = fuel_bps is not None and fuel_bps != 0
                fuel_bullet = re.search(r"fuel surcharge of\s*([\d.]+)\s*%", flat, re.I)
                if fuel_line and not fuel_bullet:
                    fail(
                        "a fuel surcharge is on the quote but the fuel terms bullet is missing"
                    )
                if fuel_bullet and not fuel_line:
                    fail(
                        "the fuel terms bullet appears but no fuel line is on the quote"
                    )
                if fuel_line and fuel_bullet:
                    want = fuel_bps / 100.0
                    got = float(fuel_bullet.group(1))
                    if want is not None and abs(float(want) - got) > 0.01:
                        fail(
                            f"fuel terms bullet says {got}% but the quote's fuel line is {want}%"
                        )
                checks += 1
                for bad in INTERNAL:
                    if bad in ("None", "null"):
                        if re.search(rf"\b{bad}\b", flat):
                            warn(
                                f"the literal '{bad}' appears in the PDF — a field rendered empty"
                            )
                        continue
                    if bad.lower() in flat.lower():
                        fail(f"internal vocabulary in the PDF: '{bad}'")
                # route page: if a map was requested, every leg must appear in the route table too
                if q.get("route_map"):
                    checks += 1
                    after = (
                        flat.split("Itinerary map", 1)[-1]
                        if "Itinerary map" in flat
                        else ""
                    )
                    for l in q["legs"]:
                        if not l.get("ref"):
                            continue
                        if not re.search(rf"\b{re.escape(l['ref'])}\b", after):
                            fail(
                                f"{l['ref']} missing from the route table — the route page is clipping rows"
                            )
                checks += 1
                for l in q["legs"]:
                    if any(
                        s.get("kind") == "airport"
                        and (s.get("flight") or {}).get("tbd")
                        for s in l.get("stops", [])
                    ):
                        if "to be confirmed" not in flat.lower():
                            fail(
                                f"{l.get('ref')} has a TBD flight but the PDF doesn't say so"
                            )
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
    print(
        f"{verdict} — {checks} checks run, {len(fails)} failure(s), {len(warns)} warning(s), {len(skipped)} group(s) skipped"
    )
    if code == 2:
        print(
            "  PARTIAL means the document could not be fully verified — say so when you deliver it."
        )
    sys.exit(code)


if __name__ == "__main__":
    main()
