#!/usr/bin/env python3
"""The ONE reader of a Savoya quote tool result. Every script that reads a pricing
response reads it through here, in both skills.

The MCP returns a successful quote as `{ "presentation": {...} }` and nothing else: the
compact quote view, presentation version 2 (savoya-quote-mcp
`src/domains/quotes/presentationContracts.ts`). The MCP has already read Core's raw
payload, so airports, service areas, coordinates and drive times arrive in one shape.
Any other presentation version is REFUSED, loudly: a newer one says to update the plugin, an
older one says the connector is behind. Reading on would be guessing.

    packages(raw) -> [{key, label, strategy, total_cents, units, estimate_type,
                       currency, persisted, warnings, unpriced}]

`key` is None for a single quote_result package and the option key for each scenario
of a comparison. `units` are the view's quote units, with the warnings the MCP stated once
in `warnings_on_every_unit` given back to every unit. A warning only some units carry
stays on those units: it describes them alone ("No local providers in Syracuse" on one
leg must never reach the others).

Money is passed through, never computed: totals, line totals, per-vehicle amounts, rates
and adjustments are the view's.
"""
import copy
import re

PRESENTATION_VERSION = 2


class QuoteViewError(ValueError):
    """The response cannot be read: an unknown presentation version, or not a quote."""


def version(raw):
    """The presentation version, which must be 2. Raises QuoteViewError otherwise."""
    if not isinstance(raw, dict):
        raise QuoteViewError("The quote response is not a JSON object.")
    presentation = raw.get("presentation")
    if not isinstance(presentation, dict):
        if "quote_units" in raw or "aggregate_total" in raw:
            # The raw Core payload the connector sent before the compact view existed.
            raise QuoteViewError(
                "This quote came back as the old raw payload, not the compact quote view this build "
                f"of the savoya-quoting plugin reads (presentation version {PRESENTATION_VERSION}). The Savoya quoting "
                "connector is older than this plugin. Do not use this result; tell Savoya engineering "
                "the connector needs to serve the compact quote view, then run the quote again.")
        raise QuoteViewError("The response carries no presentation, so it is not a Savoya quote result. "
                             "Paste the whole tool result, unedited.")
    found = presentation.get("version")
    if isinstance(found, int) and found > PRESENTATION_VERSION:
        # The MCP is newer than this plugin: the fix is on the user's side.
        raise QuoteViewError(
            f"This quote came back in MCP presentation version {found}, which this build of the "
            f"savoya-quoting plugin cannot read (it reads version {PRESENTATION_VERSION}). Update the "
            "savoya-quoting plugin, start a new chat, and run the quote again.")
    if found != PRESENTATION_VERSION:
        # The MCP is older than this plugin (or sent no version): updating the plugin cannot help.
        raise QuoteViewError(
            f"This quote came back in MCP presentation version {found}, but this build of the "
            f"savoya-quoting plugin reads version {PRESENTATION_VERSION} only. The Savoya quoting "
            "connector is older than this plugin. Do not use this result; tell Savoya engineering "
            "the connector needs to serve the compact quote view, then run the quote again.")
    return found


def view(raw):
    """The presentation view name (quote_result, scenario_comparison, blocked, ...)."""
    version(raw)
    return raw["presentation"].get("view")


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


def packages(raw):
    """[{key, label, strategy, total_cents, units, ...}] for a quote or scenario result.
    Raises QuoteViewError for an unsupported version or a response that is not a quote."""
    version(raw)
    presentation = raw["presentation"]
    data = presentation.get("data") or {}
    name = presentation.get("view")
    common = {"estimate_type": presentation.get("estimate_type"),
              "currency": presentation.get("currency_code") or "USD"}
    if name == "scenario_comparison":
        return [dict(common, key=s.get("key"), label=s.get("label") or s.get("key"), strategy=s.get("strategy"),
                     total_cents=s.get("total_amount"), persisted=s.get("persisted"),
                     warnings=list(s.get("warnings") or []), unpriced=[],
                     units=with_shared_warnings(s.get("quote_units"), s.get("warnings_on_every_unit")))
                for s in data.get("scenarios") or []]
    if name == "quote_result":
        return [dict(common, key=None, label=None, strategy=None, total_cents=data.get("total_amount"),
                     persisted=data.get("persisted"),
                     warnings=[w.get("message") if isinstance(w, dict) else w for w in presentation.get("warnings") or []],
                     unpriced=list(data.get("unquoteable_unit_keys") or []),
                     units=with_shared_warnings(data.get("quote_units"), data.get("warnings_on_every_unit")))]
    raise QuoteViewError(f"This is a {name!r} response, not a priced quote.")


def is_options(raw):
    """A comparison of several complete packages (generate_quote_options)."""
    return view(raw) == "scenario_comparison"


def to_v2(pkg):
    """One package as a quote_result response: the shape handoff.py writes for a saved
    option or a merged package, so everything after ingest reads one shape. Units keep
    every warning they carry (the shared ones were already given back), so
    `warnings_on_every_unit` is empty and nothing is lost."""
    return {"presentation": {
        "version": PRESENTATION_VERSION, "view": "quote_result", "status": "ready",
        "estimate_type": pkg.get("estimate_type") or "exact", "title": "Exact quote",
        "currency_code": pkg.get("currency") or "USD", "amount_unit": "cents",
        "warnings": [{"severity": "warning", "message": w} for w in pkg.get("warnings") or []],
        "data": {"total_amount": pkg.get("total_cents"), "quote_units": copy.deepcopy(pkg.get("units") or []),
                 "unquoteable_unit_keys": list(pkg.get("unpriced") or []), "warnings_on_every_unit": [],
                 "persisted": False if pkg.get("persisted") is None else pkg["persisted"],
                 "pricing": {"adjustments": {"temporary_rate_used": False}}},
    }}


STOP_PLACEHOLDER = re.compile(r"Stop \d+")


def stop_names(unit):
    """Every name a stop is known by in a view unit: the label and the address."""
    return [n for s in unit.get("stops") or [] for n in (s.get("label"), s.get("address")) if n]
