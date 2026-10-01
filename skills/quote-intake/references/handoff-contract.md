# Quote-to-document handoff contract (version 3)

```text
handoff/
  request.md          original user request
  raw_quote.json      selected exact, complete, non-persisted MCP result
  source_request.json exact selected request, including signed stop references
  intake.json         provenance, workflow decisions, and document state
```

## Invariants

- `raw_quote.json` is never edited by the document pipeline.
- `source_request.json` has one Core-selected `vehicle_type_id` per unit; candidate lists are removed.
- `intake.json` records `contract: 3`, `source_tool`, selected option metadata, `persisted: false`, currency, aggregate total, warnings, and temporary-pricing provenance.
- Only exact and complete results may be normalized.
- One complete comparison option must be selected. Document generation never blends alternatives.
- Passenger information is absent unless the user named a passenger; `passenger_count` remains in every unit request.

## Document-stage temporary discount

`handoff.py prepare-discount` rebuilds `source_request.json` with the same whole-percentage temporary discount on every unit. The skill sends that request to the returned tool, then uses `handoff.py replace` to atomically replace the authoritative result and provenance.

If a discount is removed, the helper selects `calculate_quote_units` unless temporary rates still require `calculate_temporary_quote_units`. A partly temporary package is rejected instead of locally merging totals.

## Client cache

Only unique resolver results or explicit user selections are cached. `handoff.py clear-cache` removes client and legacy passenger caches and preserves all unrelated configuration.
