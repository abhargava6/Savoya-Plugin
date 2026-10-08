#!/usr/bin/env python3
"""Render Core's `presentation` block as the CSM-facing view.

  render_presentation.py <raw.json>

Every MCP response now carries a `presentation` block: a `view`, a `title`,
severity-tagged `warnings`, pre-formatted rows, and `actions` carrying intents. Core is
proposing the UI. We render it rather than composing our own table, for two reasons:

  1. Consistency. A table the model writes fresh each session varies between sessions;
     Core's rows are the same for every CSM looking at the same quote.
  2. It is the money rule in another costume. Restating Core's numbers in our own words is
     a transcription step, and transcription is where our numbers have drifted from Core's
     before. Printing what Core sent removes the step.

THREE BOUNDARIES, or this gets over-applied:

  * INTERNAL ONLY. This output carries rate ids, rack-versus-effective rates and
    `limited_availability`. None of it goes in front of a client. `quote.json` and the
    whole document layer stay ours.
  * NO PARAPHRASE. Labels and messages are printed as Core wrote them. A model rewording
    this block is the drift we are removing, wearing a different hat.
  * MISSING OR CONTRADICTORY. No presentation block → exit 3, and the caller falls back to
    `handoff.py summarize`. Presentation totals disagreeing with the quote units → print
    BOTH and say so. Core contradicting itself is worth seeing, not worth hiding behind a
    choice we made silently.

On view coverage: the `quote_result` and `blocked` shapes were read off real responses and
are rendered field by field. `scenario_comparison` and `rate_preview` were observed but not
captured in full, so they render from the structure that is actually present rather than
from field names we would be guessing at. An unrecognised view renders generically too —
printing what is there beats inventing a layout for it.

Exit codes: 0 rendered · 3 no presentation block (fall back) · 4 malformed block.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handoff import SUPPRESSED_WARNING  # noqa: E402  — one source, not a third copy


def money(cents, currency="USD"):
    if cents is None:
        return "—"
    sym = "$" if currency in (None, "USD") else ""
    return f"{sym}{cents / 100:,.2f}"


def pct(bps):
    return None if not bps else f"{bps / 100:g}%"


def hours(h):
    if h is None:
        return None
    return f"{h:g} hr" if h == 1 else f"{h:g} hrs"


def _warn_lines(warnings, seen, priced=True):
    """Severity-tagged warnings, as Core wrote them, said once each.

    Core repeats the same warning on the unit, on every option and on the aggregate, so
    `seen` is shared across the whole render — not per call, which is how this printed the
    passenger note twice on its first run.

    One suppression, imported from handoff.py so the two skills cannot disagree: Core's
    "no passenger was selected" note, and only when the unit priced. Everything else
    surfaces, including a warning we don't recognise."""
    out = []
    for w in warnings or []:
        msg = w.get("message") if isinstance(w, dict) else str(w)
        if not msg or msg in seen:
            continue
        if SUPPRESSED_WARNING in msg and priced:
            continue
        seen.add(msg)
        sev = (w.get("severity") if isinstance(w, dict) else None) or "warning"
        icon = {"error": "✗", "warning": "⚠"}.get(sev, "ℹ")
        out.append(f"- {icon} {msg}")
    return out


def _hours_note(u, raw_unit):
    """Say out loud when Core billed more hours than the user asked for.

    Core adds positioning time: an as-directed stop sent `duration: 2` billed 3.25 hours
    and `duration: 4` billed 5.25 — a constant +1.25h. A CSM who typed "4 hours" and reads
    a 5.25-hour line will call it a bug unless the difference is named. We print both and
    explain; we never back-solve the duration, which would be exactly the local arithmetic
    this release removes."""
    if not raw_unit:
        return []
    billable = ((u.get("pricing") or {}).get("billable_hours"))
    if billable is None:
        return []
    requested = sum(s.get("duration") or 0 for s in (raw_unit.get("stops") or []))
    if not requested or abs(billable - requested) < 0.01:
        return []
    extra = round(billable - requested, 2)
    return [f"ℹ Billed {hours(billable)} against {hours(requested)} requested "
            f"(+{extra:g}) — Core adds positioning time. The client sees the billed figure."]


def _pricing_bits(pr):
    """One compact line of the pricing facts Core returned. Values, not arithmetic."""
    if not pr:
        return None
    bits = []
    eff = pr.get("effective_rate_amount") or pr.get("rate_amount")
    unit = pr.get("billing_unit")
    if eff:
        bits.append(f"{money(eff)}/{unit}" if unit else money(eff))
    base = pr.get("base_rate_amount")
    if base and eff and base != eff:
        bits.append(f"rack {money(base)}")
    bh = hours(pr.get("billable_hours"))
    if bh:
        bits.append(f"{bh} billable")
    mh = pr.get("minimum_hours")
    if mh:
        bits.append(f"{hours(mh)} min")
    adj = pr.get("adjustments") or {}
    saved = adj.get("discount_basis_points")
    eff_d = adj.get("effective_discount_basis_points")
    temp_d = adj.get("temporary_discount_basis_points")
    if eff_d and eff_d != saved:
        # Show what the CLIENT is actually getting, and where it came from. Printing only
        # the contracted 30% while a temporary 10% is also applied understates the discount
        # on screen by a third — and discounts are additive in basis points, not compounded.
        label = adj.get("temporary_discount_label") or "temporary"
        bits.append(f"{pct(eff_d)} discount ({pct(saved)} contracted + {pct(temp_d)} {label})")
    elif saved:
        bits.append(f"{pct(saved)} discount")
    f = pct(adj.get("fuel_surcharge_basis_points"))
    if f:
        bits.append(f"{f} fuel")
    sh = pct(adj.get("special_handling_basis_points"))
    if sh:
        bits.append(f"{sh} special handling")
    if adj.get("temporary_rate_used"):
        bits.append("**temporary rate — not saved**")
    cx = pr.get("cancellation_hours")
    if cx is not None:
        bits.append(f"{cx}-hr cancel")
    return " · ".join(bits) if bits else None


def _unit_block(u, currency, seen, raw_unit=None):
    out = [f"**{u.get('label') or u.get('key')}** — {money(u.get('total_amount'), currency)}"]
    facts = []
    if u.get("vehicle_name"):
        q = u.get("quantity")
        facts.append(f"{q}× {u['vehicle_name']}" if q and q > 1 else u["vehicle_name"])
    if u.get("passenger_count"):
        facts.append(f"{u['passenger_count']} pax")
    if u.get("pickup_date"):
        facts.append(u["pickup_date"])
    if facts:
        out.append("  " + " · ".join(facts))
    pb = _pricing_bits(u.get("pricing"))
    if pb:
        out.append(f"  {pb}")
    rps = (raw_unit or {}).get("pricing_summary") or {}
    sub = rps.get("subtotal_amount")
    if sub and sub != u.get("total_amount"):
        off = sub - (u.get("total_amount") or 0)
        out.append(f"  {money(sub, currency)} before the additional discount "
                   f"− {money(off, currency)} = {money(u.get('total_amount'), currency)}")
    for s in u.get("stops") or []:
        label = s.get("label") or s.get("address") or "(stop)"
        dm = s.get("drive_minutes")
        ft = s.get("flight_time")
        extra = []
        if dm:
            extra.append(f"{dm} min drive")
        if ft:
            extra.append(f"flight {ft}")
        out.append(f"  {s.get('order', '•')}. {label}"
                   + (f" — {' · '.join(extra)}" if extra else ""))
    out += ["  " + ln for ln in _warn_lines(u.get("warnings"), seen)]
    out += ["  " + ln for ln in _hours_note(u, raw_unit)]
    return out


def _generic(data, depth=0):
    """Print a structure we don't have a captured shape for, without inventing one."""
    pad = "  " * depth
    out = []
    for k, v in (data or {}).items():
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            key = k.replace("_", " ")
            out.append(f"{pad}- {key}: "
                       + (money(v) if k.endswith("_amount") else str(v)))
        elif isinstance(v, bool):
            out.append(f"{pad}- {k.replace('_', ' ')}: {'yes' if v else 'no'}")
        elif isinstance(v, list) and v:
            out.append(f"{pad}- {k.replace('_', ' ')} ({len(v)}):")
            for item in v:
                if isinstance(item, dict):
                    out += _generic(item, depth + 2)
                    out.append("")
                else:
                    out.append(f"{pad}    - {item}")
        elif isinstance(v, dict) and v:
            out.append(f"{pad}- {k.replace('_', ' ')}:")
            out += _generic(v, depth + 1)
    return out


def cross_check(raw, pres):
    """Does Core's own presentation total match its own quote units?

    If it doesn't, that is Core disagreeing with itself. Say so and show both. Picking one
    silently would make our output look authoritative about a number we can't vouch for."""
    shown = ((pres.get("data") or {}).get("total_amount"))
    actual = raw.get("aggregate_total")
    if actual is None:
        actual = (raw.get("pricing_summary") or {}).get("total_amount")
    if shown is None or actual is None or shown == actual:
        return []
    return [
        "",
        "> **Core's presentation total and its quote units disagree.** "
        f"Presentation says {money(shown)}; the quote units add to {money(actual)}. "
        "Neither has been preferred here. Re-run the quote, and if it persists this is a "
        "Savoya-side report, not a plugin one.",
    ]


def render(raw):
    pres = raw.get("presentation")
    if not isinstance(pres, dict) or not pres:
        return None, 3
    view = pres.get("view") or "unknown"
    data = pres.get("data") or {}
    currency = pres.get("currency_code") or raw.get("currency") or "USD"

    seen = set()   # one warning, said once per render — not once per unit per option
    lines = [f"### {pres.get('title') or view.replace('_', ' ').title()}"]
    est = pres.get("estimate_type")
    status = pres.get("status")
    tag = " · ".join(x for x in (est, status) if x)
    if tag:
        lines.append(f"_{tag}_")
    lines.append("")

    if view == "blocked":
        ce = raw.get("client_error") or {}
        msg = ce.get("user_message") or raw.get("message") or "This could not be priced."
        lines.append(f"**{msg}**")
        seen.add(msg)   # the headline IS the warning; don't repeat it below
        for issue in (data.get("issues") or []):
            if isinstance(issue, str):
                lines.append(f"- {issue}")
        rec = (ce.get("recovery") or {}).get("message")
        if rec:
            lines += ["", rec]
        if ce.get("code") or raw.get("error_type"):
            lines += ["", f"_Core: {ce.get('code') or raw.get('error_type')}_"]
        return "\n".join(lines + _warn_lines(pres.get("warnings"), seen)), 0

    if view == "quote_result":
        total = data.get("total_amount")
        if total is not None:
            lines += [f"**Total {money(total, currency)}**", ""]
        raw_by_key = {ru.get("key"): ru for ru in (raw.get("quote_units") or [])}
        for u in data.get("quote_units") or []:
            lines += _unit_block(u, currency, seen, raw_by_key.get(u.get("key"))) + [""]
        bad = data.get("unquoteable_unit_keys") or []
        if bad:
            lines.append(f"✗ Could not be priced: {', '.join(bad)}")

    elif view == "scenario_comparison":
        for sc in data.get("scenarios") or []:
            tot = sc.get("total_amount")
            head = sc.get("label") or sc.get("key") or ""
            lines.append(f"**{head}** — {money(tot, currency)}" if tot else f"**{head}**")
            strat = sc.get("strategy")
            if strat:
                # A label, not a lever: proven to change nothing in Core's maths, so it
                # describes what the option IS and never explains why it costs what it does.
                lines.append(f"  _labelled {strat}_")
            for u in sc.get("quote_units") or []:
                lines += ["  " + ln for ln in _unit_block(u, currency, seen)]
            lines.append("")
        if not data.get("scenarios"):
            lines += _generic(data)

    elif view == "rate_preview":
        # `data.groups[]`, one per route/date, each with `rows` per vehicle type. This was
        # written from a guess first (scenarios/service_areas/rows) and corrected against a
        # real capture — the shape is groups, and the guess rendered a generic dump.
        for g in data.get("groups") or []:
            head = g.get("label") or g.get("key") or ""
            when = (g.get("date") or {}).get("value") if isinstance(g.get("date"), dict) else g.get("date")
            area = g.get("service_area")
            lines.append(f"**{head}**" + (f" · {when}" if when else "") + (f" · {area}" if area else ""))
            for r in g.get("rows") or []:
                name = r.get("vehicle_name") or r.get("vehicle_type_id")
                cap = r.get("vehicle_capacity")
                head2 = f"  {name}" + (f" ({cap} pax)" if cap else "")
                h, x = r.get("hourly") or {}, r.get("transfer") or {}
                parts = []
                if h.get("availability") == "available":
                    bit = money(h.get("amount")) + "/hr"
                    if h.get("minimum_hours"):
                        bit += f" · {hours(h['minimum_hours'])} min"
                    if h.get("cancellation_hours") is not None:
                        bit += f" · {h['cancellation_hours']}-hr cancel"
                    parts.append(bit)
                if x.get("availability") == "available":
                    parts.append(money(x.get("amount")) + "/trip")
                if not parts:
                    # Say WHY, in Core's own words. "unavailable" alone sends a CSM hunting.
                    why = ", ".join(r.get("reason_codes") or []) or "no rate"
                    parts.append(f"✗ {why.replace('_', ' ')}")
                mv = r.get("market_vehicle_count")
                tail = f"  ({mv} in market)" if mv else ""
                flags = []
                if r.get("limited_availability"):
                    flags.append("limited availability")
                if r.get("client_can_book") is False:
                    flags.append("not client-bookable")
                lines.append(f"{head2}: {' · '.join(parts)}{tail}"
                             + (f" — {', '.join(flags)}" if flags else ""))
            if g.get("missing_vehicle_type_ids"):
                lines.append(f"  _not evaluated: {g['missing_vehicle_type_ids']}_")
            lines.append("")
        if not data.get("groups"):
            lines += _generic(data)

    else:
        lines.append(f"_No captured layout for view `{view}` — printing what Core sent._")
        lines.append("")
        lines += _generic(data)

    lines += _warn_lines(pres.get("warnings"), seen)

    # One line per distinct intent. A comparison returns select_scenario once per option,
    # which printed as "select_scenario, select_scenario" before this.
    acts, seen_acts = [], set()
    for a in pres.get("actions") or []:
        name = a.get("intent") or a.get("id")
        if name and name not in seen_acts:
            seen_acts.add(name)
            acts.append(name)
    if acts:
        # Read, recorded, bound to nothing. These look like the intended way to drive the
        # refine loop, but they are undocumented beyond their names and our loop is
        # tested. When that changes, this is the seam.
        lines += ["", f"_Core offers: {', '.join(acts)}._"]

    lines += cross_check(raw, pres)
    return "\n".join(lines).rstrip() + "\n", 0


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        sys.exit(2)
    try:
        with open(sys.argv[1]) as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read {sys.argv[1]}: {e}", file=sys.stderr)
        sys.exit(4)
    out, code = render(raw)
    if code == 3:
        print("no presentation block in this response — fall back to handoff.py summarize",
              file=sys.stderr)
        sys.exit(3)
    print(out)
    sys.exit(code)


if __name__ == "__main__":
    main()
