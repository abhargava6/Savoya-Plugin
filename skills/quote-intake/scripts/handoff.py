#!/usr/bin/env python3
"""Deterministic bridge from authoritative Savoya MCP results to documents."""

import argparse, copy, datetime as dt, json, os, re, shutil, sys

CONFIG = os.path.expanduser("~/.savoya-quoting/config.json")
HERE = os.path.dirname(os.path.abspath(__file__))
EXACT_TOOLS = {
    "calculate_quote_units",
    "calculate_temporary_quote_units",
    "generate_quote_options",
}


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def dump_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    dump_json(CONFIG, cfg)


def money(cents):
    return "—" if cents is None else f"${cents / 100:,.2f}"


def day(iso):
    try:
        value = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (
            value.strftime("%a %-m/%-d %-I:%M%p")
            .replace("AM", "am")
            .replace("PM", "pm")
        )
    except (ValueError, TypeError):
        return str(iso or "")


def result_for(raw, selected=None):
    """Return (selected exact package, selected option metadata)."""
    if not isinstance(raw, dict):
        raise ValueError("quote response is not a JSON object")
    if raw.get("options") is not None:
        options = raw.get("options") or []
        chosen = next((o for o in options if o.get("key") == selected), None)
        if chosen is None:
            if selected:
                raise ValueError(f"selected option {selected!r} is not present")
            if len(options) != 1:
                raise ValueError(
                    "one complete option must be selected before document generation"
                )
            chosen = options[0]
        return chosen.get("result") or {}, {
            k: chosen.get(k) for k in ("key", "label", "strategy")
        }
    return raw, None


def validate_exact(package):
    errors, units = [], (
        package.get("quote_units") if isinstance(package, dict) else None
    )
    if not isinstance(units, list) or not units:
        return ["selected result has no quote units"]
    if package.get("aggregate_total") is None:
        errors.append("selected result has no aggregate_total")
    if package.get("persisted") is not False:
        errors.append("selected result must explicitly be non-persisted")
    for index, unit in enumerate(units):
        key, summary = (
            unit.get("key") or f"unit {index + 1}",
            unit.get("pricing_summary") or {},
        )
        if summary.get("estimate_type") != "exact":
            errors.append(f"{key} is not exact")
        if summary.get("status") not in (None, "priced", "complete"):
            errors.append(f"{key} is not completely priced")
        for field in ("quantity", "unit_total", "line_total"):
            if unit.get(field) is None:
                errors.append(f"{key} is missing {field}")
        if not (unit.get("vehicle_type") or {}).get("id"):
            errors.append(f"{key} has no Core-selected vehicle")
    return errors


def packages(raw):
    if isinstance(raw, dict) and raw.get("options") is not None:
        return [
            (o.get("key"), o.get("label") or o.get("key"), o.get("result") or {})
            for o in raw.get("options") or []
        ]
    return [(None, None, raw or {})]


def route_of(unit):
    labels = []
    for stop in unit.get("stops") or []:
        name = (
            (stop.get("name") or stop.get("display_name") or "Stop")
            .split(",")[0]
            .strip()
        )
        wait = stop.get("duration") or 0
        labels.append(f"{name} ({wait:g}h wait)" if wait else name)
    return " → ".join(labels)


def basis_of(summary):
    rate, calc = summary.get("rate") or {}, summary.get("calculation") or {}
    effective = rate.get("effective_rate_amount")
    if summary.get("pricing_method") == "hourly":
        hours = calc.get("billable_hours")
        text = (
            f"{hours:g} hr × {money(effective)}/hr"
            if hours is not None
            else f"{money(effective)}/hr"
        )
        if rate.get("minimum_hours") is not None:
            text += f" ({rate['minimum_hours']:g}-hr min)"
        return text
    return f"transfer {money(effective)}"


def summarize(raw, select=None):
    groups, lines = packages(raw), []
    for key, label, package in groups:
        if len(groups) > 1:
            marker = (
                " ← recommended"
                if (key == select if select else key == groups[0][0])
                else ""
            )
            lines.append(
                f"### {label}{marker} — **{money(package.get('aggregate_total'))}**"
            )
        for unit in package.get("quote_units") or []:
            vehicle, summary = (
                unit.get("vehicle_type") or {},
                unit.get("pricing_summary") or {},
            )
            quantity = unit.get("quantity") if unit.get("quantity") is not None else 1
            lines += [
                f"  **{day(unit.get('pickup_date'))}** · {unit.get('passenger_count')} pax · {route_of(unit)}",
                f"  {quantity} × {vehicle.get('name')} ({vehicle.get('capacity')} pax) — {basis_of(summary)} → **{money(unit.get('line_total'))}**",
                "",
            ]
        if len(groups) == 1:
            lines.append(f"**Total: {money(package.get('aggregate_total'))}**")
    lines += ["", "_Exact, non-persisted Savoya Core pricing._"]
    return "\n".join(lines)


def selected_request(source, package, selected_option=None):
    request = copy.deepcopy(source)
    request_units = request.get("quote_units")
    if not isinstance(request_units, list) and isinstance(request.get("options"), list):
        chosen = next(
            (
                option
                for option in request["options"]
                if option.get("key") == selected_option
            ),
            None,
        )
        if chosen is None:
            raise ValueError(
                "source comparison request does not contain the selected option"
            )
        request = {"quote_units": copy.deepcopy(chosen.get("quote_units") or [])}
        request_units = request["quote_units"]
    if not isinstance(request_units, list):
        raise ValueError("source request must contain quote_units")
    chosen = {
        u.get("key"): (u.get("vehicle_type") or {}).get("id")
        for u in package["quote_units"]
    }
    if set(chosen) != {u.get("key") for u in request_units}:
        raise ValueError("source request units do not match selected result")
    for unit in request_units:
        vehicle_id = chosen[unit.get("key")]
        if not vehicle_id:
            raise ValueError(f"{unit.get('key')} has no selected vehicle id")
        unit["vehicle_type_id"] = vehicle_id
        unit.pop("vehicle_type_ids", None)
        unit.pop("candidate_vehicle_type_ids", None)
    for key in ("options", "strategies", "option_specs"):
        request.pop(key, None)
    return request


def provenance(package):
    out = []
    for unit in package.get("quote_units") or []:
        adj = (unit.get("pricing_summary") or {}).get("adjustments") or {}
        out.append(
            {
                "key": unit.get("key"),
                "temporary_rate_used": bool(adj.get("temporary_rate_used")),
                "temporary_discount_basis_points": adj.get(
                    "temporary_discount_basis_points"
                ),
                "temporary_discount_amount": adj.get("temporary_discount_amount"),
                "temporary_discount_label": adj.get("temporary_discount_label"),
            }
        )
    return out


def write_handoff(args):
    try:
        package, option = result_for(load_json(args.raw), args.selected)
    except ValueError as exc:
        sys.exit(f"Refusing handoff: {exc}")
    errors = validate_exact(package)
    if errors:
        sys.exit("Refusing handoff: " + "; ".join(errors))
    try:
        request = selected_request(
            load_json(args.source_request), package, (option or {}).get("key")
        )
    except ValueError as exc:
        sys.exit(f"Refusing handoff: {exc}")
    os.makedirs(args.dir, exist_ok=True)
    shutil.copy(args.request, os.path.join(args.dir, "request.md"))
    dump_json(os.path.join(args.dir, "raw_quote.json"), package)
    dump_json(os.path.join(args.dir, "source_request.json"), request)
    struct = {}
    for spec in args.unit:
        key, _, rest = spec.partition("=")
        structure, _, rationale = rest.partition(":")
        struct[key] = {"structure": structure, "rationale": rationale}
    units = []
    for unit in package["quote_units"]:
        vehicle = unit.get("vehicle_type") or {}
        units.append(
            {
                "key": unit.get("key"),
                "label": unit.get("label"),
                "date": unit.get("pickup_date"),
                "passenger_count": unit.get("passenger_count"),
                "structure": struct.get(unit.get("key"), {}).get("structure"),
                "rationale": struct.get(unit.get("key"), {}).get("rationale"),
                "vehicle": {
                    "id": vehicle.get("id"),
                    "name": vehicle.get("name"),
                    "quantity": unit.get("quantity"),
                },
                "line_total": unit.get("line_total"),
            }
        )
    path, previous = (
        os.path.join(args.dir, "intake.json"),
        load_json(os.path.join(args.dir, "intake.json"), {}) or {},
    )
    intake = {
        "contract": 3,
        "client": {
            "name": args.client,
            "profile_id": args.profile_id,
            "source": args.client_source,
        },
        "source_tool": args.tool,
        "selected_option": option,
        "estimate_type": "exact",
        "persisted": False,
        "currency": package.get("currency")
        or (package.get("pricing_summary") or {}).get("currency_code")
        or "USD",
        "aggregate_total": package.get("aggregate_total"),
        "warnings": package.get("warnings") or [],
        "temporary_pricing": provenance(package),
        "quote_mode": args.mode,
        "units": units,
        "rate_sheet_shown": args.rate_sheet_shown,
        "ambiguities": args.ambiguity,
        "placeholders": args.placeholder,
        "client_questions": args.client_question,
        "final": args.final,
        "decisions": previous.get("decisions", {}),
        "log": previous.get("log", [])
        + [
            {
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "step": "quote",
                "note": f"{args.tool}, mode={args.mode}, option={(option or {}).get('key')}, final={args.final}",
            }
        ],
    }
    dump_json(path, intake)
    if args.client and args.profile_id and args.client_source in ("resolve", "user"):
        cfg = load_json(CONFIG, {}) or {}
        cfg.setdefault("known_clients", {})[args.client] = args.profile_id
        save_config(cfg)
    print(
        f"Handoff written to {args.dir}/ ({len(units)} units, exact, persisted=false)"
    )


def prepare_discount(args):
    if args.percent < 0 or args.percent > 100 or int(args.percent) != args.percent:
        sys.exit("Temporary discount must be a whole percentage from 0 through 100.")
    request = load_json(os.path.join(args.dir, "source_request.json"))
    if not isinstance(request, dict) or not isinstance(
        request.get("quote_units"), list
    ):
        sys.exit("Missing valid source_request.json in the handoff directory.")
    output, units = copy.deepcopy(request), copy.deepcopy(request["quote_units"])
    for unit in units:
        unit.pop("temporary_discount", None)
        if args.percent:
            unit["temporary_discount"] = {
                "basis_points": int(args.percent * 100),
                "label": args.label,
            }
    rate_flags = [bool(unit.get("temporary_rate")) for unit in units]
    if not args.percent and any(rate_flags) and not all(rate_flags):
        sys.exit(
            "Mixed temporary pricing is unsupported: after removing the discount, only some units have temporary rates."
        )
    tool = (
        "calculate_temporary_quote_units"
        if args.percent or any(rate_flags)
        else "calculate_quote_units"
    )
    output["quote_units"] = units
    dump_json(args.out, output)
    print(
        json.dumps(
            {
                "tool": tool,
                "request": args.out,
                "basis_points": int(args.percent * 100),
            },
            indent=2,
        )
    )


def replace_result(args):
    try:
        package, option = result_for(load_json(args.raw), args.selected)
    except ValueError as exc:
        sys.exit(f"Refusing replacement: {exc}")
    errors = validate_exact(package)
    if errors:
        sys.exit("Refusing replacement: " + "; ".join(errors))
    try:
        source = selected_request(
            load_json(args.source_request), package, (option or {}).get("key")
        )
    except ValueError as exc:
        sys.exit(f"Refusing replacement: {exc}")
    dump_json(os.path.join(args.dir, "raw_quote.json"), package)
    dump_json(os.path.join(args.dir, "source_request.json"), source)
    path, intake = (
        os.path.join(args.dir, "intake.json"),
        load_json(os.path.join(args.dir, "intake.json"), {}) or {},
    )
    intake.update(
        {
            "contract": 3,
            "source_tool": args.tool,
            "selected_option": option,
            "estimate_type": "exact",
            "persisted": False,
            "currency": package.get("currency") or "USD",
            "aggregate_total": package.get("aggregate_total"),
            "warnings": package.get("warnings") or [],
            "temporary_pricing": provenance(package),
        }
    )
    intake.setdefault("log", []).append(
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "step": "re-quote",
            "note": f"authoritative result replaced via {args.tool}",
        }
    )
    dump_json(path, intake)
    print(f"Replaced authoritative handoff result via {args.tool}")


def capture(args):
    intake, raw = (
        load_json(os.path.join(args.dir, "intake.json"), {}) or {},
        load_json(os.path.join(args.dir, "raw_quote.json"), {}) or {},
    )
    slim = {k: v for k, v in raw.items() if k not in ("presentation", "quote_units")}
    slim["quote_units"] = []
    for unit in raw.get("quote_units") or []:
        item = {
            k: v
            for k, v in unit.items()
            if k not in ("vehicle_options", "stops", "quote")
        }
        item["stops"] = [
            {
                k: v
                for k, v in stop.items()
                if k in ("name", "display_name", "duration", "flight")
            }
            for stop in unit.get("stops") or []
        ]
        slim["quote_units"].append(item)
    cfg, asset = (
        load_json(CONFIG, {}) or {},
        load_json(os.path.join(HERE, "..", "assets", "capture.json"), {}) or {},
    )
    base = (args.slug or (intake.get("client") or {}).get("name") or "quote").lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", base).strip("-") + "-quote-only"
    path = os.path.join(args.dir, f"{slug}.capture.json")
    request = open(os.path.join(args.dir, "request.md"), encoding="utf-8").read()
    data = {
        "capture_version": 3,
        "slug": slug,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "user": cfg.get("user"),
        "client": (intake.get("client") or {}).get("name"),
        "deliverable": "quote-only",
        "request": request,
        "raw_quote": slim,
        "intake": {k: v for k, v in intake.items() if k != "log"},
        "log": intake.get("log", []),
        "feedback": {
            "worked": args.worked,
            "change": args.change,
            "answered": bool(args.worked or args.change),
        },
    }
    dump_json(path, data)
    print(
        json.dumps(
            {
                "path": path,
                "title": os.path.basename(path),
                "bytes": os.path.getsize(path),
                "drive_folder_id": asset.get("drive_folder_id"),
                "user": cfg.get("user"),
            },
            indent=2,
        )
    )


def clear_cache():
    cfg = load_json(CONFIG, {}) or {}
    removed = {k: len(cfg.get(k) or {}) for k in ("known_clients", "known_passengers")}
    cfg.pop("known_clients", None)
    cfg.pop("known_passengers", None)
    save_config(cfg)
    print(json.dumps({"cleared": removed, "preserved": sorted(cfg.keys())}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="cmd", required=True)
    summary = commands.add_parser("summarize")
    summary.add_argument("raw")
    summary.add_argument("--select")
    write = commands.add_parser("write")
    for flag in ("client", "request", "raw", "source-request"):
        write.add_argument(f"--{flag}", required=True)
    write.add_argument("--dir", default="handoff")
    write.add_argument("--profile-id", type=int, required=True)
    write.add_argument("--mode", default="best")
    write.add_argument("--tool", required=True, choices=sorted(EXACT_TOOLS))
    write.add_argument("--selected")
    for flag in ("unit", "ambiguity", "placeholder", "client-question"):
        write.add_argument(f"--{flag}", action="append", default=[])
    write.add_argument("--rate-sheet-shown", action="store_true")
    write.add_argument("--final", action="store_true")
    write.add_argument(
        "--client-source",
        default="resolve",
        choices=("resolve", "user", "ambiguous", "preselection"),
    )
    client = commands.add_parser("client")
    client.add_argument("name")
    commands.add_parser("clear-cache")
    discount = commands.add_parser("prepare-discount")
    discount.add_argument("--dir", default="handoff")
    discount.add_argument("--percent", type=float, required=True)
    discount.add_argument("--label", default="Temporary client presentation discount")
    discount.add_argument("--out", required=True)
    replace = commands.add_parser("replace")
    replace.add_argument("--dir", default="handoff")
    replace.add_argument("--raw", required=True)
    replace.add_argument("--source-request", required=True)
    replace.add_argument(
        "--tool",
        required=True,
        choices=("calculate_quote_units", "calculate_temporary_quote_units"),
    )
    replace.add_argument("--selected")
    cap = commands.add_parser("capture")
    cap.add_argument("--dir", default="handoff")
    cap.add_argument("--slug")
    cap.add_argument("--worked")
    cap.add_argument("--change")
    args = parser.parse_args()
    if args.cmd == "summarize":
        print(summarize(load_json(args.raw, {}) or {}, args.select))
    elif args.cmd == "write":
        write_handoff(args)
    elif args.cmd == "client":
        for name, profile_id in (
            (load_json(CONFIG, {}) or {}).get("known_clients") or {}
        ).items():
            if name.lower() == args.name.lower():
                print(profile_id)
                return
        sys.exit(1)
    elif args.cmd == "clear-cache":
        clear_cache()
    elif args.cmd == "prepare-discount":
        prepare_discount(args)
    elif args.cmd == "replace":
        replace_result(args)
    else:
        capture(args)


if __name__ == "__main__":
    main()
