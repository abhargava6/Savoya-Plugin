#!/usr/bin/env python3
"""Normalize a Savoya engine quote result into canonical quote.json.

Accepts the JSON returned by calculate_quote_units,
calculate_temporary_quote_units, or a single option from generate_quote_options.

Usage:
  normalize_quote.py raw_quote.json quote.json --client "Yerdle" [--prepared-by NAME]
      [--select key1,key2] [--title TITLE] [--valid-days 7]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The ONE Core warning we suppress, and only when the unit actually priced. We send no
# passenger_id unless the user named one, so Core attaching an eligible passenger to the
# unsaved calculation is the expected path, not an exception — and it repeats on every
# unit, every option and the aggregate.
#
# A list of one, matched by substring, with the condition attached. Every other warning
# Core sends reaches internal.warnings, including one we don't recognise.
#
# The same string lives in quote-intake/scripts/handoff.py. regress.py asserts the two are
# identical, so the duplication cannot drift.
SUPPRESSED_WARNING = "No passenger was selected"
TERMS_PATH = os.path.join(HERE, "..", "assets", "terms.md")


def load_terms():
    terms = []
    try:
        with open(TERMS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- "):
                    terms.append(line[2:])
    except FileNotFoundError:
        pass
    return terms


def pick_option(unit):
    """Return the vehicle option to use for a unit.
    Exact path (calculate_quote_units / generate_quote_options result): the unit itself
    carries the chosen vehicle, quantity and pricing_summary."""
    if unit.get("pricing_summary") and unit.get("vehicle_type"):
        return unit
    if unit.get("value_option"):
        return unit["value_option"]
    opts = unit.get("vehicle_options") or []
    priced = [o for o in opts if o.get("quoteable")]
    if not priced:
        return None
    return min(priced, key=lambda o: o.get("line_total", 0))


def stop_label(stop, presentation_stop):
    """Best-effort client label for a stop. Flags 'Stop N' placeholders."""
    if stop.get("name"):
        return stop["name"], False
    # exact path: airport stops carry display_name ("BOS - Boston Logan International")
    if stop.get("display_name") and not str(stop["display_name"]).startswith("Stop "):
        return stop["display_name"], False
    if presentation_stop and presentation_stop.get("label") and not presentation_stop["label"].startswith("Stop "):
        return presentation_stop["label"], False
    if is_airport(stop):
        return "Airport (label needed)", True
    if stop.get("as_directed"):
        city = (stop.get("service_area") or {}).get("name", "").split("/")[0].split(",")[0].strip()
        return f"As directed — {city}" if city else "As directed", False
    return "Stop (label needed)", True


def is_airport(stop):
    """Is this stop an airport, in EITHER response shape?

    The connector moved airport identification. It used to arrive as a top-level
    `airport` object on the stop ({"airport": {"id": 4655910}}); current responses carry
    no such key and identify the airport through `location.type == "airport"` instead.

    Reading only the old shape made every airport stop normalize as kind "address" and
    DROPPED the flight object with it — so the "flight time to be confirmed" disclosure
    silently stopped appearing on client documents. Found by re-capturing a fixture
    against the live MCP; invisible before, because the fixture carried the old shape.

    Both shapes are accepted: an old capture must keep working, and the suite still holds
    fixtures in both."""
    if stop.get("airport"):
        return True
    return ((stop.get("location") or {}).get("type") == "airport"
            or stop.get("stop_type") == "airport")


def normalize_stop(stop, presentation_stop):
    label, needs_label = stop_label(stop, presentation_stop)
    out = {"label": label}
    if stop.get("address"):
        out["address"] = stop["address"]
    if is_airport(stop):
        out["kind"] = "airport"
        fl = stop.get("flight") or {}
        out["flight"] = {
            "tbd": bool(fl.get("commercial_tbd")),
            "type": fl.get("flight_type"),
            "scheduled_time": fl.get("scheduled_time"),
        }
    else:
        out["kind"] = "address"
    pos = stop.get("position") or {}
    if pos.get("latitude") is not None and pos.get("longitude") is not None:
        out["lat"], out["lon"] = pos["latitude"], pos["longitude"]
    if stop.get("as_directed"):
        out["kind"] = "as_directed"
        out["as_directed"] = True
    if stop.get("duration"):
        out["wait_hours"] = stop["duration"]
    if needs_label:
        out["needs_label"] = True
    return out


def normalize_unit(unit, presentation_unit):
    opt = pick_option(unit)
    if not opt:
        return None, [f"{unit.get('key')}: no quoteable vehicle option"]
    ps = opt.get("pricing_summary", {})
    rate = ps.get("rate", {})
    pres_stops = (presentation_unit or {}).get("stops") or []
    stops = []
    for i, s in enumerate(unit.get("stops", [])):
        stops.append(normalize_stop(s, pres_stops[i] if i < len(pres_stops) else None))
    vt = opt.get("vehicle_type", {})
    adj = ps.get("adjustments") or {}
    std_rate = rate.get("base_rate_amount") or rate.get("rate_amount_before_temporary_discount")
    eff_rate = rate.get("effective_rate_amount") or opt.get("effective_rate_amount")
    bps = adj.get("discount_basis_points") or adj.get("custom_discount_basis_points") or 0
    engine_discount_pct = None
    if bps and std_rate and eff_rate and std_rate > eff_rate:
        engine_discount_pct = bps / 100.0
    engine_fuel_pct = (adj.get("fuel_surcharge_basis_points") or 0) / 100.0 or None
    engine_handling_pct = (adj.get("special_handling_basis_points") or 0) / 100.0 or None
    service_area = next((s.get("service_area", {}).get("name") for s in unit.get("stops", []) if s.get("service_area")), None)
    leg = {
        "key": unit.get("key"),
        "service_area": service_area,
        "label": unit.get("label") or unit.get("key"),
        "date": unit.get("pickup_date") or (presentation_unit or {}).get("date"),
        "passenger_count": unit.get("passenger_count") or ps.get("calculation", {}).get("passenger_count"),
        "vehicle": {
            "name": vt.get("name"),
            "capacity": vt.get("capacity"),
            "quantity": opt.get("quantity") or ps.get("calculation", {}).get("quantity") or 1,
        },
        "stops": stops,
        "pricing": {
            "method": ps.get("pricing_method"),
            "rate_cents": std_rate if engine_discount_pct else eff_rate,
            "billable_hours": opt.get("billable_hours") or ps.get("calculation", {}).get("billable_hours"),
            "minimum_hours": rate.get("minimum_hours") or opt.get("minimum"),
            "cancellation_hours": opt.get("cancellation_hours") or ps.get("cancellation_hours"),
            "special_event": ({"name": ps["special_event"]["name"]} if ps.get("special_event") else None),
            "per_vehicle_cents": opt.get("unit_total") or ps.get("per_vehicle_total_amount"),
            "line_total_cents": opt.get("line_total") or ps.get("total_amount"),
        },
        "client_notes": [],
    }
    if engine_fuel_pct:
        leg["engine_fuel_pct"] = engine_fuel_pct
    if engine_handling_pct:
        leg["engine_handling_pct"] = engine_handling_pct
    tt = unit.get("travel_times") or []
    if tt:
        for i, s_ in enumerate(leg["stops"]):
            if i < len(tt) and tt[i]:
                s_["drive_minutes"] = tt[i]
        leg["route"] = {"drive_min": int(sum(x for x in tt if x)), "source": "engine"}
    if engine_discount_pct:
        # Present standard rates on the line; the engine's discount becomes a visible line item.
        qty = leg["vehicle"]["quantity"] or 1
        hourly = leg["pricing"]["method"] == "hourly"
        units = (leg["pricing"]["billable_hours"] or 0) if hourly else 1
        if hourly:
            per = std_rate * units
        else:
            per = round((opt.get("unit_total") or 0) * std_rate / eff_rate)
        # Keep Core's own net alongside the standard presentation. C5 needs both: the
        # standard figure is what the rate card shows, the net is what Core actually
        # quoted, and the engine lines are pinned so standard + lines == net exactly.
        leg["engine_net_line_cents"] = int(leg["pricing"]["line_total_cents"] or 0)
        leg["engine_standard_rate_cents"] = int(std_rate)
        leg["engine_rate_units"] = units
        leg["engine_standard_line_cents"] = int(per * qty)
        leg["pricing"]["per_vehicle_cents"] = int(per)
        leg["pricing"]["line_total_cents"] = int(per * qty)
        leg["engine_discount_pct"] = engine_discount_pct
    # "No local providers" is client-relevant: surface it as a line note automatically.
    #
    # Two triggers, because the signal moved. The warning text now appears only on
    # resolve_itinerary_stops; the QUOTE response carries `excess_drive_time: true`
    # instead. Reading only the warning meant a Whistler job — priced out of Vancouver,
    # 4 hours of positioning folded into a 12-hour bill — produced NO note at all, so a
    # client saw the hours without the reason. Found by re-capturing the Whistler fixture.
    #
    # The warning is preferred when present because it names the market. `excess_drive_time`
    # doesn't, so the wording falls back to the service area, then to generic. Carrying the
    # resolution warning through the handoff would restore the name in every case — that
    # belongs with handoff contract v3 (F2).
    note = None
    for w in unit.get("warnings") or []:
        if "No local providers" in w:
            m = re.search(r"local providers in ([^.]+)\.", w)
            note = m.group(1).strip() if m else (service_area or None)
            break
    if note is None and unit.get("excess_drive_time"):
        note = service_area or ""
    if note is not None:
        where = f"our {note} partners" if note else "a neighbouring market"
        leg["client_notes"].append(
            f"Vehicles for this service are positioned from {where}; additional drive time "
            f"is included in the reservation.")
    if leg["pricing"]["method"] != "hourly":
        leg["pricing"]["billable_hours"] = None
        leg["pricing"]["minimum_hours"] = None
    unit_priced = ((unit.get("pricing_summary") or {}).get("status") or "priced") == "priced"
    internal = {
        "rate_ids": [opt.get("rate_id")] if opt.get("rate_id") else [],
        "warnings": [w for w in (unit.get("warnings") or [])
                     if not (SUPPRESSED_WARNING in w and unit_priced)],
        "placeholders": [],
    }
    for s in stops:
        if s.get("kind") == "airport" and s.get("flight", {}).get("tbd"):
            internal["placeholders"].append(
                f"{leg['key']}: flight time {s['flight'].get('scheduled_time')} is a placeholder (TBD flight)")
    return leg, internal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?", default=None)
    ap.add_argument("out")
    ap.add_argument("--option", default=None,
                    help="when raw is a generate_quote_options response, which option key to normalize")
    ap.add_argument("--from-handoff", default=None, help="handoff dir from quote-intake; supplies raw, client, select, alternatives, placeholders")
    ap.add_argument("--client", default=None)
    ap.add_argument("--prepared-by", default=None)
    ap.add_argument("--select", default=None, help="comma-separated unit keys to keep")
    ap.add_argument("--title", default="Ground Transportation Quote")
    ap.add_argument("--valid-days", type=int, default=7)
    ap.add_argument("--alternative", action="append", default=[],
                    help="altKey:primaryKey — mark altKey as Option B for primaryKey (kept, excluded from totals)")
    args = ap.parse_args()

    handoff = None
    if args.from_handoff:
        handoff = json.load(open(os.path.join(args.from_handoff, "intake.json"), encoding="utf-8"))
        if not handoff.get("final"):
            sys.exit("Handoff is not final — the quote hasn't been confirmed by the user.")
        args.raw = args.raw or os.path.join(args.from_handoff, "raw_quote.json")
        args.client = args.client or handoff["client"]["name"]
        sel = handoff.get("selection", {})
        if sel.get("select") and not args.select:
            args.select = ",".join(sel["select"] + list((sel.get("alternatives") or {}).keys()))
        for alt, prim in (sel.get("alternatives") or {}).items():
            if f"{alt}:{prim}" not in args.alternative:
                args.alternative.append(f"{alt}:{prim}")
    if not args.raw or not args.client:
        sys.exit("Need raw_quote.json and --client, or --from-handoff <dir>")

    with open(args.raw, encoding="utf-8") as f:
        raw = json.load(f)

    # generate_quote_options returns options[].result; each result is the single-package shape.
    if raw.get("options") and raw.get("quote_units") is None:
        keys = [o.get("key") for o in raw["options"]]
        want = args.option or (handoff or {}).get("selected_option")
        chosen = next((o for o in raw["options"] if o.get("key") == want), None)
        if chosen is None:
            if want:
                sys.exit(f"Option {want!r} not in this response. Available: {keys}")
            if len(raw["options"]) > 1:
                sys.exit(f"This is a multi-option response ({keys}). Pass --option <key> for the one the user chose.")
            chosen = raw["options"][0]
        print(f"Using option {chosen.get('key')!r} from a multi-option response", file=sys.stderr)
        raw = chosen.get("result") or {}

    units = raw.get("quote_units") or []
    pres_units = {u.get("key"): u for u in (raw.get("presentation", {}).get("data", {}).get("quote_units") or [])}
    selected = set(k.strip() for k in args.select.split(",")) if args.select else None

    alt_map = dict(a.split(":", 1) for a in args.alternative)
    legs, dropped, warnings, placeholders, rate_ids = [], [], [], [], []
    for u in units:
        if selected is not None and u.get("key") not in selected:
            dropped.append(u.get("key"))
            continue
        leg, internal = normalize_unit(u, pres_units.get(u.get("key")))
        if leg is None:
            warnings.extend(internal)
            continue
        legs.append(leg)
        warnings.extend(internal["warnings"])
        placeholders.extend(internal["placeholders"])
        rate_ids.extend(internal["rate_ids"])

    if selected is None and len(units) > 1 and not alt_map:
        print("WARNING: no --select given; keeping ALL units: "
              + ", ".join(u.get("key", "?") for u in units)
              + ". If any are alternatives for the same leg, re-run with --select.", file=sys.stderr)

    for leg in legs:
        for s in leg["stops"]:
            if s.get("needs_label"):
                print(f"WARNING: {leg['key']} has an unlabeled stop ('{s['label']}'). "
                      f"Set stops[].label from the resolve_itinerary_stops display_name.", file=sys.stderr)
    for p in placeholders:
        print(f"PLACEHOLDER: {p}", file=sys.stderr)

    for leg in legs:
        if leg["key"] in alt_map:
            leg["alternative_of"] = alt_map[leg["key"]]
    primaries = [l for l in legs if not l.get("alternative_of")]
    alts = [l for l in legs if l.get("alternative_of")]
    for i, leg in enumerate(primaries):
        leg["ref"] = f"A{i+1}"
    for i, leg in enumerate(alts):
        leg["ref"] = f"B{i+1}"
    today = dt.date.today()
    subtotal = sum(l["pricing"]["line_total_cents"] or 0 for l in legs if not l.get("alternative_of"))
    adjustments = []
    # engine-applied fuel surcharge, if the result carries one (field names vary; check the common ones)
    ps_top = raw.get("pricing_summary") or {}
    fuel = None
    for src in (ps_top, raw):
        for k in ("fuel_surcharge_percent", "fuel_surcharge_pct", "fuel_surcharge"):
            v = src.get(k)
            if isinstance(v, (int, float)) and v:
                fuel = float(v) if v < 100 else None
            elif isinstance(v, dict) and (v.get("percent") or v.get("rate")):
                fuel = float(v.get("percent") or v.get("rate"))
    if fuel:
        adjustments.append({"label": "Fuel surcharge", "type": "percent", "value": fuel, "applies_to": None,
                            "source": "engine", "amount_cents": 0})
    pcts = {l.get("engine_discount_pct") for l in legs if l.get("engine_discount_pct")}
    if len(pcts) == 1:
        pct = pcts.pop()
        # C5 — pin the amount, computed per leg at Core's own rounding granularity (per
        # hour, then × hours × quantity) rather than as a percentage of the subtotal.
        # Applying the percentage to a subtotal and applying it per hour differ by cents,
        # and the engine total is Core's to state, not ours to approximate.
        disc = 0
        for l in legs:
            if l.get("alternative_of"):
                continue
            std = l.get("engine_standard_rate_cents") or 0
            rate_units = l.get("engine_rate_units") or 0
            qty = (l.get("vehicle") or {}).get("quantity") or 1
            disc -= round(std * pct / 100.0) * rate_units * qty
        adjustments.append({"label": "Preferred client discount", "type": "percent", "value": -pct,
                            "applies_to": None, "source": "engine", "amount_cents": 0,
                            "amount_cents_fixed": int(disc)})
    elif len(pcts) > 1:
        print("WARNING: legs carry different engine discounts; leaving effective rates as-is", file=sys.stderr)
    hnd = {l.get("engine_handling_pct") for l in legs if l.get("engine_handling_pct")}
    if len(hnd) == 1:
        adjustments.append({"label": "Special handling", "type": "percent", "value": hnd.pop(),
                            "applies_to": None, "source": "engine", "amount_cents": 0})
    fpc = {l.get("engine_fuel_pct") for l in legs if l.get("engine_fuel_pct")}
    if len(fpc) == 1:
        # Fuel is pinned as the REMAINDER: Core's net minus (standard + discount). That makes
        # standard + discount + fuel equal Core's aggregate exactly, by construction, which
        # is the whole point of C5 — the document states Core's number, it does not
        # approach it. Any genuine disagreement now surfaces through C4's fail-closed check
        # rather than being absorbed into a line that then misstates its own percentage.
        # engine_net_line_cents is Core's net for the leg. line_total_cents has by now been
        # REPLACED with the standard-rate presentation, so reading it here would compare
        # standard against standard and make fuel the whole discount.
        net = sum((l.get("engine_net_line_cents")
                   if l.get("engine_net_line_cents") is not None
                   else (l["pricing"]["line_total_cents"] or 0))
                  for l in legs if not l.get("alternative_of"))
        std = sum((l.get("engine_standard_line_cents")
                   if l.get("engine_standard_line_cents") is not None
                   else (l["pricing"]["line_total_cents"] or 0))
                  for l in legs if not l.get("alternative_of"))
        disc_line = next((a for a in adjustments if a.get("label") == "Preferred client discount"), None)
        disc_amt = (disc_line or {}).get("amount_cents_fixed") or 0
        adjustments.append({"label": "Fuel surcharge", "type": "percent", "value": fpc.pop(),
                            "applies_to": None, "source": "engine", "amount_cents": 0,
                            "amount_cents_fixed": int(net - std - disc_amt)})
    quote = {
        "meta": {
            "client": args.client,
            "profile_id": next((u.get("travel_coordination_profile_id") for u in units if u.get("travel_coordination_profile_id")), None),
            "prepared_by": args.prepared_by,
            "prepared_on": today.isoformat(),
            "valid_until": (today + dt.timedelta(days=args.valid_days)).isoformat(),
            "estimate_type": raw.get("estimate_type") or raw.get("pricing_summary", {}).get("estimate_type"),
            "currency": raw.get("currency") or raw.get("pricing_summary", {}).get("currency_code") or "USD",
            "title": args.title,
            "reference": None,
            "travel_coordinator": None,
            "service_area": next((l.get("service_area") for l in legs if l.get("service_area")), None),
        },
        "legs": legs,
        "engine_total_cents": raw.get("aggregate_total") or (raw.get("pricing_summary") or {}).get("total_amount"),
        "engine_subtotal_cents": subtotal,
        "adjustments": adjustments,
        "total_cents": subtotal + sum(a["amount_cents"] for a in adjustments),
        "personalization": {
            "cover": "general",
            "cover_image_url": None, "client_logo_url": None, "event_name": None,
            "intro_note": None, "pull_quote": None, "pull_quote_attribution": None,
            "account_manager": {"name": args.prepared_by, "title": None, "email": None, "phone": None},
            "closing_note": None,
        },
        "terms": [],  # filled by apply_adjustments (conditional bullets)
        "internal": {
            "rate_ids": sorted(set(r for r in rate_ids if r)),
            "warnings": sorted(set(warnings)),
            "placeholders": placeholders + list((handoff or {}).get("placeholders") or []),
            "dropped_units": dropped,
            "intake": ({"quote_mode": handoff.get("quote_mode"), "ambiguities": handoff.get("ambiguities"),
                        "rationale": {u["key"]: u.get("rationale") for u in handoff.get("units", [])}} if handoff else None),
        },
    }
    sys.path.insert(0, HERE)
    from apply_adjustments import recompute
    quote = recompute(quote)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(quote, f, indent=2)
    print(f"Wrote {args.out}: {len(legs)} leg(s), engine subtotal ${subtotal/100:,.2f}"
          + (f", dropped {dropped}" if dropped else ""))


if __name__ == "__main__":
    main()
