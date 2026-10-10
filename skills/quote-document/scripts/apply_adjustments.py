#!/usr/bin/env python3
"""Apply document-level adjustments to quote.json and recompute totals.

The engine subtotal is never changed. Adjustments apply IN LIST ORDER on the
running total. Document PERCENTAGE lines are refused (C2): percentages belong to
Core. Flat document lines are still applied, on top of Core's total.
Leg-scoped adjustments (applies_to) use that leg's total as the base instead.

Usage:
  apply_adjustments.py quote.json --add "On-site coordinator|flat|150|offsite_9_15_minibus"
  apply_adjustments.py quote.json --remove "Fuel surcharge"
  apply_adjustments.py quote.json --clear
  apply_adjustments.py quote.json            # just recompute
"""
import argparse
import json
import os
import re
import sys

TERMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "terms.md")


def fuel_pct(quote):
    """The live fuel surcharge percentage, or None. Comes from the engine when it set one."""
    for a in quote.get("adjustments", []):
        if "fuel" in (a.get("label") or "").lower() and not a.get("waived"):
            return abs(a.get("value") or 0) or None
    return None


def has_fuel_surcharge(quote):
    return fuel_pct(quote) is not None


def build_terms(quote):
    """Terms from assets/terms.md; `[if:fuel_surcharge]` bullets only when a live fuel line exists."""
    out = []
    try:
        lines = open(TERMS_PATH, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return quote.get("terms", [])
    fuel = has_fuel_surcharge(quote)
    commission = quote.get("commission_pct")
    for line in lines:
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        m = re.match(r"\[if:(\w+)\]\s*(.*)", body)
        if m:
            if m.group(1) == "fuel_surcharge" and fuel:
                pct = fuel_pct(quote)
                out.append(m.group(2).replace("{pct}", f"{pct:g}") if pct else m.group(2).replace("{pct}", "5"))
            # A recorded commission rate, stated and never calculated. It names no
            # beneficiary: the commission may be earned by the client or by an agency
            # acting for them, and a client document should not assert which.
            elif m.group(1) == "commission" and commission:
                out.append(m.group(2).replace("{pct}", f"{float(commission):g}"))
            continue
        out.append(body)
    return out


def parse_add(spec):
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) < 3:
        sys.exit(f"Bad --add spec '{spec}'. Use label|percent|5 or label|flat|150[|leg_key]")
    label, kind, value = parts[0], parts[1].lower(), parts[2]
    if kind not in ("percent", "flat"):
        sys.exit(f"Adjustment type must be percent or flat, got '{kind}'")
    try:
        value = float(value)
    except ValueError:
        sys.exit(f"Adjustment value must be numeric, got '{value}'")
    applies_to = parts[3] if len(parts) > 3 and parts[3] else None
    return {"label": label, "type": kind, "value": value, "applies_to": applies_to}


def option_total(quote, legs_subset):
    """Total for a set of legs (used for Option B) — from Core's amounts, not ours.

    This applied each percentage to a RUNNING total, so two discounts compounded:
    30% then 5% gives 0.665 where Core's additive 35% gives 0.65, and Option B came out
    about 2.3% high. A live London/Sicily/Milan quote on 10 Oct 2026 hit it and the
    session pinned the figure to Core's aggregate by hand.

    It is the same defect C2 was written about — "percentages compounded against a
    running subtotal" — and it survived in here for a structural reason worth keeping in
    mind. Option A never computes a percentage: normalize pins each engine line's amount
    at Core's own granularity (C5), the lines are summed, and C4 then refuses to render
    if the result misses Core's aggregate. Option B has no Core aggregate to be checked
    against, because Core never priced that leg combination as a package. So the one
    total with no fail-closed check behind it was also the only one still doing its own
    arithmetic.

    The fix is the same as everywhere else: each leg already carries
    `engine_net_line_cents`, which is Core's net for that leg with every engine
    percentage already in it. Summing those is Core's number, not a reconstruction of it.
    Document FLAT lines still apply on top — a real amount a CSM was told — and a
    leg-scoped one only when its leg is in this option.
    """
    sub = sum((l["pricing"]["line_total_cents"] or 0) for l in legs_subset)
    keys = {l.get("key") for l in legs_subset}
    nets = [l.get("engine_net_line_cents") for l in legs_subset]

    if nets and all(n is not None for n in nets):
        total = sum(int(n) for n in nets)
    else:
        # No engine figures (a pre-0.23 quote.json, or one assembled by hand). Sum the
        # global percentages and apply them ONCE, the way Core does and the way
        # render_print's rate card does — never one after another.
        disc = sum(a["value"] for a in quote.get("adjustments", [])
                   if a["type"] == "percent" and not a.get("applies_to")
                   and not a.get("waived") and a["value"] < 0)
        sur = sum(a["value"] for a in quote.get("adjustments", [])
                  if a["type"] == "percent" and not a.get("applies_to")
                  and not a.get("waived") and a["value"] > 0)
        total = round(round(sub * (1 + disc / 100.0)) * (1 + sur / 100.0))
        print(f"WARNING: Option B has no per-leg engine amounts, so its total is derived "
              f"from the summed percentages ({disc:g}% then {sur:g}%) rather than taken "
              f"from Core. Re-normalize from a fresh response to pin it.", file=sys.stderr)

    for adj in quote.get("adjustments", []):
        if adj.get("waived") or adj["type"] == "percent":
            continue
        # engine percentages are already inside engine_net_line_cents; only a document
        # flat line is added here, and a leg-scoped one only for legs in this option
        if adj.get("source") == "engine":
            continue
        if adj.get("applies_to") and adj["applies_to"] not in keys:
            continue
        total += round(adj["value"] * 100)
    return sub, int(total)


def recompute(quote):
    legs = {l["key"]: l for l in quote["legs"]}
    subtotal = sum((l["pricing"]["line_total_cents"] or 0) for l in quote["legs"]
                   if not l.get("alternative_of"))
    quote["engine_subtotal_cents"] = subtotal
    total = subtotal
    for adj in quote.get("adjustments", []):
        base = total
        if adj.get("applies_to"):
            leg = legs.get(adj["applies_to"])
            if not leg:
                sys.exit(f"Adjustment '{adj['label']}' applies_to unknown leg '{adj['applies_to']}'")
            base = leg["pricing"]["line_total_cents"] or 0
        if adj.get("waived"):
            adj["amount_cents"] = 0
            continue
        if adj.get("source") != "engine" and adj["type"] == "percent":
            # C2 — no document-sourced PERCENTAGE lines. This is where local money math
            # lived: percentages compounded against a running subtotal, in list order, so a
            # 25% discount followed by a 5% surcharge depended on which was entered first.
            #
            # Nothing legitimate calls it any more. The discount is a Core re-quote (C1,
            # temporary_discount), fuel is Core's and no longer adjustable (C3), and a
            # greeter is a priced Core unit (D1). A flat line is still allowed — a fallback
            # on-site cost in a market with no greeter rate is a real amount a CSM was told,
            # not a percentage of Savoya's number.
            sys.exit(
                f"REFUSING: '{adj['label']}' is a {adj['value']}% document line.\n"
                "Percentages are not applied here any more — they are Savoya's to compute.\n"
                "  • an additional discount → re-quote with calculate_temporary_quote_units\n"
                "    and temporary_discount.basis_points, then rebuild from that response\n"
                "  • the fuel surcharge → Core's, for the market; it is not adjustable here\n"
                "  • a greeter or on-site coordinator → price it as a Savoya quote unit\n"
                "A flat amount is still fine: --add \"Label|flat|<dollars>\".")
        if adj.get("source") == "engine" and adj.get("amount_cents_fixed") is not None:
            # C5 — an engine line's amount is Core's, not ours. normalize_quote computes it
            # per unit at the granularity Core rounds at (per hour, per vehicle) and pins it
            # here. Re-deriving it as a percentage of a running subtotal is what produced a
            # 30-cent gap on a 5-vehicle Boston job, which the old code then hid by quietly
            # adding the difference to this very line.
            amount = adj["amount_cents_fixed"]
        elif adj["type"] == "percent":
            amount = round(base * adj["value"] / 100.0)
        else:
            amount = round(adj["value"] * 100)
        adj["amount_cents"] = int(amount)
        total += adj["amount_cents"]
    quote["total_cents"] = int(total)

    # C4 — FAIL CLOSED. This used to absorb any penny-level gap between our reconstruction
    # and the engine total into the last engine-sourced line, so the document always
    # reconciled. The contract forbids it: "If normalized data and the raw MCP result
    # disagree, fail closed. Do not repair the difference with arithmetic."
    #
    # The gap was real, not noise. Core rounds the effective rate PER HOUR and multiplies;
    # we were applying the same percentages to a subtotal. On a 5-vehicle Boston job that
    # is 30 cents — invisible on $9,355, and exactly the kind of difference that hides a
    # real one. Absorbing it also meant the engine line printed an amount that was not the
    # percentage it claimed.
    #
    # A document line does not excuse the check, it just moves what is compared.
    #
    # This used to run only when NO document line had been added, on the reasoning that
    # the total is then deliberately no longer the engine's. True of the total; not true
    # of the engine's share of it. The effect was that adding one flat line switched off
    # the only fail-closed money check in the plugin — and on a live Irvine quote on
    # 10 Oct 2026 it did exactly that: a $200 on-site coordinator line meant the quote
    # rendered with no comparison against Savoya's aggregate at all. That quote was also
    # built from a hand-transcribed engine response, which is precisely when the check
    # matters most.
    #
    # So the document lines are subtracted back out and the ENGINE portion is compared.
    # Only flat lines can be document-sourced (C2 refuses document percentages), so the
    # subtraction is exact.
    # A WAIVED engine line is the other adjustment to make before comparing. Core's
    # aggregate still contains it — the waiver is ours, recorded so the booking carries
    # the same waiver in Savoya — so the document total is legitimately short by exactly
    # that amount. Without adding it back, waiving anything made this refuse to render,
    # which made `--waive` unusable: on the Irvine quote, waiving the fuel surcharge
    # produced a $58.50 "gap" that was the waiver itself. That was true before the
    # document-line fix above and had no guard on it at all.
    eng_total = quote.get("engine_total_cents")
    eng_lines = [a for a in quote.get("adjustments", []) if a.get("source") == "engine" and not a.get("waived")]
    doc_lines = [a for a in quote.get("adjustments", []) if a.get("source") != "engine" and not a.get("waived")]
    waived_eng = [a for a in quote.get("adjustments", []) if a.get("source") == "engine" and a.get("waived")]
    engine_share = (quote["total_cents"]
                    - sum(int(a.get("amount_cents") or 0) for a in doc_lines)
                    + sum(int(a.get("amount_cents_fixed") or 0) for a in waived_eng))
    if eng_total and eng_lines and engine_share != eng_total:
        gap = engine_share - eng_total
        sys.exit(
            "REFUSING TO RENDER: this document's total does not match Savoya's.\n"
            f"  Savoya quoted   {eng_total/100:,.2f}\n"
            f"  This document   {engine_share/100:,.2f}"
            + (f"  (the engine share of {quote['total_cents']/100:,.2f}, "
               f"after {len(doc_lines)} added line{'s' if len(doc_lines) != 1 else ''})"
               if doc_lines else "") + "\n"
            f"  Difference      {gap/100:+,.2f}\n"
            "\nThe numbers on a client quote have to be Savoya's, so this stops here rather\n"
            "than papering over the gap. Re-run the quote in intake and rebuild the document\n"
            "from the fresh response. If it happens again on the same quote, that is a\n"
            "Savoya-side report, not a plugin one — send the quote reference to engineering.")

    quote["terms"] = build_terms(quote)
    alts = [l for l in quote["legs"] if l.get("alternative_of")]
    if alts:
        replaced = {l["alternative_of"] for l in alts}
        carried = [l for l in quote["legs"] if not l.get("alternative_of") and l["key"] not in replaced]
        alt_sub = sum((l["pricing"]["line_total_cents"] or 0) for l in alts)
        car_sub = sum((l["pricing"]["line_total_cents"] or 0) for l in carried)
        _, tot = option_total(quote, alts + carried)
        quote["option_b"] = {"alt_subtotal_cents": alt_sub, "carried_subtotal_cents": car_sub,
                             "carried_refs": [l.get("ref") for l in carried],
                             "subtotal_cents": alt_sub + car_sub, "total_cents": tot}
    else:
        quote.pop("option_b", None)
    return quote


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--commission-pct", dest="commission_pct", default=None,
                    help="commission rate recorded for this quote, from the "
                         "commission_pct question: a percentage, or 'none'. It is STATED "
                         "on the documents and changes no arithmetic — it is set here "
                         "rather than in a setter because this script owns the terms "
                         "block, so the rate and the terms bullet land in one call and "
                         "cannot get out of order.")
    ap.add_argument("--waive", action="append", default=[],
                    help="Waive an engine-applied line (e.g. 'Fuel surcharge'): kept for audit, amount 0, not shown")
    args = ap.parse_args()

    with open(args.quote, encoding="utf-8") as f:
        quote = json.load(f)

    if args.commission_pct is not None:
        raw = str(args.commission_pct).strip().lower().rstrip("%").strip()
        if raw in ("none", "no", "0", ""):
            quote.pop("commission_pct", None)
        else:
            try:
                pct = float(raw)
            except ValueError:
                sys.exit(f"--commission-pct wants a percentage or 'none', not "
                         f"{args.commission_pct!r}")
            if not 0 < pct <= 100:
                sys.exit(f"--commission-pct {pct:g} is outside 0–100%. A commission is a "
                         f"share of the program, and a rate this far out is a typo rather "
                         f"than a deal.")
            quote["commission_pct"] = pct

    if args.clear:
        quote["adjustments"] = [a for a in quote.get("adjustments", []) if a.get("source") == "engine"]
    for label in args.remove:
        hit = next((a for a in quote.get("adjustments", []) if a["label"] == label), None)
        if hit and hit.get("source") == "engine":
            sys.exit(f"'{label}' was applied by the engine. Use --waive \"{label}\" instead so the waiver is recorded; "
                     f"the booking will need the same waiver applied in Savoya.")
        quote["adjustments"] = [a for a in quote.get("adjustments", []) if a["label"] != label]
    for label in args.waive:
        hit = next((a for a in quote.get("adjustments", []) if a["label"] == label), None)
        if not hit:
            sys.exit(f"No adjustment labeled '{label}' to waive")
        hit["waived"] = True
        quote.setdefault("internal", {}).setdefault("notes", []).append(
            f"{label} waived in document ({hit['type']} {hit['value']:g}); engine total still includes it — apply the waiver in Savoya at booking.")
    for spec in args.add:
        adj = parse_add(spec)
        quote.setdefault("adjustments", [])
        quote["adjustments"] = [a for a in quote["adjustments"] if a["label"] != adj["label"]]
        quote["adjustments"].append(adj)

    quote["adjustments"] = sorted(quote.get("adjustments", []), key=lambda a: 0 if a.get("source") == "engine" else 1)
    quote = recompute(quote)
    with open(args.quote, "w", encoding="utf-8") as f:
        json.dump(quote, f, indent=2)

    print(f"Engine subtotal  ${quote['engine_subtotal_cents']/100:,.2f}")
    for a in quote["adjustments"]:
        if a.get("waived"):
            print(f"  ~ {a['label']}: waived"); continue
        sign = "-" if a["amount_cents"] < 0 else "+"
        scope = f" ({a['applies_to']})" if a.get("applies_to") else ""
        print(f"  {sign} {a['label']}{scope}: ${abs(a['amount_cents'])/100:,.2f}")
    print(f"Total            ${quote['total_cents']/100:,.2f}")


if __name__ == "__main__":
    main()
