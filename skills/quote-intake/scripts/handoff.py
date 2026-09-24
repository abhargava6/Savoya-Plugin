#!/usr/bin/env python3
"""Intake helpers — everything between an engine response and the chat reply is deterministic.

  handoff.py summarize <raw.json> [--select <option_key>]
      → markdown. Handles generate_quote_options (scenarios) and
        calculate_quote_units / plan_approximate_quote_units (single package).

  handoff.py write --dir handoff --client "Yerdle" --profile-id 201890 \
      --request request.md --raw raw_quote.json --tool calculate_quote_units --mode best \
      [--scenarios scenarios.json] [--selected <option_key>] \
      [--unit key=structure:rationale]... [--placeholder "..."]... [--ambiguity "..."]... \
      [--passenger-id N --passenger-name "..."] [--rate-sheet-shown] [--final]

  handoff.py client "Yerdle"                 → cached profile id, else exit 1
  handoff.py passenger <profile_id>          → cached "id<TAB>name", else exit 1
  handoff.py remember-passenger <profile_id> <passenger_id> "<name>"
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
HERE = os.path.dirname(os.path.abspath(__file__))


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
    if isinstance(raw, dict) and raw.get("options"):
        return "scenarios"
    if isinstance(raw, dict) and raw.get("quote_units") is not None:
        return "package"
    return "unknown"


def packages(raw):
    """Normalize either shape into [(key, label, strategy, quote_units, total)]."""
    if shape_of(raw) == "scenarios":
        out = []
        for o in raw["options"]:
            r = o.get("result") or {}
            out.append((o.get("key"), o.get("label") or o.get("key"), o.get("strategy"),
                        r.get("quote_units") or [], r.get("aggregate_total")))
        return out
    return [(None, None, None, raw.get("quote_units") or [], raw.get("aggregate_total"))]


def route_of(unit):
    names = []
    for s in unit.get("stops") or []:
        n = s.get("name") or s.get("display_name") or "Stop"
        n = n.split(",")[0].strip()
        wait = s.get("duration") or 0
        names.append(f"{n} ({wait:g}h wait)" if wait else n)
    return " → ".join(names)


def basis_of(ps):
    rate = ps.get("rate") or {}
    std, eff = rate.get("base_rate_amount"), rate.get("effective_rate_amount")
    bps = (ps.get("adjustments") or {}).get("discount_basis_points") or 0
    if ps.get("pricing_method") == "hourly":
        hrs = (ps.get("calculation") or {}).get("billable_hours")
        txt = f"{hrs:g} hr × {money(eff)}/hr" if hrs else f"{money(eff)}/hr"
        if rate.get("minimum_hours"):
            txt += f" ({rate['minimum_hours']:g}-hr min)"
    else:
        txt = f"transfer {money(eff)}"
    if bps and std and std != eff:
        txt += f" — {money(std)} less {bps/100:g}%"
    return txt


def unit_lines(unit, indent="  "):
    ps = unit.get("pricing_summary") or {}
    vt = unit.get("vehicle_type") or {}
    qty = unit.get("quantity") or 1
    head = f"{indent}**{day(unit.get('pickup_date'))}** · {unit.get('passenger_count')} pax · {route_of(unit)}"
    body = f"{indent}{qty} × {vt.get('name')} ({vt.get('capacity')} pax) — {basis_of(ps)} → **{money(unit.get('line_total'))}**"
    cx = ps.get("cancellation_hours")
    if cx is not None:
        body += f" · {cx}-hr cancel"
    out = [head, body]
    if ps.get("special_event"):
        out.append(f"{indent}⚠ {ps['special_event'].get('name')} event pricing in effect")
    for w in unit.get("warnings") or []:
        if "No local providers" in w:
            m = re.search(r"providers in ([^.]+)\.", w)
            out.append(f"{indent}⚠ positioned from {m.group(1).strip() if m else 'a nearby market'} — extra drive time included")
        elif "not quoteable" in w:
            out.append(f"{indent}✗ {w.split(' was not quoteable')[0]}: no rate in this market")
    chosen_total = unit.get("line_total") or 0
    for alt in unit.get("vehicle_options") or []:
        av = alt.get("vehicle_type") or {}
        if not alt.get("quoteable") or av.get("id") == vt.get("id"):
            continue
        at = alt.get("line_total") or 0
        flag = ""
        if chosen_total and at and at < chosen_total * 0.7:
            flag = "  ← **cheaper; check the candidate set**"
        out.append(f"{indent}  alt: {alt.get('quantity')} × {av.get('name')} → {money(at)}{flag}")
    return out


def summarize(raw, select=None):
    pkgs = packages(raw)
    est = None
    for _, _, _, units, _ in pkgs:
        for u in units:
            est = (u.get("pricing_summary") or {}).get("estimate_type") or est
    lines, multi = [], len(pkgs) > 1
    for key, label, _strategy, units, total in pkgs:
        if multi:
            mark = " ← recommended" if (key == select if select else key == pkgs[0][0]) else ""
            lines.append(f"### {label}{mark} — **{money(total)}**")
        for u in units:
            lines += unit_lines(u)
            lines.append("")
    if not multi:
        lines.append(f"**Total: {money(pkgs[0][4])}**")
    bps, fuel = set(), set()
    for _, _, _, units, _ in pkgs:
        for u in units:
            adj = (u.get("pricing_summary") or {}).get("adjustments") or {}
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


def write(a):
    os.makedirs(a.dir, exist_ok=True)
    shutil.copy(a.request, os.path.join(a.dir, "request.md"))
    shutil.copy(a.raw, os.path.join(a.dir, "raw_quote.json"))
    if a.scenarios:
        shutil.copy(a.scenarios, os.path.join(a.dir, "scenarios.json"))
    raw = load_json(a.raw, {}) or {}
    pkgs = packages(raw)
    chosen = next((p for p in pkgs if p[0] == a.selected), pkgs[0])
    units_src = chosen[3]
    missing = [u.get("key") for u in units_src if not u.get("pickup_date")]
    if missing:
        sys.exit(f"Refusing to write handoff: units without pickup_date: {missing}.")
    struct = {}
    for spec in a.unit:
        k, _, rest = spec.partition("=")
        s, _, r = rest.partition(":")
        struct[k] = {"structure": s, "rationale": r}
    units = []
    for u in units_src:
        ps = u.get("pricing_summary") or {}
        vt = u.get("vehicle_type") or {}
        units.append({
            "key": u.get("key"), "label": u.get("label"), "date": u.get("pickup_date"),
            "passenger_count": u.get("passenger_count"),
            "structure": struct.get(u.get("key"), {}).get("structure"),
            "rationale": struct.get(u.get("key"), {}).get("rationale"),
            "vehicle": {"id": vt.get("id"), "name": vt.get("name"), "quantity": u.get("quantity")},
            "line_total": u.get("line_total"),
            "pricing_method": ps.get("pricing_method"),
            "adjustments": ps.get("adjustments"),
        })
    est = next(((u.get("pricing_summary") or {}).get("estimate_type") for u in units_src), None)
    path = os.path.join(a.dir, "intake.json")
    prev = load_json(path, {}) or {}
    intake = {
        "contract": 2,
        "client": {"name": a.client, "profile_id": a.profile_id, "source": a.client_source},
        "passenger": {"id": a.passenger_id, "name": a.passenger_name,
                      "note": "pricing is passenger-independent; required by the reservation builder"},
        "tool": a.tool, "estimate_type": est, "quote_mode": a.mode,
        "selected_option": a.selected, "option_keys": [p[0] for p in pkgs if p[0]],
        "units": units,
        "rate_sheet_shown": a.rate_sheet_shown,
        "ambiguities": a.ambiguity, "placeholders": a.placeholder,
        "client_questions": a.client_question, "final": a.final,
        "selection": {"select": [u["key"] for u in units], "alternatives": {}},
        "decisions": prev.get("decisions", {}),
        "log": prev.get("log", []) + [{"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                       "step": "quote",
                                       "note": f"{a.tool}, mode={a.mode}, option={a.selected}, final={a.final}"}],
    }
    json.dump(intake, open(path, "w", encoding="utf-8"), indent=2)
    if a.client and a.profile_id:
        cfg = load_json(CONFIG, {}) or {}
        cfg.setdefault("known_clients", {})[a.client] = a.profile_id
        if a.passenger_id:
            cfg.setdefault("known_passengers", {})[str(a.profile_id)] = {"id": a.passenger_id, "name": a.passenger_name}
        save_config(cfg)
    print(f"Handoff written to {a.dir}/ ({len(units)} units, {a.tool}, {est}, final={a.final})")


def capture(a):
    intake = load_json(os.path.join(a.dir, "intake.json"), {}) or {}
    raw = load_json(os.path.join(a.dir, "raw_quote.json"), {}) or {}

    def slim_units(us):
        out = []
        for u in us:
            su = {k: v for k, v in u.items() if k not in ("vehicle_options", "stops", "quote")}
            su["stops"] = [{k: v for k, v in s.items() if k in ("name", "display_name", "duration", "flight")}
                           for s in (u.get("stops") or [])]
            out.append(su)
        return out

    if shape_of(raw) == "scenarios":
        slim = {"options": [{"key": o.get("key"), "label": o.get("label"),
                             "aggregate_total": (o.get("result") or {}).get("aggregate_total"),
                             "quote_units": slim_units((o.get("result") or {}).get("quote_units") or [])}
                            for o in raw["options"]]}
    else:
        slim = {k: v for k, v in raw.items() if k not in ("presentation", "quote_units")}
        slim["quote_units"] = slim_units(raw.get("quote_units") or [])
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
    w.add_argument("--raw", required=True); w.add_argument("--scenarios", default=None)
    w.add_argument("--mode", default="best"); w.add_argument("--tool", default="calculate_quote_units")
    w.add_argument("--selected", default=None)
    w.add_argument("--unit", action="append", default=[]); w.add_argument("--ambiguity", action="append", default=[])
    w.add_argument("--placeholder", action="append", default=[]); w.add_argument("--rate-sheet-shown", action="store_true")
    w.add_argument("--client-question", action="append", default=[],
                   help="a client question that does not change pricing; answered in the document stage")
    w.add_argument("--final", action="store_true"); w.add_argument("--client-source", default="resolve")
    w.add_argument("--passenger-id", type=int, default=None); w.add_argument("--passenger-name", default=None)
    c = sub.add_parser("client"); c.add_argument("name")
    pg = sub.add_parser("passenger"); pg.add_argument("profile_id")
    rp = sub.add_parser("remember-passenger"); rp.add_argument("profile_id"); rp.add_argument("passenger_id"); rp.add_argument("name")
    cp = sub.add_parser("capture"); cp.add_argument("--dir", default="handoff"); cp.add_argument("--slug", default=None)
    cp.add_argument("--worked", default=None); cp.add_argument("--change", default=None)
    a = ap.parse_args()

    if a.cmd == "summarize":
        print(summarize(load_json(a.raw, {}) or {}, a.select))
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
    elif a.cmd == "passenger":
        cfg = load_json(CONFIG, {}) or {}
        p = (cfg.get("known_passengers") or {}).get(str(a.profile_id))
        if p:
            print(f"{p['id']}\t{p.get('name') or ''}"); return
        sys.exit(1)
    else:
        cfg = load_json(CONFIG, {}) or {}
        cfg.setdefault("known_passengers", {})[str(a.profile_id)] = {"id": int(a.passenger_id), "name": a.name}
        save_config(cfg); print("ok")


if __name__ == "__main__":
    main()
