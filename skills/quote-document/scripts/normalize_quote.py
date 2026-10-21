#!/usr/bin/env python3
"""Normalize a Savoya engine quote result into canonical quote.json.

Accepts the JSON returned by calculate_quote_units, calculate_sourced_quote_units,
calculate_temporary_quote_units, or generate_quote_options (pass --option): the MCP's
compact quote view, read through quote_view.py.

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
sys.path.insert(0, HERE)
import quote_view  # noqa: E402  -- the one reader of a quote response, both skills

# The handoff contract this build reads. Bumped whenever intake starts writing a
# field the document relies on, so a handoff from an older build is refused rather
# than silently misread. Kept in step with handoff.py and handoff-contract.md.
HANDOFF_CONTRACT = 3

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


_TEMP_WORDS = re.compile(r"temporar|user-supplied|unsaved", re.I)


def event_for_client(special_event, pickup_date):
    """The special-event disclosure, with a stale event NAME withheld.

    Core returned `special_event.name = "Wimbledon 2022"` against July **2027** London
    dates (rate_id 1264, SpecialEventTransferRate). It printed in three places on a
    $17.9k client proposal: both London line notes and the rate card.

    The disclosure itself must survive -- a special-event rate carries real minimums and
    a different cancellation window, and suppressing it would understate what the client
    is agreeing to. It is only the NAME that is unsafe, and only when it carries a year
    that is not the year of travel. Then the leg says event pricing is in effect and says
    nothing about which event, and the mismatch goes to the internal placeholders so the
    weekly pass sees it and Savoya can fix the record.

    A name with no year (most of them) is published unchanged.
    """
    if not special_event or not special_event.get("name"):
        return {"name": None} if special_event else None
    name = str(special_event["name"])
    years = re.findall(r"\b(19|20)(\d{2})\b", name)
    if not years or not pickup_date:
        return {"name": name}
    leg_year = str(pickup_date)[:4]
    if any(a + b == leg_year for a, b in years):
        return {"name": name}
    print(f"WARNING: special event {name!r} names a year other than {leg_year}; "
          f"the event name is withheld from the client document and the rate-bearing "
          f"disclosure is kept. Core's special-event record looks stale.", file=sys.stderr)
    return {"name": None, "stale_name": name, "leg_year": leg_year}


def client_label(raw):
    """Core's discount label, made safe to print to a client.

    Two real defects, both on 10 Oct 2026, both from publishing this string as-is:

      * Core sent "Temporary user-supplied discount" and it printed in a client PDF.
        "Temporary" is Core's word for pricing it did not persist -- an internal fact
        about the quote's storage, not a fact about the client's discount. RULES.md
        forbids showing it; the session relabelled it by hand mid-flow.
      * Core sent "Additional 5% discount", and the renderer appends the percentage to
        every percent line, so the PDF read "Additional 5% discount (5%)".

    Only the first is fixed here: anything leaking the internal nature of the pricing
    becomes the neutral truth. The double percentage is NOT fixed by editing the label
    -- an earlier attempt stripped any percentage it found and turned "Loyalty 12.5%
    off" into "Loyalty off". The renderer owns the percentage it appends, so that is
    where it is suppressed; see `pct_suffix` in render_print.py.
    """
    label = (raw or "").strip()
    if not label or _TEMP_WORDS.search(label):
        return "Additional discount"
    return label


def normalize_stop(stop):
    """One view stop (quote_view units carry version 2 stops) as a quote.json stop.

    The view labels a stop by the venue's own name, then its address, and only when Core
    gave neither does it send a numbered "Stop N". That placeholder is the one label never
    printed: it becomes "(label needed)" and the session must name it. Only the exact
    "Stop <number>" shape counts, so a venue called "Stop & Shop" keeps its name. An
    unnamed as-directed stop is named after its market instead ("As directed — Irvine")."""
    label = (stop.get("label") or "").strip()
    kind = stop.get("kind") or "address"
    needs_label = not label or quote_view.STOP_PLACEHOLDER.fullmatch(label) is not None
    if needs_label and kind == "as_directed":
        city = (stop.get("service_area") or "").split("/")[0].split(",")[0].strip()
        label, needs_label = (f"As directed — {city}" if city else "As directed"), False
    elif needs_label:
        label = "Airport (label needed)" if kind == "airport" else "Stop (label needed)"
    out = {"label": label}
    # An as-directed stop's "address" is Core's placeholder for it ("As Directed - Irvine,
    # California"), not a place; printed beside the label it reads "As Directed · As
    # Directed - Irvine, California". The label already says it.
    if stop.get("address") and kind != "as_directed":
        out["address"] = stop["address"]
    out["kind"] = kind
    if kind == "airport":
        out["flight"] = {
            "tbd": bool(stop.get("flight_tbd")),
            "type": stop.get("flight_type"),
            "scheduled_time": stop.get("flight_time"),
        }
    if stop.get("latitude") is not None and stop.get("longitude") is not None:
        out["lat"], out["lon"] = stop["latitude"], stop["longitude"]
    if kind == "as_directed":
        out["as_directed"] = True
    if stop.get("wait_hours"):
        out["wait_hours"] = stop["wait_hours"]
    if needs_label:
        out["needs_label"] = True
    return out


def normalize_unit(unit):
    """One quote-view unit as a leg."""
    pricing = unit.get("pricing") or {}
    view_stops = unit.get("stops") or []
    stops = [normalize_stop(s) for s in view_stops]
    adj = pricing.get("adjustments") or {}
    std_rate = pricing.get("base_rate_amount")
    eff_rate = pricing.get("effective_rate_amount")
    bps = adj.get("discount_basis_points") or adj.get("custom_discount_basis_points") or 0
    # An ADDITIONAL discount asked for in the document flow comes back as its own basis
    # points; `discount_basis_points` keeps reporting only the contracted one. Reading just
    # that field made the extra discount invisible as a line while still being inside Core's
    # net, so C5's remainder swept it into the fuel line and printed a NEGATIVE "Fuel
    # surcharge" at a positive percentage. The total stayed exact, which is precisely why
    # nothing caught it: C4 compares totals, and the total was never wrong.
    temp_bps = adj.get("temporary_discount_basis_points") or 0
    eff_bps = adj.get("effective_discount_basis_points") or 0
    if eff_bps and bps and temp_bps and bps + temp_bps != eff_bps:
        print(f"WARNING: Core's discount basis points do not add up on unit "
              f"{unit.get('key')}: contracted {bps} + temporary {temp_bps} != effective "
              f"{eff_bps}. Presenting the parts Core stated; check the quote.", file=sys.stderr)
    engine_discount_pct = None
    if bps and std_rate and eff_rate and std_rate > eff_rate:
        engine_discount_pct = bps / 100.0
    engine_fuel_pct = (adj.get("fuel_surcharge_basis_points") or 0) / 100.0 or None
    engine_handling_pct = (adj.get("special_handling_basis_points") or 0) / 100.0 or None
    pickup_service_area = next((s.get("service_area") for s in view_stops if s.get("service_area")), None)
    # No stop in this unit sits in a Savoya service area at all. Core still prices it,
    # from whichever market owns the nearest fleet, and bills the positioning -- which
    # is the EXPENSIVE sourcing case, not an edge case. On 10 Oct 2026 a Catania airport
    # transfer of 36 minutes came back as 14.75 hours hourly from Naples: $9,233.50 for
    # one leg, and with its return $18,623 of a $23,259 quote.
    #
    # Core reports primary == source for it, because Naples genuinely is both the primary
    # and the source market of that unit. So `source != primary` -- the test for an
    # ordinary cross-market override -- is FALSE here, and the costly case was the one
    # case the sourcing marker missed.
    #
    # A view stop carries `service_area: null` only when Core said the place is in no
    # market; the key is absent when Core did not say, which must not read as "nowhere".
    orphan_stops = bool(view_stops) and all(
        "service_area" in s and not s["service_area"] for s in view_stops)
    # Cross-market sourcing (PRD R48-R51). Core carries ONE source per unit, not an
    # array per leg: a mixed-market package is several units, each with its own
    # source_service_area, which is exactly how calculate_sourced_quote_units takes
    # the allocation. `service_area` therefore means "where this vehicle came from",
    # and `primary_service_area` means "where the work is".
    source_service_area = unit.get("source_service_area")
    service_area = source_service_area or pickup_service_area
    primary_service_area = unit.get("primary_service_area") or pickup_service_area
    leg = {
        "key": unit.get("key"),
        "service_area": service_area,
        "primary_service_area": primary_service_area,
        "sourced_from_other_market": bool(service_area and (
            orphan_stops
            or (source_service_area and source_service_area != primary_service_area))),
        "no_local_service_area": orphan_stops,
        "label": unit.get("label") or unit.get("key"),
        "date": unit.get("pickup_date"),
        "passenger_count": unit.get("passenger_count"),
        "vehicle": {
            "name": unit.get("vehicle_name"),
            "capacity": unit.get("vehicle_capacity"),
            "quantity": unit.get("quantity") or 1,
        },
        "stops": stops,
        "pricing": {
            "method": pricing.get("pricing_method"),
            "rate_cents": std_rate if engine_discount_pct else eff_rate,
            "billable_hours": pricing.get("billable_hours"),
            "minimum_hours": pricing.get("minimum_hours"),
            "cancellation_hours": pricing.get("cancellation_hours"),
            "special_event": event_for_client(pricing.get("special_event"), unit.get("pickup_date")),
            "per_vehicle_cents": unit.get("per_vehicle_amount"),
            "line_total_cents": unit.get("total_amount"),
        },
        "client_notes": [],
    }
    # The excess drive-time cost of pulling this vehicle from another market. R51 says
    # it is disclosed as its own visible line, never folded silently into the rate, so
    # it is kept as a named amount here rather than appended as prose to client_notes.
    #
    # ASSUMPTION, and a deliberate one: `incremental_client_amount` is treated as a
    # component ALREADY INSIDE `line_total_cents`, not an addition to it. If that is
    # backwards, the money-ownership check (C4) fails closed and refuses to render
    # rather than shipping a wrong total — which is the point of C4. Confirm against a
    # real sourced quote before trusting either reading.
    drive = unit.get("sourcing_drive_time") or {}
    if drive.get("additional_quoted_time_hours") is not None or \
            drive.get("incremental_client_amount") is not None:
        leg["pricing"]["sourcing_drive_time"] = {
            "from_service_area": source_service_area,
            "additional_quoted_hours": drive.get("additional_quoted_time_hours"),
            "amount_cents": drive.get("incremental_client_amount"),
        }
    if engine_fuel_pct:
        leg["engine_fuel_pct"] = engine_fuel_pct
    if engine_handling_pct:
        leg["engine_handling_pct"] = engine_handling_pct
    # D1 — a greeter drives nowhere. Core still reports a travel_time on the as-directed
    # stop (6 minutes at Whistler, 5 at Irvine, 13 on the wrong hotel-to-venue shape), and
    # "5 min drive" against a person meeting a flight is the kind of detail a client notices.
    is_greeter = "greet" in (unit.get("vehicle_name") or "").lower()
    if is_greeter:
        leg["is_greeter"] = True
    # Drive times are Core's: the view carries the minutes from the previous stop on each
    # stop. A greeter's are dropped (D1 above); a stop with none gets none, never a zero.
    tt = [] if is_greeter else [s.get("drive_minutes") for s in view_stops]
    if any(tt):
        for s_, minutes in zip(leg["stops"], tt):
            if minutes:
                s_["drive_minutes"] = minutes
        leg["route"] = {"drive_min": int(sum(x for x in tt if x)), "source": "engine"}
    if engine_discount_pct:
        # Present standard rates on the line; the engine's discount becomes a visible line item.
        qty = leg["vehicle"]["quantity"] or 1
        hourly = leg["pricing"]["method"] == "hourly"
        units = (leg["pricing"]["billable_hours"] or 0) if hourly else 1
        if hourly:
            per = std_rate * units
        else:
            per = round((unit.get("per_vehicle_amount") or 0) * std_rate / eff_rate)
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
        if temp_bps:
            leg["engine_temp_discount_pct"] = temp_bps / 100.0
            # Core's own words for it reach the client document, so they are read rather
            # than invented -- but they are NOT published unexamined. See client_label().
            leg["engine_temp_discount_label"] = client_label(
                adj.get("temporary_discount_label"))
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
    # Say it ONCE. The renderers draw a marker under any leg flagged
    # `sourced_from_other_market`, placed next to the line it explains, which is where
    # R51 wants it. This note predates that marker and says the same thing in LINE
    # NOTES. On the real Irvine quote both fired: every leg was `excess_drive_time` AND
    # sourced, so the client PDF said "positioned from our San Diego, CA partners"
    # twice per leg. Caught by replaying the capture before the build shipped.
    #
    # The two cover complementary halves and both are needed: the marker handles a named
    # source market, the note handles positioning with no market to name -- Whistler out
    # of Vancouver, Catania out of Naples -- where there is no second line for a reader
    # to be confused by.
    if note is not None and not leg.get("sourced_from_other_market"):
        where = f"our {note} partners" if note else "a neighbouring market"
        leg["client_notes"].append(
            f"Vehicles for this service are positioned from {where}; additional drive time "
            f"is included in the reservation.")
    if leg["pricing"]["method"] != "hourly":
        leg["pricing"]["billable_hours"] = None
        leg["pricing"]["minimum_hours"] = None
    # The MCP passes only priced units in a successful result; a unit with no amount is
    # the one case where Core's passenger note may explain something and is kept.
    unit_priced = unit.get("total_amount") is not None
    internal = {
        "rate_ids": [pricing.get("rate_id")] if pricing.get("rate_id") else [],
        "warnings": [w for w in (unit.get("warnings") or [])
                     if not (SUPPRESSED_WARNING in w and unit_priced)],
        "placeholders": [],
    }
    for s in stops:
        if s.get("kind") == "airport" and s.get("flight", {}).get("tbd"):
            internal["placeholders"].append(
                f"{leg['key']}: flight time {s['flight'].get('scheduled_time')} is a placeholder (TBD flight)")
    # The costly sourcing case, stated in money so it cannot be skimmed past. A 36-minute
    # Catania transfer billed 14.75 hours out of Naples -- $9,233.50, and $18,623 with its
    # return, against a $23,259 quote. The client-facing marker says where the vehicle
    # came from; this says what it cost, to the CSM, before anything is sent.
    if leg.get("no_local_service_area"):
        hrs = leg["pricing"].get("billable_hours")
        amount = leg.get("engine_net_line_cents")
        internal["placeholders"].append(
            f"{leg['key']}: NO SAVOYA SERVICE AREA at any stop. Core priced it from "
            f"{leg.get('service_area') or 'the nearest market'}"
            + (f" and billed {hrs:g} hours" if hrs else "")
            + (f" = ${amount / 100:,.2f}" if amount else "")
            + ". Positioning drive time is inside that figure. Confirm with the CSM "
              "before this goes to a client.")
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
        b_ = os.path.join(args.from_handoff, "blocked.json")
        if os.path.exists(b_):
            try:
                r_ = json.load(open(b_, encoding="utf-8"))
            except (OSError, ValueError):
                r_ = {}
            sys.exit(f"The handoff write was refused ({r_.get('gate', '?')}): {r_.get('reason', 'see blocked.json')}\nFix: {r_.get('fix', 'fix the cause and write the handoff again')}\n"
                     "Do not carry on by hand: no hand-built intake.json, no decisions kept in your head, no calling the scripts' internals. "
                     "Fix the cause and write again, or stop and tell the user why (R92).")
        handoff = json.load(open(os.path.join(args.from_handoff, "intake.json"), encoding="utf-8"))
        # R108: the user answers operational client requests before the document inputs are built. The answers
        # are read here; an answer recorded afterwards is not in quote.json and the document would contradict it.
        from client_requests import request_keys as _request_keys
        _open = [k for k in _request_keys(handoff.get("client_questions")) if k not in (handoff.get("decisions") or {})]
        if _open:
            _qs = handoff.get("client_questions") or []
            sys.exit("The user has not answered " + str(len(_open)) + " client request(s) yet (R108): "
                     + "; ".join(f"{k} \"{_qs[int(k.split(':')[1])]}\"" for k in _open) + ".\n"
                     "Ask them first: run decide.py --next, put each question to the user, record each answer with decide.py request:<n> <answer>, "
                     "and stop asking when the next key is not request:<n>. Then run this again. Never answer for the user.")
        # F2 — a stale handoff is REJECTED, not interpreted. A v1 or v2 handoff was written
        # against the previous MCP contract, where estimate_type could be "approximate", a
        # passenger id was always present, and the sourcing market arrived on the quote.
        # Reading those fields as if they still mean what they meant produces a document
        # that looks right, which is worse than one that refuses.
        ver = handoff.get("contract")
        if ver != HANDOFF_CONTRACT:
            sys.exit(
                f"This handoff was written by an older version of the plugin "
                f"(contract {ver}, this build needs {HANDOFF_CONTRACT}).\n"
                "The quote behind it predates the current Savoya contract, so building a\n"
                "document from it would produce numbers that look right and aren't.\n"
                "\nRe-run the quote in intake and the handoff will be rewritten.")
        if not handoff.get("final"):
            sys.exit("Handoff is not final — the quote hasn't been confirmed by the user.")
        args.raw = args.raw or os.path.join(args.from_handoff, "raw_quote.json")
        args.client = args.client or handoff["client"].get("display_name") or handoff["client"]["name"]
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

    # The response is read through quote_view, which hands back packages of view units
    # and refuses any presentation version this build does not read, loudly.
    try:
        pkgs = quote_view.packages(raw)
    except quote_view.QuoteViewError as e:
        sys.exit(str(e))
    if not pkgs:
        sys.exit("The quote result has no priced packages.")
    # generate_quote_options returns several complete packages; one is chosen.
    if quote_view.is_options(raw):
        keys = [p["key"] for p in pkgs]
        want = args.option or (handoff or {}).get("selected_option")
        chosen = next((p for p in pkgs if p["key"] == want), None)
        if chosen is None:
            if want:
                sys.exit(f"Option {want!r} not in this response. Available: {keys}")
            if len(pkgs) > 1:
                sys.exit(f"This is a multi-option response ({keys}). Pass --option <key> for the one the user chose.")
            chosen = pkgs[0]
        print(f"Using option {chosen['key']!r} from a multi-option response", file=sys.stderr)
    else:
        chosen = pkgs[0]
    units = chosen["units"]
    unpriced = [f"{k}: no quoteable vehicle option" for k in chosen.get("unpriced") or []]
    selected = set(k.strip() for k in args.select.split(",")) if args.select else None

    alt_map = dict(a.split(":", 1) for a in args.alternative)
    legs, dropped, warnings, placeholders, rate_ids = [], [], list(unpriced), [], []
    for u in units:
        if selected is not None and u.get("key") not in selected:
            dropped.append(u.get("key"))
            continue
        leg, internal = normalize_unit(u)
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

    # R98: a stop the user is holding open prints a neutral label, never the resolved name or
    # address. The resolved location still priced the leg and still places the map pin.
    for ps_ in ((handoff or {}).get("placeholder_stops") or []):
        for leg in legs:
            if leg["key"] != ps_.get("unit"):
                continue
            for st in leg["stops"]:
                if ps_["stop"].lower() in (st.get("label") or "").lower() or ps_["stop"].lower() in (st.get("address") or "").lower():
                    st["label"] = ps_["label"]
                    st["placeholder"] = True
                    st.pop("address", None)
                    st.pop("needs_label", None)
    for v_ in ((handoff or {}).get("venue_names") or []):          # R62: the venue the client named, not the address Core resolved
        for leg in legs:
            if leg["key"] == v_.get("unit"):
                for st in leg["stops"]:
                    if v_["stop"].lower() in (st.get("label") or "").lower():
                        st["label"] = v_["label"]
                        st.pop("needs_label", None)
    fl = {f.get("unit"): f.get("text") for f in ((handoff or {}).get("flight_details") or [])}
    for leg in legs:
        if fl.get(leg["key"]):
            leg["flight_supplied"] = fl[leg["key"]]               # R74: printed as given, never "to be confirmed"
    placeholders[:] = [p for p in placeholders if not any(p.startswith(k + ":") for k in fl if fl.get(k))]   # R74: a supplied flight is no placeholder
    tr = {r.get("unit"): r for r in ((handoff or {}).get("time_readings") or [])}
    for leg in legs:
        r = tr.get(leg["key"])
        if r and r.get("airport_target"):
            leg["airport_target"] = r["airport_target"]   # R34: printed beside the pickup
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
    # The additional discount is its own line, pinned per leg at Core's granularity exactly
    # as the contracted one is (C5). Core also sends `temporary_discount_amount`, but that
    # figure is grossed up by the fuel surcharge ($49.50 where the standard-rate line is
    # $45.00 on the sedan fixture), so it is not the amount this presentation wants —
    # standard -> discounts -> fuel -> net. Deriving it the same way as the contracted line
    # keeps the two consistent and keeps fuel as the honest remainder.
    tpcts = {l.get("engine_temp_discount_pct") for l in legs if l.get("engine_temp_discount_pct")}
    if len(tpcts) == 1:
        tpct = tpcts.pop()
        label = next((l.get("engine_temp_discount_label") for l in legs
                      if l.get("engine_temp_discount_label")), "Additional discount")
        tdisc = 0
        for l in legs:
            if l.get("alternative_of"):
                continue
            std = l.get("engine_standard_rate_cents") or 0
            rate_units = l.get("engine_rate_units") or 0
            qty = (l.get("vehicle") or {}).get("quantity") or 1
            tdisc -= round(std * tpct / 100.0) * rate_units * qty
        adjustments.append({"label": label, "type": "percent", "value": -tpct,
                            "applies_to": None, "source": "engine", "amount_cents": 0,
                            "amount_cents_fixed": int(tdisc)})
    elif len(tpcts) > 1:
        print("WARNING: legs carry different additional discounts; not presenting one as a "
              "single line", file=sys.stderr)
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
        # Every discount line already placed, not just the contracted one — otherwise the
        # remainder re-absorbs the additional discount and we are back to a negative
        # "Fuel surcharge".
        disc_amt = sum((a.get("amount_cents_fixed") or 0) for a in adjustments
                       if a.get("source") == "engine" and (a.get("value") or 0) < 0)
        adjustments.append({"label": "Fuel surcharge", "type": "percent", "value": fpc.pop(),
                            "applies_to": None, "source": "engine", "amount_cents": 0,
                            "amount_cents_fixed": int(net - std - disc_amt)})
    quote = {
        "meta": {
            "client": args.client,
            # The profile the quote ran under, as intake recorded it. The view does not carry
            # it, and no Core response ever did on a unit in any capture.
            "profile_id": ((handoff or {}).get("client") or {}).get("profile_id"),
            "prepared_by": args.prepared_by,
            # R109: the headcount the user confirmed. The header prints it; legs priced without a
            # passenger_count (a vehicle default) cannot say how many people the party is.
            "headcount": (handoff or {}).get("headcount_confirmed"),
            "prepared_on": today.isoformat(),
            "valid_until": (today + dt.timedelta(days=args.valid_days)).isoformat(),
            "estimate_type": chosen.get("estimate_type"),
            "currency": chosen.get("currency") or "USD",
            "title": args.title,
            "reference": None,
            "travel_coordinator": None,
            # Where the WORK is, not where the vehicles came from. Since sourcing,
            # `service_area` on a leg means the source market, so reading it here put
            # "San Diego, CA" on the header of an Orange County event whose Mini Buses
            # happened to be positioned from San Diego. The session caught it by hand.
            "service_area": next((l.get("primary_service_area") for l in legs
                                  if l.get("primary_service_area")),
                                 next((l.get("service_area") for l in legs
                                       if l.get("service_area")), None)),
        },
        "legs": legs,
        "engine_total_cents": chosen["total_cents"],
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
        # R73: requests the client made that Core cannot answer. Carried, never resolved here.
        "user_supplied_facts": list((handoff or {}).get("user_supplied_facts") or []),   # R35: the only dimensions a document may print
        "client_requests": __import__("client_requests").carry((handoff or {}).get("client_questions"), (handoff or {}).get("decisions")),
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
