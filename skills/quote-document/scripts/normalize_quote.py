#!/usr/bin/env python3
"""Copy an exact Savoya Core quote into the presentation schema.

No money is calculated here. Values are copied by field presence so valid zeroes
remain zero and a missing value remains missing.
"""

import argparse, datetime as dt, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS_PATH = os.path.join(HERE, "..", "assets", "terms.md")


def present(mapping, key, default=None):
    return mapping[key] if isinstance(mapping, dict) and key in mapping else default


def load_terms(has_fuel=False, fuel_pct=None):
    terms = []
    try:
        lines = open(TERMS_PATH, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return terms
    for line in lines:
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        match = re.match(r"\[if:(\w+)\]\s*(.*)", body)
        if match:
            if match.group(1) == "fuel_surcharge" and has_fuel:
                terms.append(
                    match.group(2).replace(
                        "{pct}",
                        f"{fuel_pct:g}" if fuel_pct is not None else "the quoted",
                    )
                )
            continue
        terms.append(body)
    return terms


def stop_label(stop, presentation):
    for value in (
        stop.get("name"),
        stop.get("display_name"),
        (presentation or {}).get("label"),
    ):
        if value and not str(value).startswith("Stop "):
            return value, False
    if stop.get("airport"):
        return "Airport (label needed)", True
    if stop.get("as_directed"):
        city = (
            ((stop.get("service_area") or {}).get("name") or "")
            .split("/")[0]
            .split(",")[0]
            .strip()
        )
        return (f"As directed — {city}" if city else "As directed"), False
    return "Stop (label needed)", True


def normalize_stop(stop, presentation):
    label, needs_label = stop_label(stop, presentation)
    out = {"label": label, "kind": "airport" if stop.get("airport") else "address"}
    if "address" in stop:
        out["address"] = stop["address"]
    if stop.get("airport"):
        flight = stop.get("flight") or {}
        out["flight"] = {
            "tbd": bool(flight.get("commercial_tbd")),
            "type": flight.get("flight_type"),
            "scheduled_time": flight.get("scheduled_time"),
        }
    if stop.get("as_directed"):
        out.update({"kind": "as_directed", "as_directed": True})
    if "duration" in stop:
        out["wait_hours"] = stop["duration"]
    position = stop.get("position") or {}
    if position.get("latitude") is not None and position.get("longitude") is not None:
        out["lat"], out["lon"] = position["latitude"], position["longitude"]
    if needs_label:
        out["needs_label"] = True
    return out


def normalize_unit(unit, presentation):
    summary, rate = (
        unit.get("pricing_summary") or {},
        (unit.get("pricing_summary") or {}).get("rate") or {},
    )
    calc, adj, vehicle = (
        summary.get("calculation") or {},
        summary.get("adjustments") or {},
        unit.get("vehicle_type") or {},
    )
    source_stops, presentation_stops = (
        unit.get("stops") or [],
        (presentation or {}).get("stops") or [],
    )
    stops = [
        normalize_stop(
            stop, presentation_stops[i] if i < len(presentation_stops) else None
        )
        for i, stop in enumerate(source_stops)
    ]
    pricing = {
        "method": present(summary, "pricing_method"),
        "base_rate_cents": present(rate, "base_rate_amount"),
        "rate_before_temporary_discount_cents": present(
            rate, "rate_amount_before_temporary_discount"
        ),
        "effective_rate_cents": present(rate, "effective_rate_amount"),
        "rate_cents": present(rate, "effective_rate_amount"),
        "billable_hours": present(calc, "billable_hours"),
        "minimum_hours": present(rate, "minimum_hours"),
        "cancellation_hours": present(summary, "cancellation_hours"),
        "per_vehicle_cents": present(
            unit, "unit_total", present(summary, "per_vehicle_total_amount")
        ),
        "unit_total_cents": present(unit, "unit_total"),
        "line_total_cents": present(unit, "line_total"),
        "subtotal_cents": present(summary, "subtotal_amount"),
        "per_vehicle_subtotal_cents": present(summary, "per_vehicle_subtotal_amount"),
        "temporary_discount_amount_cents": present(adj, "temporary_discount_amount"),
        "special_event": (
            {"name": summary["special_event"].get("name")}
            if summary.get("special_event")
            else None
        ),
    }
    service_area = next(
        (
            (s.get("service_area") or {}).get("name")
            for s in source_stops
            if s.get("service_area")
        ),
        None,
    )
    leg = {
        "key": unit.get("key"),
        "service_area": service_area,
        "label": unit.get("label") or unit.get("key"),
        "date": present(unit, "pickup_date", (presentation or {}).get("date")),
        "passenger_count": present(
            unit, "passenger_count", present(calc, "passenger_count")
        ),
        "vehicle": {
            "id": vehicle.get("id"),
            "name": vehicle.get("name"),
            "capacity": vehicle.get("capacity"),
            "quantity": present(unit, "quantity", present(calc, "quantity")),
        },
        "stops": stops,
        "pricing": pricing,
        "adjustments": adj,
        "terms": summary.get("terms") or [],
        "warnings": unit.get("warnings") or [],
        "client_notes": [],
    }
    travel_times = unit.get("travel_times") or []
    if travel_times:
        for i, stop in enumerate(stops):
            if i < len(travel_times) and travel_times[i] is not None:
                stop["drive_minutes"] = travel_times[i]
        leg["route"] = {
            "drive_min": int(
                sum(v for v in travel_times if isinstance(v, (int, float)))
            ),
            "source": "engine",
        }
    for warning in leg["warnings"]:
        if "No local providers" in warning:
            match = re.search(r"local providers in ([^.]+)\.", warning)
            city = (
                match.group(1).strip() if match else (service_area or "a nearby market")
            )
            leg["client_notes"].append(
                f"Vehicles for this service are positioned from our {city} partners; additional drive time is included in the reservation."
            )
            break
    return leg


def validate(raw):
    errors = []
    if raw.get("persisted") is not False:
        errors.append("result must explicitly be non-persisted")
    if raw.get("aggregate_total") is None:
        errors.append("aggregate_total is required")
    if not raw.get("quote_units"):
        errors.append("quote_units are required")
    for unit in raw.get("quote_units") or []:
        key, summary = unit.get("key") or "unit", unit.get("pricing_summary") or {}
        if summary.get("estimate_type") != "exact":
            errors.append(f"{key} is not exact")
        for field in ("quantity", "unit_total", "line_total"):
            if field not in unit or unit[field] is None:
                errors.append(f"{key} is missing {field}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", nargs="?")
    parser.add_argument("out")
    parser.add_argument("--from-handoff")
    parser.add_argument("--client")
    parser.add_argument("--prepared-by")
    parser.add_argument("--title", default="Ground Transportation Quote")
    parser.add_argument("--valid-days", type=int, default=7)
    args = parser.parse_args()
    handoff = None
    if args.from_handoff:
        handoff = json.load(
            open(os.path.join(args.from_handoff, "intake.json"), encoding="utf-8")
        )
        if handoff.get("contract") != 3:
            sys.exit("Document generation requires handoff contract 3.")
        if not handoff.get("final"):
            sys.exit("Handoff is not final — the quote has not been confirmed.")
        args.raw = args.raw or os.path.join(args.from_handoff, "raw_quote.json")
        args.client = args.client or (handoff.get("client") or {}).get("name")
    if not args.raw or not args.client:
        sys.exit("Need raw_quote.json and --client, or --from-handoff <dir>.")
    raw = json.load(open(args.raw, encoding="utf-8"))
    errors = validate(raw)
    if errors:
        sys.exit("Refusing to normalize: " + "; ".join(errors))
    presentation = {
        u.get("key"): u
        for u in (
            ((raw.get("presentation") or {}).get("data") or {}).get("quote_units") or []
        )
    }
    legs = [
        normalize_unit(unit, presentation.get(unit.get("key")))
        for unit in raw["quote_units"]
    ]
    for index, leg in enumerate(legs):
        leg["ref"] = f"A{index + 1}"
    top = raw.get("pricing_summary") or {}
    top_adj = dict(top.get("adjustments") or {})
    for key in (
        "discount_basis_points",
        "fuel_surcharge_basis_points",
        "special_handling_basis_points",
        "temporary_discount_basis_points",
        "temporary_discount_amount",
        "temporary_discount_label",
        "temporary_rate_used",
    ):
        if key in top_adj:
            continue
        values = {
            (leg.get("adjustments") or {}).get(key)
            for leg in legs
            if key in (leg.get("adjustments") or {})
        }
        if len(values) == 1:
            top_adj[key] = values.pop()
    fuel_bps = top_adj.get("fuel_surcharge_basis_points")
    if fuel_bps is None:
        values = {
            (leg.get("adjustments") or {}).get("fuel_surcharge_basis_points")
            for leg in legs
        }
        values.discard(None)
        fuel_bps = values.pop() if len(values) == 1 else None
    today = dt.date.today()
    quote = {
        "meta": {
            "client": args.client,
            "profile_id": next(
                (
                    u.get("travel_coordination_profile_id")
                    for u in raw["quote_units"]
                    if u.get("travel_coordination_profile_id")
                ),
                None,
            ),
            "prepared_by": args.prepared_by,
            "prepared_on": today.isoformat(),
            "valid_until": (today + dt.timedelta(days=args.valid_days)).isoformat(),
            "estimate_type": "exact",
            "currency": raw.get("currency") or top.get("currency_code") or "USD",
            "title": args.title,
            "reference": None,
            "travel_coordinator": None,
            "service_area": next(
                (l.get("service_area") for l in legs if l.get("service_area")), None
            ),
        },
        "legs": legs,
        "engine_total_cents": raw["aggregate_total"],
        "engine_subtotal_cents": present(top, "subtotal_amount"),
        "package_subtotal_cents": present(top, "subtotal_amount"),
        "adjustments": top_adj,
        "total_cents": raw["aggregate_total"],
        "personalization": {
            "cover": "general",
            "cover_image_url": None,
            "client_logo_url": None,
            "event_name": None,
            "intro_note": None,
            "pull_quote": None,
            "pull_quote_attribution": None,
            "account_manager": {
                "name": args.prepared_by,
                "title": None,
                "email": None,
                "phone": None,
            },
            "closing_note": None,
        },
        "terms": load_terms(
            fuel_bps is not None and fuel_bps != 0,
            (fuel_bps / 100.0) if fuel_bps is not None else None,
        ),
        "internal": {
            "raw_quote_path": os.path.abspath(args.raw),
            "source_tool": (handoff or {}).get("source_tool"),
            "warnings": sorted({w for leg in legs for w in leg.get("warnings") or []}),
            "placeholders": list((handoff or {}).get("placeholders") or []),
            "intake": (
                {
                    "quote_mode": handoff.get("quote_mode"),
                    "ambiguities": handoff.get("ambiguities"),
                    "rationale": {
                        u["key"]: u.get("rationale") for u in handoff.get("units", [])
                    },
                }
                if handoff
                else None
            ),
        },
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(quote, handle, indent=2)
        handle.write("\n")
    print(
        f"Wrote {args.out}: {len(legs)} leg(s), Core total ${raw['aggregate_total'] / 100:,.2f}"
    )


if __name__ == "__main__":
    main()
