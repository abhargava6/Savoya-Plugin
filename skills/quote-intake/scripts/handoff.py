#!/usr/bin/env python3
"""Intake helpers — everything between an engine response and the chat reply is deterministic.

  handoff.py summarize <raw.json> [--select <option_key>]
      → markdown. Handles generate_quote_options (scenarios) and
        calculate_quote_units / calculate_temporary_quote_units (single package).

  handoff.py write --dir handoff --client "Yerdle" --profile-id 201890 \
      --request request.md --raw raw_quote.json --tool calculate_quote_units --mode best \
      [--scenarios scenarios.json] [--selected <option_key>] \
      [--unit key=structure:rationale]... [--placeholder "..."]... [--ambiguity "..."]... \
      [--passenger-id N --passenger-name "..."] [--rate-sheet-shown] [--final]

  handoff.py ingest --name A [--dir handoff] [--file response.json]   (response on stdin otherwise)
      → saves a pricing response EXACTLY as given to <dir>/responses/<name>.json, after checking
        that it parses, carries priced units, and that the unit totals add up to the response's
        own total. Never edits a figure. Exit 2 = rejected, nothing written.

  handoff.py write … --package A --package B [--shared B_key=A_key]... [--alt-of B_key=A_key]...
      → several separately priced packages as options in one handoff (R79). The first package is
        Option A; every other package's units become alternatives. Each package keeps its own
        Core total; nothing is summed or averaged.

  handoff.py client "Yerdle"                 → cached profile id, else exit 1
  handoff.py capture --dir handoff [--slug ...] [--worked ...] [--change ...]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys

CONFIG = os.path.expanduser("~/.savoya-quoting/config.json")

# The ONE Core warning we suppress, and only when the unit actually priced.
#
# We send no passenger_id unless the user named one, so Core attaching an eligible
# passenger to the unsaved calculation is the expected path, not an exception — and it
# says so on every unit, every option and the aggregate.
#
# A list of one, matched by substring, with the condition attached. NOT a filter, NOT a
# severity threshold, NOT a pattern. Suppressing Core warnings wholesale is how a real one
# gets hidden, and an allowlist of warnings we recognise does the same thing by omission:
# this file used to print only the two shapes it knew and drop everything else silently.
# Unrecognised warnings are now surfaced verbatim.
#
# The same string lives in quote-document/scripts/normalize_quote.py. regress.py asserts
# the two are identical, so the duplication cannot drift.
SUPPRESSED_WARNING = "No passenger was selected"
HERE = os.path.dirname(os.path.abspath(__file__))
# The one reader of a quote response lives with the document skill's scripts; both skills
# ship in the same plugin, side by side under skills/.
sys.path.insert(0, os.path.join(HERE, "..", "..", "quote-document", "scripts"))
import quote_view  # noqa: E402


def load_json(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), indent=2)


def money(c):
    return f"${(c or 0)/100:,.2f}"


def day(iso, fmt="%a %-m/%-d %-I:%M%p"):
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime(fmt).replace("AM", "am").replace("PM", "pm")
    except (ValueError, TypeError):
        return str(iso or "")


def shape_of(raw):
    """"scenarios" (generate_quote_options), "package" (one priced package) or "unknown".
    An unsupported presentation version is refused here, loudly."""
    try:
        if quote_view.is_options(raw):
            return "scenarios"
        quote_view.packages(raw)
        return "package"
    except quote_view.QuoteViewError as e:
        if "presentation version" in str(e):
            sys.exit(str(e))
        return "unknown"
    except (AttributeError, TypeError):
        return "unknown"


def packages(raw):
    """[(key, label, strategy, units, total)] for a quote or a comparison; units are view units."""
    try:
        return [(p["key"], p["label"], p["strategy"], p["units"], p["total_cents"]) for p in quote_view.packages(raw)]
    except quote_view.QuoteViewError as e:
        sys.exit(str(e))


def route_of(unit):
    names = []
    for s in unit.get("stops") or []:
        n = s.get("label") or "Stop"
        n = n.split(",")[0].strip()
        wait = s.get("wait_hours") or 0
        names.append(f"{n} ({wait:g}h wait)" if wait else n)
    return " → ".join(names)


def basis_of(pr):
    std, eff = pr.get("base_rate_amount"), pr.get("effective_rate_amount")
    bps = (pr.get("adjustments") or {}).get("discount_basis_points") or 0
    if pr.get("pricing_method") == "hourly":
        hrs = pr.get("billable_hours")
        txt = f"{hrs:g} hr × {money(eff)}/hr" if hrs else f"{money(eff)}/hr"
        if pr.get("minimum_hours"):
            txt += f" ({pr['minimum_hours']:g}-hr min)"
    else:
        txt = f"transfer {money(eff)}"
    if bps and std and std != eff:
        txt += f" — {money(std)} less {bps/100:g}%"
    return txt


def unit_lines(unit, indent="  ", seen=None):
    pr = unit.get("pricing") or {}
    qty = unit.get("quantity") or 1
    head = f"{indent}**{day(unit.get('pickup_date'))}** · {unit.get('passenger_count')} pax · {route_of(unit)}"
    body = f"{indent}{qty} × {unit.get('vehicle_name')} ({unit.get('vehicle_capacity')} pax) — {basis_of(pr)} → **{money(unit.get('total_amount'))}**"
    cx = pr.get("cancellation_hours")
    if cx is not None:
        body += f" · {cx}-hr cancel"
    # Cross-market sourcing. Core used to signal this only as a free-text warning
    # ("No local providers in X"), which is still translated below; it now also comes
    # back structured on the unit. Both are handled on purpose — the warning path is
    # what older captures and fixtures carry, and a signal moving is how three live
    # bugs in 0.23 happened.
    src = unit.get("source_service_area")
    primary = unit.get("primary_service_area")
    if src and src != primary:
        body += f" · sourced from {src}"
    out = [head, body]
    drive = unit.get("sourcing_drive_time") or {}
    hours = drive.get("additional_quoted_time_hours")
    delta = drive.get("incremental_client_amount")
    if hours is not None or delta is not None:
        bits = []
        if hours is not None:
            bits.append(f"+{hours:g} hr quoted time")
        if delta is not None:
            bits.append(f"{money(delta)} added to the client price")
        out.append(f"{indent}↳ excess drive time from {src or 'another market'}: "
                   + " · ".join(bits))
    if pr.get("special_event"):
        out.append(f"{indent}⚠ {pr['special_event'].get('name')} event pricing in effect")
    priced = unit.get("total_amount") is not None
    if seen is None:
        seen = set()
    for w in unit.get("warnings") or []:
        if SUPPRESSED_WARNING in w and priced:
            continue
        if w in seen:          # same warning on every unit and option — say it once
            continue
        seen.add(w)
        if "No local providers" in w:
            m = re.search(r"providers in ([^.]+)\.", w)
            out.append(f"{indent}⚠ positioned from {m.group(1).strip() if m else 'a nearby market'} — extra drive time included")
        elif "not quoteable" in w:
            out.append(f"{indent}✗ {w.split(' was not quoteable')[0]}: no rate in this market")
        else:
            # Not a shape we translate. Show it anyway, verbatim — an unrecognised
            # warning is exactly the kind we must not swallow.
            out.append(f"{indent}⚠ {w}")
    return out


def summarize(raw, select=None):
    pkgs = packages(raw)
    est = next((p["estimate_type"] for p in quote_view.packages(raw) if p.get("estimate_type")), None)
    lines, multi = [], len(pkgs) > 1
    seen_warnings = set()   # a distinct warning is shown once per quote, not once per unit
    for key, label, _strategy, units, total in pkgs:
        if multi:
            mark = " ← recommended" if (key == select if select else key == pkgs[0][0]) else ""
            lines.append(f"### {label}{mark} — **{money(total)}**")
        for u in units:
            lines += unit_lines(u, seen=seen_warnings)
            lines.append("")
    if not multi:
        lines.append(f"**Total: {money(pkgs[0][4])}**")
    bps, fuel = set(), set()
    for _, _, _, units, _ in pkgs:
        for u in units:
            adj = (u.get("pricing") or {}).get("adjustments") or {}
            if adj.get("discount_basis_points"):
                bps.add(adj["discount_basis_points"])
            if adj.get("fuel_surcharge_basis_points"):
                fuel.add(adj["fuel_surcharge_basis_points"])
    notes = []
    if bps:
        notes.append(f"includes the client's {max(bps)/100:g}% contracted discount")
    notes.append(f"fuel surcharge {max(fuel)/100:g}%" if fuel else "no fuel surcharge on this profile")
    lines.append("")
    lines.append(f"_{(est or 'exact').capitalize()} pricing — {', '.join(notes)}. Additional discounts and document options are set when you build the client document._")
    return "\n".join(lines)


def temporary_pricing_of(units):
    """The additional discount or temporary rate Core applied, read off the response.

    Core reports it per unit under `pricing_summary.adjustments`. The document flow needs
    it to draw the additional-discount line and to say the pricing was not persisted, and
    it was being hand-written into the handoff. The label is passed through as Core sent
    it; `normalize_quote.client_label()` is what makes it safe to print.
    """
    for u in units or []:
        adj = ((u.get("pricing") or {}).get("adjustments") or {})
        bps = adj.get("temporary_discount_basis_points") or 0
        rate_used = adj.get("temporary_rate_used")
        label = adj.get("temporary_discount_label")
        if bps or rate_used:
            return {
                "rate": (u.get("pricing") or {}).get("effective_rate_amount") if rate_used else None,
                "discount": ({"basis_points": bps, "label": label} if bps else None),
                "label": label,
            }
    return None


def check_response(raw):
    """Return (problems, units, total). A response is acceptable only if it is a priced package
    whose units add up to the figure the pricing system itself returned."""
    if not isinstance(raw, dict):
        return ["not a JSON object"], [], None
    if shape_of(raw) != "package":
        return ["no quote units: this is not a priced package. A generate_quote_options response is saved with ingest, which keeps each option as its own package"], [], None
    return check_package(quote_view.packages(raw)[0])


def check_package(pkg):
    """(problems, units, total) for one quote_view package: its units must add up to the
    total the pricing system itself returned. Units are quote-view units."""
    problems = []
    units = pkg.get("units") or []
    if not units:
        problems.append("no quote units")
    problems.extend(f"unit {k}: no quoteable vehicle option" for k in pkg.get("unpriced") or [])
    keys = [u.get("key") for u in units]
    if len(set(keys)) != len(keys):
        problems.append("duplicate unit keys")
    for u in units:
        if not isinstance(u.get("total_amount"), (int, float)):
            problems.append(f"unit {u.get('key')}: no numeric line total")
        if not u.get("pickup_date"):
            problems.append(f"unit {u.get('key')}: no pickup_date")
    total = pkg.get("total_cents")
    if not isinstance(total, (int, float)):
        problems.append("no quote total")
    elif not problems and sum(u["total_amount"] for u in units) != total:
        problems.append(f"unit totals add to {sum(u['total_amount'] for u in units)} but the quote total is {total}: "
                        "the text was altered or cut off. Paste the response again, whole")
    return problems, units, total


def ingest_options(a, raw):
    """A generate_quote_options response: keep each option as its own saved package, in the
    version 2 shape whatever the MCP sent (quote_view.to_v2; amounts and units untouched).
    Every option is checked as a package would be; one failure writes nothing."""
    saved, bad = [], []
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", a.name).strip("-") or "A"
    for i, pkg in enumerate(quote_view.packages(raw)):
        okey = re.sub(r"[^A-Za-z0-9_-]+", "-", str(pkg.get("key") or i + 1)).strip("-") or str(i + 1)
        problems, units, total = check_package(pkg)
        if problems:
            bad.append(f"option {okey}: " + "; ".join(problems))
        else:
            saved.append((f"{base}_{okey}", quote_view.to_v2(pkg), units, total,
                          {"key": pkg.get("key"), "label": pkg.get("label")}))
    if bad or not saved:
        print("REJECTED (nothing written):", file=sys.stderr)
        for p in bad or ["no options carry a priced result"]:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(2)
    out = os.path.join(a.dir, "responses")
    os.makedirs(out, exist_ok=True)
    # the response exactly as the MCP returned it, kept beside the per-option packages
    with open(os.path.join(out, f"{base}.options-response.json"), "w", encoding="utf-8") as fh:
        json.dump(raw, fh)
    for name, res, units, total, o in saved:
        res["_ingest"] = {"from_options_response": base, "option_key": o.get("key"), "option_label": o.get("label")}
        with open(os.path.join(out, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh)
        print(f"SAVED {os.path.join(out, name + '.json')}: {len(units)} units, total {money(total)} (units add up to the option's own total)")
    names = " ".join(f"--package {n}" for n, *_ in saved)
    print(f"{len(saved)} options saved. Write them as one document with: handoff.py write … {names} "
          "[--shared OPT_unit=A_unit] [--alt-of OPT_unit=A_unit]. The first is Option A.")


def ingest(a):
    text = open(a.file, encoding="utf-8").read() if a.file else sys.stdin.read()
    try:
        raw = json.loads(text)
    except ValueError as e:
        sys.exit(f"REJECTED (nothing written): not valid JSON ({e}). Paste the whole response, unedited.")
    if shape_of(raw) == "scenarios":
        return ingest_options(a, raw)
    problems, units, total = check_response(raw)
    if problems:
        print("REJECTED (nothing written):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(2)
    out = os.path.join(a.dir, "responses")
    os.makedirs(out, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", a.name).strip("-") or "A"
    path = os.path.join(out, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"SAVED {path}: {len(units)} units, total {money(total)} (units add up to the response's own total)")


def merge_packages(a):
    """Build raw_quote.json from separately priced packages. The first is the primary; the
    others' units become alternatives. It is written in the version 2 shape (quote_view.to_v2)
    whatever the saved responses are; unit objects are copied verbatim from the view and only
    bookkeeping is added."""
    import copy
    pk = []
    for name in a.package:
        path = os.path.join(a.dir, "responses", f"{name}.json")
        if not os.path.exists(path):
            sys.exit(f"No saved response {path}. Run: handoff.py ingest --name {name}")
        raw = load_json(path, {}) or {}
        problems, units, total = check_response(raw)
        if problems:
            sys.exit(f"Saved response {name} no longer checks out: {problems}")
        pk.append((name, raw, units, total))
    shared = dict(x.split("=", 1) for x in a.shared)        # other_key=primary_key
    alt_of = dict(x.split("=", 1) for x in a.alt_of)
    merged = quote_view.to_v2(quote_view.packages(pk[0][1])[0])
    all_units = merged["presentation"]["data"]["quote_units"]
    prim_units = list(all_units)          # Option A alone; alternatives are appended to all_units
    seen = {u["key"] for u in prim_units}
    prim_by_key = {u["key"]: u for u in prim_units}
    alternatives, meta = {}, {pk[0][0]: {"aggregate_total": pk[0][3], "unit_keys": [u["key"] for u in prim_units]}}
    for name, raw, units, total in pk[1:]:
        kept, renamed = [], {}
        for u in units:
            k = orig = u["key"]
            if k in shared:
                p = prim_by_key.get(shared[k])
                if p is None or p.get("total_amount") != u.get("total_amount"):
                    sys.exit(f"{k} is declared the same as {shared[k]} but its line total differs. "
                             "Declare it an alternative (--alt-of) or fix the pairing")
                continue                                   # carried: the primary's unit stands
            if k in seen:
                # Two packages quoted separately can reuse a key ("jun9_tour_coach"). The merge
                # namespaces it; a session never edits a saved response to avoid this.
                new = f"{name}_{k}"
                n = 2
                while new in seen:
                    new = f"{name}_{k}_{n}"; n += 1
                renamed[k] = new
                u = dict(u, key=new)
                k = new
            seen.add(k)
            twin = alt_of.get(orig) or alt_of.get(k) or (orig if orig in prim_by_key else None) or next((pu["key"] for pu in prim_units
                                          if (pu.get("pickup_date") or "")[:10] == (u.get("pickup_date") or "")[:10]), None)
            if twin is None:
                sys.exit(f"Cannot tell which Option A unit {k} replaces. Pass --alt-of {k}=<option A unit key>")
            alternatives[k] = twin
            kept.append(copy.deepcopy(u))
            if k in renamed.values():
                kept[-1]["key"] = k
        all_units.extend(kept)
        meta[name] = {"aggregate_total": total, "unit_keys": [u["key"] for u in kept], "renamed_keys": dict(renamed),
                      "shared_with_primary": {k: v for k, v in shared.items() if k in {x["key"] for x in units}}}
    merged["merged_packages"] = meta
    return merged, [u["key"] for u in prim_units], alternatives


RANGE = re.compile(r"(\d{1,4})\s*(?:-|\u2013|\u2014|to)\s*(\d{1,4})\s*(?:passengers?|guests?|people|persons?|pax|attendees|travell?ers|riders)"
                   r"|between\s+(\d{1,4})\s+and\s+(\d{1,4})\s+(?:passengers?|guests?|people|persons?|pax|attendees|travell?ers|riders)", re.I)


def headcount_range(text):
    """(low, high) when the request gives a headcount as a range, else None (R84)."""
    m = RANGE.search(text or "")
    if not m:
        return None
    lo, hi = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    lo, hi = int(lo), int(hi)
    return (lo, hi) if lo < hi else None


def refuse(a, gate, reason, fix):
    """R92: a refusal leaves a record and a way forward. `blocked.json` sits beside request.md;
    the document step refuses to run while it exists, so a refused write is never walked
    around by hand. A successful write removes it."""
    try:
        os.makedirs(a.dir, exist_ok=True)
        json.dump({"gate": gate, "reason": reason, "fix": fix,
                   "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "given": {"client": a.client, "headcount": a.headcount, "package": a.package,
                             "stop_note": a.stop_note, "selected": a.selected}},
                  open(os.path.join(a.dir, "blocked.json"), "w", encoding="utf-8"), indent=2)
    except OSError:
        pass
    sys.exit(f"Refusing to write ({gate}): {reason}\nFix: {fix}\n"
             "Do not build intake.json, decisions or the document by hand to get past this. Fix the cause and write again, "
             "or stop and tell the user why (R92).")


def _vehicle_id(value):
    """intake.json has always held Core's numeric vehicle id; the view sends it as a string."""
    return int(value) if isinstance(value, str) and value.isdigit() else value


def trip_key(u):
    """Units that serve the same trip share a pickup time and a stop list (R91)."""
    sig = []
    for s_ in u.get("stops") or []:
        sig.append((s_.get("label") or s_.get("address") or "") if isinstance(s_, dict) else str(s_))
    return ((u.get("pickup_date") or ""), tuple(sig))


def package_sets(raw, units_src, pkgs):
    """The unit lists that are each one complete priced package. In a merged response each
    package's own units plus the Option A units it shares."""
    mp = raw.get("merged_packages") if isinstance(raw, dict) else None
    if mp:
        by_key = {u.get("key"): u for u in units_src}
        out = {}
        for name, m in mp.items():
            keys = list(m.get("unit_keys") or []) + list((m.get("shared_with_primary") or {}).values())
            out[name] = [by_key[k] for k in dict.fromkeys(keys) if k in by_key]
        return out
    return {(p[0] or "quote"): p[3] for p in pkgs}


def split_problems(units, headcount):
    """R91: every unit carries its own passenger_count, and the counts of the units that serve
    one trip add up to the confirmed headcount. Never equality per unit: Core sizes the number
    of vehicles from a unit's count, so 50 on a coach and 25 on two vans is a correct 75."""
    out = []
    ok = lambda n: isinstance(n, int) and not isinstance(n, bool) and n > 0
    nocount = [u.get("key") for u in units if not ok(u.get("passenger_count"))]
    if nocount:
        out.append(f"units {nocount} were priced without a passenger_count, so their capacity is a vehicle default")
    groups = {}
    for u in units:
        if ok(u.get("passenger_count")):
            groups.setdefault(trip_key(u), []).append(u)
    for (when, _), us_ in groups.items():
        tot = sum(u["passenger_count"] for u in us_)
        if tot != headcount:
            out.append("units " + ", ".join(f"{u.get('key')} ({u['passenger_count']})" for u in us_)
                       + f" serve the same trip ({when[:16]}) and add up to {tot}, not {headcount}")
    return out


STOP_HOW = ("single_match", "user_pick", "user_address", "stand_in_chosen_by_user")


def gates(a, raw, units_src, pkgs):
    """R83 and R84 (amended by R91): the rules a session kept skipping while they were only guidance."""
    notes = []
    for n in a.stop_note:
        parts = [x.strip() for x in n.split("|")]
        if len(parts) not in (3, 5) or parts[2] not in ("resolved", "unresolved"):
            sys.exit(f"--stop-note must be '<stop>|<query sent>|resolved' or '…|unresolved', optionally followed by "
                     f"'|<stop_ref>|<how>', got {n!r}")
        note = {"stop": parts[0], "query": parts[1], "result": parts[2]}
        if len(parts) == 5:
            if parts[4] not in STOP_HOW:
                sys.exit(f"--stop-note: how a stop was settled must be one of {', '.join(STOP_HOW)}, got {parts[4]!r}")
            note["stop_ref"], note["how"] = parts[3], parts[4]
        notes.append(note)
    bad = [x for x in notes if x["result"] == "unresolved"]
    if bad:
        refuse(a, "R83", "a stop did not resolve (" + "; ".join(f"{x['stop']} via {x['query']!r}" for x in bad) + ").",
               "Ask the user for an address. Never substitute another stop, and never edit travel times or stops to get past a check.")
    rng = headcount_range(open(a.request, encoding="utf-8", errors="replace").read())
    if rng:
        if not a.headcount:
            refuse(a, "R84", f"the request gives a headcount range ({rng[0]}-{rng[1]}).",
                   "Ask the user which number to quote, re-quote with that passenger_count, then pass --headcount N.")
        if not (rng[0] <= a.headcount <= rng[1]):
            refuse(a, "R84", f"--headcount {a.headcount} is outside the requested range {rng[0]}-{rng[1]}.",
                   "Ask the user which number to quote.")
        for name, units in package_sets(raw, units_src, pkgs).items():
            probs = split_problems(units, a.headcount)
            if probs:
                refuse(a, "R84/R91", f"package {name}: " + "; ".join(probs) + ".",
                       "Re-quote so each vehicle group carries its own passenger_count and the groups serving one trip add up to "
                       f"{a.headcount} (for example 50 on the coach and 25 on the vans), then ingest again.")
    return notes


def _is_airport_stop(st):
    """A view stop says its kind; quote_view decided it from every shape Core has used."""
    return st.get("kind") == "airport"


def _span(u):
    """(start, end) in minutes from midnight of the unit's date, or None when the unit has no usable time."""
    t = (u.get("pickup_date") or "")[11:16]
    if not re.fullmatch(r"\d{2}:\d{2}", t):
        return None
    start = _hm(t)
    pr = u.get("pricing") or {}
    if pr.get("pricing_method") == "hourly":
        hrs = pr.get("billable_hours") or 0
        return start, start + int(round(float(hrs) * 60))
    return start, start + drive_minutes(u)


def drive_minutes(u):
    """Core's drive time for a unit: the minutes from the previous stop, summed over its stops."""
    return int(sum(x for x in (s.get("drive_minutes") for s in u.get("stops") or []) if isinstance(x, (int, float)) and x))


def option_sets(merged, prim_keys, alts):
    """Unit keys that belong to the same option. Option A is the primary package; every other
    option is its own units plus the Option A units it does not replace. Two units in
    different options are alternatives, never both in one trip, so they cannot overlap."""
    meta = merged.get("merged_packages") or {}
    prim = set(prim_keys)
    sets = [prim]
    for name in list(meta)[1:]:
        mine = set(meta[name].get("unit_keys") or [])
        sets.append(mine | (prim - {alts[k] for k in mine if k in alts}))
    return sets


def _stop_sig(u):
    """The stops of a unit as a comparable tuple: the address when there is one, else the label.
    The view carries no location id; within one response the address names the place."""
    return tuple(st.get("address") or st.get("label") or "" for st in (u.get("stops") or []))


def _same_trip(a, b):
    """R107: two units on the same date, at the same start time, over the same stops serve one trip in
    parallel (a Sprinter and an SUV carrying one split group). They are not an overlap."""
    sa, sb = _stop_sig(a), _stop_sig(b)
    return bool(sa) and sa == sb and a.get("pickup_date") == b.get("pickup_date")


def overlaps(units_src, sets=None):
    """R97: an hourly block that runs across an airport transfer on the same date.
    Returns [(hourly_key, transfer_key)]. Nothing is priced on an overlap without the user's answer."""
    out = []
    for h in units_src:
        if (h.get("pricing") or {}).get("pricing_method") != "hourly":
            continue
        hs = _span(h)
        for t in units_src:
            if t is h or (t.get("pickup_date") or "")[:10] != (h.get("pickup_date") or "")[:10]:
                continue
            if sets and not any(h.get("key") in s and t.get("key") in s for s in sets):
                continue
            if not any(_is_airport_stop(st) for st in (t.get("stops") or [])):
                continue
            if _same_trip(h, t):
                continue
            ts = _span(t)
            if hs and ts and ts[0] < hs[1] and hs[0] < max(ts[1], ts[0] + 1):
                out.append((h.get("key"), t.get("key")))
    return out


OVERLAP_CHOICES = ("start_after_transfer", "client_time")


def overlap_decisions(specs, units_src, sets=None):
    found = overlaps(units_src, sets)
    got, problems = [], []
    for spec in specs:
        parts = [x.strip() for x in spec.split("|")]
        if len(parts) != 3 or not (parts[2] in OVERLAP_CHOICES or re.fullmatch(r"other:\d{1,2}:\d{2}", parts[2])):
            problems.append(f"bad --overlap {spec!r}: use BLOCK|TRANSFER|start_after_transfer, client_time or other:HH:MM")
            continue
        got.append({"block": parts[0], "transfer": parts[1], "decision": parts[2]})
    answered = {(g["block"], g["transfer"]) for g in got}
    for h, t in found:
        if (h, t) not in answered:
            problems.append(f"{h} (hourly) runs across the airport transfer {t} on the same date. Ask the user: start the block after the transfer, "
                            f"start it at the client's time, or another time. Nothing is priced on the overlap until they answer")
    by = {u.get("key"): u for u in units_src}
    for g in got:
        if g["decision"] == "start_after_transfer" and by.get(g["block"]) and by.get(g["transfer"]):
            hs, ts = _span(by[g["block"]]), _span(by[g["transfer"]])
            if hs and ts and hs[0] < ts[1]:
                problems.append(f"{g['block']} still starts before {g['transfer']} ends. Re-price it after the transfer and ingest again")
    return got, problems


TIME_KINDS = ("flight_departure", "pickup", "airport_arrival_target")
ARRIVAL_WINDOW_MIN = 10   # R105: the car reaches the airport 0 to 10 minutes before the target


def _hm(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _fmt(mins):
    mins %= 1440
    return f"{mins // 60:02d}:{mins % 60:02d}"


def time_readings(specs, units_src):
    """R18/R34: how each client time was read, and the pickup that follows from it.

    Spec: KEY|kind|HH:MM[|lead_hours]. kind is flight_departure, pickup or
    airport_arrival_target. A departure gets target = departure - lead; an arrival
    target is the target. The computed pickup is target - Core's drive time. R105: the
    unit is accepted when the pickup it was PRICED at puts the car at the airport at or
    before the target and no more than ARRIVAL_WINDOW_MIN before it, using the drive time
    Core returned for that pickup; the time on the quote is the time priced. A pickup
    is the pickup, and the unit must be priced at it. Nothing is estimated here.
    """
    out, problems = [], []
    by_key = {u.get("key"): u for u in units_src}
    for spec in specs:
        parts = [x.strip() for x in spec.split("|")]
        if len(parts) < 3 or parts[1] not in TIME_KINDS or not re.fullmatch(r"\d{1,2}:\d{2}", parts[2]):
            problems.append(f"bad --time-reading {spec!r}: use KEY|{'/'.join(TIME_KINDS)}|HH:MM[|lead_hours]")
            continue
        key, kind, client = parts[0], parts[1], _hm(parts[2])
        u = by_key.get(key)
        if not u:
            problems.append(f"--time-reading names unit {key!r}, which is not in the response")
            continue
        r = {"unit": key, "kind": kind, "client_time": _fmt(client)}
        drive = drive_minutes(u)
        if kind == "pickup":
            pickup = client
        else:
            if kind == "flight_departure":
                if len(parts) < 4:
                    problems.append(f"{key}: a flight departure needs the lead time in hours (2 domestic, 3 international, or the client's own)")
                    continue
                lead = float(parts[3])
                target = client - int(round(lead * 60))
                r["lead_hours"] = lead
            else:
                target = client
            if not drive:
                problems.append(f"{key}: Core returned no travel time for this unit, so the pickup cannot be computed. Ask the user for the pickup time.")
                continue
            pickup = target - drive
            r.update(airport_target=_fmt(target), drive_minutes=drive)
        priced = (u.get("pickup_date") or "")[11:16]
        if kind == "pickup":
            r["pickup"] = _fmt(pickup)
            if priced != r["pickup"]:
                problems.append(f"{key}: the leg is priced at {priced or 'no time'} but the reading gives a pickup of {r['pickup']}. "
                                f"Re-price the unit at {r['pickup']} and ingest again.")
                continue
            out.append(r)
            continue
        # R105: a pickup that follows from a drive time is accepted when the car reaches the airport at or
        # before the target and no more than ARRIVAL_WINDOW_MIN before it, using the drive time Core returned
        # for the pickup that was priced. The time on the quote is the time priced (R34).
        computed = _fmt(pickup)
        if not re.fullmatch(r"\d{2}:\d{2}", priced or ""):
            problems.append(f"{key}: the leg has no priced pickup time. Re-price the unit at {computed} and ingest again.")
            continue
        arrival = _hm(priced) + drive
        early = (target - arrival) % 1440
        if early > ARRIVAL_WINDOW_MIN:
            problems.append(f"{key}: the leg is priced at {priced}, so the car reaches the airport at {_fmt(arrival)} for a target of {_fmt(target)} "
                            f"(accepted: {_fmt(target - ARRIVAL_WINDOW_MIN)} to {_fmt(target)}). Re-price the unit at {computed} and ingest again. "
                            f"If it is still outside, ask the user to confirm the pickup and record it with --time-reading {key}|pickup|HH:MM.")
            continue
        r.update(pickup=priced, computed_pickup=computed, priced_pickup=priced, arrival=_fmt(arrival), window_min=ARRIVAL_WINDOW_MIN)
        out.append(r)
    return out, problems


def copy_into(src, dst):
    """Copy src to dst, unless they are the same file (a session that wrote request.md
    straight into the handoff folder would otherwise crash with SameFileError)."""
    if os.path.exists(dst) and os.path.samefile(src, dst):
        return
    shutil.copy(src, dst)


def write(a):
    os.makedirs(a.dir, exist_ok=True)
    copy_into(a.request, os.path.join(a.dir, "request.md"))
    merged_sel = None
    osets = None
    if a.package:
        merged, prim_keys, alts = merge_packages(a)
        osets = option_sets(merged, prim_keys, alts) if len(a.package) > 1 else None
        json.dump(merged, open(os.path.join(a.dir, "raw_quote.json"), "w", encoding="utf-8"), indent=2)
        a.raw = os.path.join(a.dir, "raw_quote.json")
        merged_sel = {"select": prim_keys, "alternatives": alts}
    elif a.raw:
        copy_into(a.raw, os.path.join(a.dir, "raw_quote.json"))
    else:
        sys.exit("write needs --raw <file> or --package <ingested name> (repeat for options)")
    if a.scenarios:
        copy_into(a.scenarios, os.path.join(a.dir, "scenarios.json"))
    raw = load_json(a.raw, {}) or {}
    pkgs = packages(raw)
    chosen = next((p for p in pkgs if p[0] == a.selected), pkgs[0])
    chosen_pkg = next(p for p in quote_view.packages(raw) if p["key"] == chosen[0])
    units_src = chosen[3]
    stop_notes = gates(a, raw, units_src, pkgs)
    missing = [u.get("key") for u in units_src if not u.get("pickup_date")]
    if missing:
        refuse(a, "pickup_date", f"units without pickup_date: {missing}.", "Re-quote those units with a date and ingest again.")
    pstops, pprob = [], []
    for spec in a.placeholder_stop:
        unit_, stop_, label_ = (x.strip() for x in (spec.split("|", 2) + ["", ""])[:3])
        names = [n for u in units_src if u.get("key") == unit_ for n in quote_view.stop_names(u)]
        if not (unit_ and stop_ and label_) or "to be confirmed" not in label_.lower():
            pprob.append(f"bad --placeholder-stop {spec!r}: use UNIT|stop name|a neutral label that says '(... to be confirmed)'")
        elif not any(stop_.lower() in n.lower() for n in names):
            pprob.append(f"--placeholder-stop: unit {unit_!r} has no stop matching {stop_!r}")
        else:
            pstops.append({"unit": unit_, "stop": stop_, "label": label_})
    if pprob:
        refuse(a, "R98", "; ".join(pprob), "Use the stop name Core returned and a neutral label such as 'White Plains, NY (pickup address to be confirmed)'.")
    flights, venues, vprob = [], [], []
    req_text = open(a.request, encoding="utf-8", errors="replace").read()
    for spec in a.flight:
        unit_, text_ = (x.strip() for x in (spec.split("|", 1) + [""])[:2])
        if not (unit_ and text_) or unit_ not in {u.get("key") for u in units_src}:
            vprob.append(f"bad --flight {spec!r}: use UNIT|the flight details as the client gave them (number, time)")
        else:
            flights.append({"unit": unit_, "text": text_})
    for spec in a.venue:
        unit_, stop_, name_ = (x.strip() for x in (spec.split("|", 2) + ["", ""])[:3])
        names = [n for u in units_src if u.get("key") == unit_ for n in quote_view.stop_names(u)]
        if not (unit_ and stop_ and name_) or not any(stop_.lower() in n.lower() for n in names):
            vprob.append(f"bad --venue {spec!r}: use UNIT|the stop name Core returned|the venue name the client used")
        else:
            venues.append({"unit": unit_, "stop": stop_, "label": name_})
    # R74: a time or number the client supplied is never logged as a placeholder.
    if re.search(r"\b[A-Z][A-Z0-9]\s?\d{2,4}\b", req_text):
        for ph in a.placeholder:
            if re.search(r"flight", ph, re.I) and re.search(r"placeholder|tbd|assumed|to be confirmed", ph, re.I) and not a.flight:
                vprob.append(f"the request gives flight details but a placeholder says they are missing ({ph[:70]!r}). Record what the client supplied with --flight")
                break
    if vprob:
        refuse(a, "R74", "; ".join(vprob), "Record supplied flight details with --flight and the venue name with --venue; use --placeholder only for what the client did not give.")
    # R102: a stand-in client carries no discount, and the document names the real client.
    if a.client_source == "stand-in":
        sprob = []
        if not (a.prospect or "").strip():
            sprob.append("a stand-in client needs --prospect with the real client's name; the document says 'Prepared for' that name")
        found = sorted({((u.get("pricing") or {}).get("adjustments") or {}).get("discount_basis_points")
                        for u in units_src
                        if ((u.get("pricing") or {}).get("adjustments") or {}).get("discount_basis_points")})
        if found:
            sprob.append(f"the stand-in client's quote carries a {max(found)/100:g}% contracted discount, so this client is not a no-discount stand-in")
        if sprob:
            refuse(a, "R102", "; ".join(sprob),
                   "Pick an existing client with no discount on its company and none on its profile, then quote again; or quote under the real client. Give the real name with --prospect.")
    overlap, oprob = overlap_decisions(a.overlap, units_src, osets)
    if oprob:
        refuse(a, "R97", "; ".join(oprob), "Put the question to the user, record the answer with --overlap, then write again.")
    readings, tprob = time_readings(a.time_reading, units_src)
    if tprob:
        refuse(a, "R18/R34", "; ".join(tprob), "Fix the time reading or re-price, then write again.")
    facts, fprob = [], []
    for spec in a.fact:
        key, q_, ans = (x.strip() for x in (spec.split("|", 2) + ["", ""])[:3])
        if not (key and q_ and ans):
            fprob.append(f"bad --fact {spec!r}: use KEY|the question you asked the user|their answer")
        else:
            facts.append({"key": key, "question": q_, "answer": ans, "source": "user"})
    if fprob:
        refuse(a, "R35", "; ".join(fprob), "Ask the user, then record the question and their answer.")
    struct = {}
    for spec in a.unit:
        k, _, rest = spec.partition("=")
        s, _, r = rest.partition(":")
        struct[k] = {"structure": s, "rationale": r}
    units = []
    for u in units_src:
        pr = u.get("pricing") or {}
        units.append({
            "key": u.get("key"), "label": u.get("label"), "date": u.get("pickup_date"),
            "passenger_count": u.get("passenger_count"),
            "structure": struct.get(u.get("key"), {}).get("structure"),
            "rationale": struct.get(u.get("key"), {}).get("rationale"),
            "vehicle": {"id": _vehicle_id(u.get("vehicle_type_id")), "name": u.get("vehicle_name"), "quantity": u.get("quantity")},
            "line_total": u.get("total_amount"),
            "pricing_method": pr.get("pricing_method"),
            "adjustments": pr.get("adjustments"),
        })
    est = chosen_pkg.get("estimate_type")
    path = os.path.join(a.dir, "intake.json")
    prev = load_json(path, {}) or {}
    intake = {
        "contract": 3,
        "written_by": "handoff.py write",
        "client": dict({"name": a.client, "profile_id": a.profile_id, "source": a.client_source},
                       **({"display_name": a.prospect.strip()} if (a.prospect or "").strip() else {})),
        # Set only when the USER named a passenger. Omitted from the call otherwise:
        # Core attaches an eligible passenger to the unsaved calculation itself. The old
        # note here read "required by the reservation builder" — true against the previous
        # contract, not true now.
        "passenger": {"id": a.passenger_id, "name": a.passenger_name,
                      "note": "set only when the user named a passenger; otherwise Core attaches one to the unsaved quote"},
        "tool": a.tool, "estimate_type": est, "quote_mode": a.mode,
        "selected_option": a.selected, "option_keys": [p[0] for p in pkgs if p[0]],
        "units": units,
        "rate_sheet_shown": a.rate_sheet_shown,
        "headcount_confirmed": a.headcount, "stop_resolution": stop_notes,
        "ambiguities": a.ambiguity,
        "placeholders": a.placeholder + [f"Scenario reading: {r}" for r in a.reading],
        "time_readings": readings,
        "overlap_decisions": overlap,
        "placeholder_stops": pstops,
        "flight_details": flights,
        "venue_names": venues,
        "user_supplied_facts": facts,
        "client_questions": a.client_question, "final": a.final,
        "selection": merged_sel or {"select": [u["key"] for u in units], "alternatives": {}},
        "decisions": prev.get("decisions", {}),
        # DERIVED from the response, not passed in. Two of the three live sessions on
        # 10 Oct 2026 patched these into intake.json by hand -- "since handoff.py write
        # has no flags for them" -- and a hand-patched handoff is one a session can get
        # wrong or forget while firefighting. They are all in the raw quote already, so
        # asking for them as flags was the mistake, not the missing flags.
        "source_tool": a.tool,
        "persisted": chosen_pkg.get("persisted"),
        "aggregate_total": chosen_pkg.get("total_cents"),
        "temporary_pricing": temporary_pricing_of(units_src),
        "log": prev.get("log", []) + [{"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                       "step": "quote",
                                       "note": f"{a.tool}, mode={a.mode}, option={a.selected}, final={a.final}"}],
    }
    json.dump(intake, open(path, "w", encoding="utf-8"), indent=2)
    try:
        os.remove(os.path.join(a.dir, "blocked.json"))  # a successful write ends the refusal (R92)
    except OSError:
        pass
    if a.client and a.profile_id:
        cfg = load_json(CONFIG, {}) or {}
        cfg.setdefault("known_clients", {})[a.client] = a.profile_id
        # known_passengers is no longer written. It only ever served the old "take the
        # first passenger and send it" rule; we now send no passenger_id unless the user
        # named one, so a cache would do nothing but keep the placeholder disclosure
        # alive. An existing entry in someone's config is left alone rather than pruned
        # — it is their file, and a stale key costs nothing now that nothing reads it.
        save_config(cfg)
    print(f"Handoff written to {a.dir}/ ({len(units)} units, {a.tool}, {est}, final={a.final})")


def capture(a):
    intake = load_json(os.path.join(a.dir, "intake.json"), {}) or {}
    raw = load_json(os.path.join(a.dir, "raw_quote.json"), {}) or {}

    slim = raw          # the compact view is already small; the capture keeps it whole
    cfg = load_json(CONFIG, {}) or {}
    asset = load_json(os.path.join(HERE, "..", "assets", "capture.json"), {}) or {}
    base = (a.slug or (intake.get("client") or {}).get("name") or "quote").lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", base).strip("-") + "-quote-only"
    out = os.path.join(a.dir, f"{slug}.capture.json")
    cap = {"capture_version": 2, "slug": slug,
           "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "user": cfg.get("user"), "client": (intake.get("client") or {}).get("name"),
           "deliverable": "quote-only",
           "request": open(os.path.join(a.dir, "request.md"), encoding="utf-8").read(),
           "raw_quote": slim, "intake": {k: v for k, v in intake.items() if k != "log"},
           "log": intake.get("log", []),
           "feedback": {"worked": a.worked, "change": a.change, "answered": bool(a.worked or a.change)}}
    json.dump(cap, open(out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    print(json.dumps({"path": out, "title": os.path.basename(out), "bytes": os.path.getsize(out),
                      "drive_folder_id": asset.get("drive_folder_id"), "user": cfg.get("user")}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summarize"); s.add_argument("raw"); s.add_argument("--select", default=None)
    w = sub.add_parser("write")
    w.add_argument("--dir", default="handoff"); w.add_argument("--client", required=True)
    w.add_argument("--profile-id", type=int, required=True); w.add_argument("--request", required=True)
    w.add_argument("--raw", default=None); w.add_argument("--scenarios", default=None)
    w.add_argument("--package", action="append", default=[], help="name of an ingested response; repeat for options (first = Option A)")
    w.add_argument("--shared", action="append", default=[], help="OTHER_KEY=A_KEY: a unit priced identically in both packages")
    w.add_argument("--alt-of", dest="alt_of", action="append", default=[], help="B_KEY=A_KEY: the Option A unit a unit replaces")
    w.add_argument("--headcount", type=int, default=None, help="the headcount the user chose when the request gave a range (R84)")
    w.add_argument("--stop-note", dest="stop_note", action="append", default=[],
                   help="'<stop>|<query sent>|resolved|unresolved', optionally '|<stop_ref>|<how>' (how: single_match, user_pick, user_address, stand_in_chosen_by_user), for every stop lookup (R83); unresolved refuses the write")
    w.add_argument("--reading", action="append", default=[], help="how a scenario was read (vehicles, hours, headcount); R81")
    w.add_argument("--mode", default="best"); w.add_argument("--tool", default="calculate_quote_units")
    w.add_argument("--selected", default=None)
    w.add_argument("--unit", action="append", default=[]); w.add_argument("--ambiguity", action="append", default=[])
    w.add_argument("--placeholder", action="append", default=[]); w.add_argument("--rate-sheet-shown", action="store_true")
    w.add_argument("--client-question", action="append", default=[],
                   help="a client question that does not change pricing; answered in the document stage")
    w.add_argument("--placeholder-stop", dest="placeholder_stop", action="append", default=[],
                   help="UNIT|stop name|neutral label: a stop the user is holding open, such as a pickup address still to come (R98)")
    w.add_argument("--flight", action="append", default=[],
                   help="UNIT|flight details as the client gave them, such as 'BA2612 departing 2:50 PM'; printed as given (R74)")
    w.add_argument("--venue", action="append", default=[],
                   help="UNIT|stop name Core returned|the venue name the client used; the document prints the venue name (R62)")
    w.add_argument("--overlap", action="append", default=[],
                   help="BLOCK|TRANSFER|start_after_transfer, client_time or other:HH:MM: the user's answer when an hourly block runs across an airport transfer (R97)")
    w.add_argument("--fact", action="append", default=[],
                   help="KEY|the question you asked|the user's answer: a fact Core does not return, such as a vehicle length (R35)")
    w.add_argument("--time-reading", dest="time_reading", action="append", default=[],
                   help="KEY|flight_departure|HH:MM|lead_hours, KEY|airport_arrival_target|HH:MM or KEY|pickup|HH:MM (R18/R34)")
    w.add_argument("--prospect", default=None,
                   help="R102: the real client's name when the quote ran under a stand-in client (--client-source stand-in)")
    w.add_argument("--final", action="store_true"); w.add_argument("--client-source", default="resolve")
    w.add_argument("--passenger-id", type=int, default=None); w.add_argument("--passenger-name", default=None)
    ig = sub.add_parser("ingest"); ig.add_argument("--name", required=True); ig.add_argument("--dir", default="handoff")
    ig.add_argument("--file", default=None)
    c = sub.add_parser("client"); c.add_argument("name")
    cp = sub.add_parser("capture"); cp.add_argument("--dir", default="handoff"); cp.add_argument("--slug", default=None)
    cp.add_argument("--worked", default=None); cp.add_argument("--change", default=None)
    a = ap.parse_args()

    if a.cmd == "summarize":
        print(summarize(load_json(a.raw, {}) or {}, a.select))
    elif a.cmd == "ingest":
        ingest(a)
    elif a.cmd == "write":
        write(a)
    elif a.cmd == "capture":
        capture(a)
    elif a.cmd == "client":
        cfg = load_json(CONFIG, {}) or {}
        for k, v in (cfg.get("known_clients") or {}).items():
            if k.lower() == a.name.lower():
                print(v); return
        sys.exit(1)


if __name__ == "__main__":
    main()
