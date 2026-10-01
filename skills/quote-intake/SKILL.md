---
name: quote-intake
description: Turn a client ground-transportation request into an exact, non-persisted Savoya Core quote. Use for transfers, hourly service, multi-day or multi-city work, comparisons, selected packages, and temporary client-presentation pricing. Preserves the rate-sheet decision and writes contract-v3 handoffs for quote-document.
compatibility: Requires the Savoya MCP connector and Python 3.
---

# Savoya quote intake

Savoya MCP/Core is authoritative for vehicle metadata, capacity-based quantities, rates, discounts, and totals. This skill structures requests and explains results; it never prices locally.

Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/references/decision-tree.md` once at the start. Use full `${CLAUDE_PLUGIN_ROOT}` paths for every script/reference.

## Load the tools once

Search once for: `resolve_client`, `resolve_passengers`, `resolve_itinerary_stops`, `resolve_vehicle_types`, `preview_rates`, `preview_rate_batch`, `calculate_quote_units`, `calculate_temporary_quote_units`, and `generate_quote_options`.

Do not call removed tools. Passenger resolution is needed only when the user names a passenger; otherwise omit `passenger_id` and always send `passenger_count`.

## Parse and resolve

1. Save the user's request verbatim as `request.md`.
2. Build one quote unit per actual service block. Preserve the existing airport behavior: every airport stop receives a flight object; use `commercial_tbd: true`; a missing flight time may use the current documented placeholder and is disclosed as “flight details to be confirmed.”
3. Resolve client and all deduplicated stops. Use the client cache only for a previously unique or user-selected profile.
4. Resolve a passenger only if the user named one. Never select or cache a passenger merely to make quoting work.
5. Use `resolve_vehicle_types` or rate-preview results for IDs, names, and capacities. Never use a static catalog as authority.

## Questions

Use the host's picker for enumerable choices, one question per message, and wait for each answer.

1. Resolve genuine ambiguities that change pricing.
2. Every quote: “Rate sheet first, or straight to the quote?”
3. Every quote: “Best value, a few options side by side, or you name the vehicles?”
4. After results: which complete package should be selected?
5. After confirmation: PDF, email copy, or nothing yet?

The rate-sheet question is intentional UX. If visible, use `display: "show"`. If a preview is needed only to discover current vehicle/rate metadata, use `display: "internal"`.

## Quote routing

- User-selected vehicle package → `calculate_quote_units`.
- Complete value/elevated comparison → `generate_quote_options`.
- Any user-supplied temporary rate or temporary discount → `calculate_temporary_quote_units`.

Every request carries `passenger_count`. Omit `quantity` when Core should size the fleet. Never multiply vehicles or totals locally.

For temporary pricing, every unit must be eligible for the temporary tool. Do not combine a partly temporary package with locally calculated totals. Explain the unsupported combination and ask the user to choose a complete package.

## Present and select

Save the MCP response; do not inspect or recalculate it manually. Summarize it with:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py summarize raw_quote.json --select <option-key>
```

The user must choose one complete Core-generated option before document generation. Do not mix legs from separate comparison options in the document layer.

## Contract-v3 handoff

Keep the exact request sent to the selected pricing tool, including signed stop refs, as `source-request.json`, then write:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py write \
  --dir handoff --client "<client>" --profile-id <id> \
  --request request.md --raw raw_quote.json --source-request source-request.json \
  --tool <source-tool> --mode <mode> [--selected <option-key>] \
  [--rate-sheet-shown] --client-source <resolve|user> --final
```

The writer rejects approximate, incomplete, persisted, or unselected comparison results. It creates:

- `raw_quote.json`: the selected authoritative Core result;
- `source_request.json`: the selected one-vehicle-per-unit request used for re-quotes;
- `intake.json`: provenance and workflow state, contract version 3.

If the user declines a document, preserve the existing capture workflow:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py capture --dir handoff
```

Developer-only cache reset when switching environments:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py clear-cache
```

This removes client and legacy passenger cache entries while preserving unrelated user configuration.

## Boundaries

- Keep physical/logistical vehicle guidance, but treat Core as the source for IDs and capacities.
- Unsupported fuel changes or priced greeter additions are notes or clear unsupported messages, never local money changes.
- Historical feedback may name removed tools; it is not routing guidance.
