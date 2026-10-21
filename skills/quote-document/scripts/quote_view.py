#!/usr/bin/env python3
"""The ONE reader of a Savoya quote tool result. Every script that reads a pricing
response reads it through here, in both skills.

Three shapes arrive during the rollout of the MCP's compact quote view, and all three
come out as the same thing: packages of quote-view units.

  * presentation version 2: `{ "presentation": {...} }` and nothing else. The view is
    the whole response; the raw Core payload never reaches us. Read as sent.
  * presentation version 1: the raw Core payload (`quote_units`, `aggregate_total`,
    `options[].result`, ...) plus a version 1 presentation. The raw units are converted
    to the version 2 unit shape by `unit_from_v1`, which mirrors the MCP's own mapping
    (savoya-quote-mcp `src/domains/quotes/presentation.ts`).
  * unversioned: a raw Core payload with no presentation at all (older captures, and a
    response saved with `handoff.py ingest --without-presentation`). Read as version 1.

Any other presentation version is REFUSED, loudly, with a message saying to update the
plugin. A newer MCP is the one case where reading on would be guessing.

    packages(raw) -> [{key, label, strategy, total_cents, units, estimate_type,
                       currency, persisted, warnings, fuel_pct, unpriced}]

`key` is None for a single quote_result package and the option key for each scenario
of a comparison. `units` are version 2 quote-view units (see presentationContracts.ts),
with the warnings the MCP stated once in `warnings_on_every_unit` given back to every
unit. A warning only some units carry stays on those units: it describes them alone
("No local providers in Syracuse" on one leg must never reach the others).

Money is passed through, never computed: totals, line totals, per-vehicle amounts, rates
and adjustments are the view's (version 2) or Core's (version 1). Remove the version 1
path once every MCP deployment returns version 2.
"""
import copy
import math
import re

SUPPORTED_VERSIONS = (1, 2)


class QuoteViewError(ValueError):
    """The response cannot be read: an unknown presentation version, or not a quote."""


def version(raw):
    """1 or 2 for a versioned response, None for an unversioned raw Core payload."""
    if not isinstance(raw, dict):
        raise QuoteViewError("The quote response is not a JSON object.")
    if "presentation" not in raw:
        return None
    presentation = raw.get("presentation")
    found = presentation.get("version") if isinstance(presentation, dict) else None
    if found not in SUPPORTED_VERSIONS:
        raise QuoteViewError(
            f"This quote came back in MCP presentation version {found}, which this build of the "
            f"savoya-quoting plugin cannot read (it reads versions "
            f"{', '.join(str(v) for v in SUPPORTED_VERSIONS)}). Update the savoya-quoting plugin, "
            "start a new chat, and run the quote again.")
    return found


def is_v2(raw):
    return version(raw) == 2


def view(raw):
    """The presentation view name (quote_result, scenario_comparison, blocked, ...), or None."""
    return ((raw or {}).get("presentation") or {}).get("view") if version(raw) else None


# --- version 1 -> version 2 units ------------------------------------------------------

def _coordinate(value):
    """Six decimals (about 0.1 m), rounded exactly as the MCP rounds them
    (JavaScript `Math.round(value * 1e6) / 1e6`: half rounds up). Python's round() rounds
    half to even and put a Whistler pin 0.000001 away from the version 2 one."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return math.floor(float(value) * 1e6 + 0.5) / 1e6


def _id(value):
    return None if value is None else str(value)


def _pick_option(unit):
    """The vehicle option a v1 unit was priced with. The exact tools return the chosen
    vehicle on the unit itself; older captures carry it in value_option or as the
    cheapest quoteable vehicle_options entry."""
    if unit.get("pricing_summary") and unit.get("vehicle_type"):
        return unit
    if unit.get("value_option"):
        return unit["value_option"]
    options = unit.get("vehicle_options") or []
    priced = [o for o in options if o.get("quoteable")]
    if priced:
        return min(priced, key=lambda o: o.get("line_total", 0))
    if options:
        return None             # Core offered vehicles and none of them priced
    return unit                 # nothing else to choose from: the unit is its own priced option


def stop_is_airport(stop):
    """An airport stop in ANY shape Core has used: a top-level `airport` object (old),
    `location.type == "airport"` (current), `type`/`stop_type == "airport"`. Reading only
    one of them once turned every airport stop into an address and dropped the
    "flight time to be confirmed" disclosure."""
    return bool(stop.get("airport")) or (stop.get("location") or {}).get("type") == "airport" \
        or stop.get("type") == "airport" or stop.get("stop_type") == "airport"


def stop_kind(stop):
    if stop.get("as_directed") is True or stop.get("type") == "as_directed":
        return "as_directed"
    return "airport" if stop_is_airport(stop) else "address"


_SERVICE_AREA_UNSET = object()


def stop_service_area(stop):
    """The stop's service-area name; None when Core said the place is in NO Savoya market
    (`location.service_area: null`); _SERVICE_AREA_UNSET when Core did not say. "Unknown"
    and "nowhere" decide whether a leg is treated as sourced, so they are kept apart.
    Both the current (`location.service_area`) and the old top-level shape are read."""
    for holder in ((stop.get("location") or {}), stop):
        area = holder.get("service_area")
        if isinstance(area, dict) and area.get("name"):
            return area["name"]
        if isinstance(area, str) and area:
            return area
    loc = stop.get("location")
    if isinstance(loc, dict) and "service_area" in loc and not loc.get("service_area"):
        return None
    return _SERVICE_AREA_UNSET


def coordinates_of(stop):
    """Core's own coordinates for a v1 stop, from whichever shape it sent them in.

    `position.latitude/longitude` is the documented path. A real quote once came back
    with them elsewhere, the map fell back to geocoding a market name no geocoder knows,
    and the client PDF shipped with no map while Core had the coordinates all along. So
    every shape is read, and an undocumented one is reported on stderr so it reaches a
    capture and then this list."""
    import sys

    def pair(d):
        if not isinstance(d, dict):
            return None
        for a, b in (("latitude", "longitude"), ("lat", "lon"), ("lat", "lng"), ("y", "x")):
            if d.get(a) is not None and d.get(b) is not None:
                try:
                    return float(d[a]), float(d[b])
                except (TypeError, ValueError):
                    return None
        return None

    known = pair(stop.get("position") or {})
    if known:
        return known
    for key in ("location", "coordinates", "geo", "point", "place", "address_details"):
        found = pair(stop.get(key) or {})
        if found:
            print(f"WARNING: stop coordinates found under {key!r}, not 'position' — "
                  f"add it to coordinates_of()'s documented path list and tell "
                  f"engineering which shape Core is sending", file=sys.stderr)
            return found
    found = pair(stop)
    if found:
        print("WARNING: stop coordinates found at the top level of the stop, not under "
              "'position' — add it to coordinates_of()'s documented path list",
              file=sys.stderr)
    return found


def _display_name(stop):
    for value in (stop.get("display_name"), stop.get("name"), stop.get("label"),
                  stop.get("formatted_address"), stop.get("address"),
                  (stop.get("airport") or {}).get("display_name"), (stop.get("airport") or {}).get("name"),
                  (stop.get("city") or {}).get("name")):
        if isinstance(value, str) and value.strip():
            return value
    return None


def _stop_from_v1(stop, index, travel_time):
    """One v1 Core stop as a v2 view stop (presentation.ts `stops`)."""
    label = (stop.get("name") or "").strip() or _display_name(stop) or f"Stop {index + 1}"
    full = stop.get("display_name") or stop.get("address")
    short = stop.get("address")
    out = {"order": index + 1, "label": label, "kind": stop_kind(stop)}
    if full and full != label:
        out["address"] = full
    elif short and short != label:
        out["address"] = short
    if isinstance(stop.get("duration"), (int, float)) and stop["duration"] > 0:
        out["wait_hours"] = stop["duration"]
    ll = coordinates_of(stop)
    if ll:
        out["latitude"], out["longitude"] = _coordinate(ll[0]), _coordinate(ll[1])
    if isinstance(travel_time, (int, float)) and travel_time > 0:
        out["drive_minutes"] = travel_time
    area = stop_service_area(stop)
    if area is not _SERVICE_AREA_UNSET:
        out["service_area"] = area
    if stop.get("stop_time"):
        out["time"] = stop["stop_time"]
    flight = stop.get("flight") or {}
    if flight.get("scheduled_time"):
        out["flight_time"] = flight["scheduled_time"]
    if flight.get("flight_type"):
        out["flight_type"] = flight["flight_type"]
    if flight.get("commercial_tbd") is True:
        out["flight_tbd"] = True
    return out


def stop_from_v1(stop, index=0, travel_time=None):
    """One v1 Core stop as a v2 view stop: what the version 2 view would say about it."""
    return _stop_from_v1(stop, index, travel_time)


# The adjustment keys the view carries (presentation.ts `pricingDetails`).
ADJUSTMENT_KEYS = ("discount_basis_points", "special_handling_basis_points", "fuel_surcharge_basis_points",
                   "custom_discount_basis_points", "temporary_discount_basis_points",
                   "effective_discount_basis_points", "temporary_discount_amount", "temporary_discount_label")


def _unique(values):
    return list(dict.fromkeys(v.strip() for v in values if isinstance(v, str) and v.strip()))


def unit_from_v1(unit):
    """A v1 raw Core unit as a version 2 quote-view unit. None when it carries no priced
    vehicle at all (an old shape with nothing quoteable)."""
    opt = _pick_option(unit)
    if opt is None:
        return None
    summary = opt.get("pricing_summary") or {}
    rate = summary.get("rate") or {}
    calculation = summary.get("calculation") or {}
    vehicle = opt.get("vehicle_type") or {}
    adj = summary.get("adjustments") or {}
    # Core stores the minutes from the previous stop on each stop; older captures carry
    # them as a unit-level `travel_times` list instead. The first stop has no leg.
    times = unit.get("travel_times")
    stops = []
    for i, s in enumerate(unit.get("stops") or []):
        if isinstance(times, list):
            tt = times[i] if i < len(times) else None
        else:
            tt = s.get("travel_time") if i > 0 else None
        stops.append(_stop_from_v1(s, i, tt))
    out = {
        "key": unit.get("key"),
        "label": unit.get("label") or unit.get("key"),
        "quantity": opt.get("quantity") or calculation.get("quantity") or 1,
        "total_amount": opt.get("line_total") if opt.get("line_total") is not None else summary.get("total_amount"),
        "per_vehicle_amount": opt.get("unit_total") if opt.get("unit_total") is not None else summary.get("per_vehicle_total_amount"),
        "requested_quantity": calculation.get("requested_quantity"),
        "required_quantity": calculation.get("required_quantity"),
        "quoted_hours": unit.get("quoted_time"),
        "vehicle_type_id": _id(vehicle.get("id")),
        "vehicle_name": vehicle.get("name") or vehicle.get("display_name"),
        "vehicle_capacity": vehicle.get("capacity") if vehicle.get("capacity") is not None else calculation.get("vehicle_capacity"),
        "passenger_count": unit.get("passenger_count") or calculation.get("passenger_count"),
        "passenger_count_source": unit.get("passenger_count_source"),
        "passenger_selection_source": unit.get("passenger_selection_source"),
        "pickup_date": unit.get("pickup_date"),
        "timezone": unit.get("timezone"),
        "primary_service_area": (unit.get("primary_service_area") or {}).get("name"),
        "source_service_area": (unit.get("source_service_area") or {}).get("name"),
        "stops": stops,
        "pricing": {
            "pricing_method": summary.get("pricing_method"),
            "rate_source": rate.get("source"),
            "rate_id": _id(rate.get("id") if rate.get("id") is not None else opt.get("rate_id")),
            "subtotal_amount": summary.get("subtotal_amount"),
            "base_rate_amount": rate.get("base_rate_amount") or rate.get("rate_amount_before_temporary_discount"),
            "effective_rate_amount": rate.get("effective_rate_amount") or opt.get("effective_rate_amount"),
            "rate_amount": rate.get("effective_rate_amount") or opt.get("effective_rate_amount"),
            "billing_unit": rate.get("billing_unit"),
            "minimum_hours": rate.get("minimum_hours") or opt.get("minimum"),
            "billable_hours": opt.get("billable_hours") or calculation.get("billable_hours"),
            "cancellation_hours": opt.get("cancellation_hours") if opt.get("cancellation_hours") is not None else summary.get("cancellation_hours"),
            "special_event": ({"id": _id((summary["special_event"] or {}).get("id")),
                               "name": (summary["special_event"] or {}).get("name"),
                               "no_rates": (summary["special_event"] or {}).get("no_rates") is True}
                              if summary.get("special_event") else None),
            "adjustments": dict({k: adj[k] for k in ADJUSTMENT_KEYS if adj.get(k) is not None},
                                temporary_rate_used=adj.get("temporary_rate_used") is True),
        },
        "warnings": _unique([*(unit.get("warnings") or []), *(summary.get("warnings") or [])]),
    }
    drive = unit.get("sourcing_drive_time") or {}
    if drive:
        out["sourcing_drive_time"] = {"additional_quoted_time_hours": drive.get("additional_quoted_time_hours"),
                                      "incremental_client_amount": drive.get("incremental_client_amount")}
    if unit.get("excess_drive_time") is True:
        out["excess_drive_time"] = True
    # The candidates Core priced and did not choose. Only old v1 captures carry them; the
    # exact tools take one vehicle per unit, so a v2 response never has alternatives.
    alts = []
    for alt in unit.get("vehicle_options") or []:
        av = alt.get("vehicle_type") or {}
        if alt.get("quoteable") and av.get("id") != vehicle.get("id"):
            alts.append({"vehicle_name": av.get("name"), "quantity": alt.get("quantity"),
                         "total_amount": alt.get("line_total")})
    if alts:
        out["v1_alternatives"] = alts
    return out


# --- packages ---------------------------------------------------------------------------

def with_shared_warnings(units, shared):
    """Give each unit back the warnings every unit carries (the MCP states those once).
    Never the response-level `presentation.warnings`: those are not per-unit facts."""
    shared = list(shared or [])
    out = []
    for unit in units or []:
        unit = copy.deepcopy(unit)
        unit["warnings"] = list(dict.fromkeys([*(unit.get("warnings") or []), *shared]))
        out.append(unit)
    return out


def _v1_package(result, key=None, label=None, strategy=None):
    units, unpriced = [], []
    for raw_unit in result.get("quote_units") or []:
        unit = unit_from_v1(raw_unit)
        if unit is None:
            unpriced.append(raw_unit.get("key"))
        else:
            units.append(unit)
    summary = result.get("pricing_summary") or {}
    fuel = None
    for src in (summary, result):            # legacy: a top-level fuel figure, when one was sent
        for k in ("fuel_surcharge_percent", "fuel_surcharge_pct", "fuel_surcharge"):
            v = src.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v:
                fuel = float(v) if v < 100 else None
            elif isinstance(v, dict) and (v.get("percent") or v.get("rate")):
                fuel = float(v.get("percent") or v.get("rate"))
    estimate = result.get("estimate_type") or summary.get("estimate_type") or next(
        ((u.get("pricing_summary") or {}).get("estimate_type") for u in result.get("quote_units") or []
         if (u.get("pricing_summary") or {}).get("estimate_type")), None)
    total = result.get("aggregate_total")
    if total is None:
        total = summary.get("total_amount")
    return {"key": key, "label": label, "strategy": strategy, "total_cents": total, "units": units,
            "estimate_type": estimate, "currency": result.get("currency") or summary.get("currency_code") or "USD",
            "persisted": result.get("persisted"), "warnings": _unique(result.get("warnings") or []),
            "fuel_pct": fuel, "unpriced": unpriced}


def packages(raw):
    """[{key, label, strategy, total_cents, units, ...}] for a quote or scenario result.
    Raises QuoteViewError for an unsupported version or a response that is not a quote."""
    found = version(raw)
    if found == 2:
        presentation = raw["presentation"]
        data = presentation.get("data") or {}
        name = presentation.get("view")
        common = {"estimate_type": presentation.get("estimate_type"),
                  "currency": presentation.get("currency_code") or "USD", "fuel_pct": None, "unpriced": []}
        if name == "scenario_comparison":
            return [dict(common, key=s.get("key"), label=s.get("label") or s.get("key"), strategy=s.get("strategy"),
                         total_cents=s.get("total_amount"), persisted=s.get("persisted"),
                         warnings=list(s.get("warnings") or []),
                         units=with_shared_warnings(s.get("quote_units"), s.get("warnings_on_every_unit")))
                    for s in data.get("scenarios") or []]
        if name == "quote_result":
            return [dict(common, key=None, label=None, strategy=None, total_cents=data.get("total_amount"),
                         persisted=data.get("persisted"),
                         warnings=[w.get("message") if isinstance(w, dict) else w for w in presentation.get("warnings") or []],
                         units=with_shared_warnings(data.get("quote_units"), data.get("warnings_on_every_unit")))]
        raise QuoteViewError(f"This is a {name!r} response, not a priced quote.")
    if isinstance(raw.get("options"), list) and raw.get("quote_units") is None:
        return [_v1_package(o.get("result") or {}, o.get("key"), o.get("label") or o.get("key"), o.get("strategy"))
                for o in raw["options"]]
    if raw.get("quote_units") is None:
        name = (raw.get("presentation") or {}).get("view")
        raise QuoteViewError(f"This is a {name!r} response, not a priced quote." if name
                             else "The response carries no quote units.")
    return [_v1_package(raw)]


def to_v2(pkg):
    """One package as a version 2 quote_result response: the shape handoff.py writes for a
    saved option or a merged package, so everything after ingest reads one shape. Units
    keep every warning they carry (the shared ones were already given back), so
    `warnings_on_every_unit` is empty and nothing is lost."""
    return {"presentation": {
        "version": 2, "view": "quote_result", "status": "ready",
        "estimate_type": pkg.get("estimate_type") or "exact", "title": "Exact quote",
        "currency_code": pkg.get("currency") or "USD", "amount_unit": "cents",
        "warnings": [{"severity": "warning", "message": w} for w in pkg.get("warnings") or []],
        "data": {"total_amount": pkg.get("total_cents"), "quote_units": copy.deepcopy(pkg.get("units") or []),
                 "unquoteable_unit_keys": list(pkg.get("unpriced") or []), "warnings_on_every_unit": [],
                 "persisted": False if pkg.get("persisted") is None else pkg["persisted"],
                 "pricing": {"adjustments": {"temporary_rate_used": False}}},
    }}


def is_options(raw):
    """A comparison of several complete packages (generate_quote_options)."""
    if version(raw) == 2:
        return raw["presentation"].get("view") == "scenario_comparison"
    return isinstance(raw.get("options"), list) and raw.get("quote_units") is None


STOP_PLACEHOLDER = re.compile(r"Stop \d+")


def stop_names(unit):
    """Every name a stop is known by in a view unit: the label and the address."""
    return [n for s in unit.get("stops") or [] for n in (s.get("label"), s.get("address")) if n]
