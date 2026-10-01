# Rules

## Money

- Core/MCP is authoritative for vehicle metadata, quantity, rates, discounts, subtotals, line totals, and aggregate total.
- Copy values by field presence; zero is a valid value.
- Never reconstruct discounts, surcharges, subtotals, option totals, or package totals.
- Do not require line totals to sum to the aggregate total. Compare every copied field directly with `raw_quote.json`.
- Document-stage discounts are whole percentages re-quoted through MCP and applied to every selected unit.
- Temporary pricing is non-persisted quote presentation only. Reject partly temporary packages rather than merging money locally.
- Fuel overrides, waivers, and priced greeter additions are unsupported in this workflow. Existing Core facts remain visible; requested changes become non-priced notes or a clear unsupported message.

## Flow

- Only exact, complete, `persisted: false` handoff contract-v3 results enter document generation.
- Require one complete selected option. Never blend comparison alternatives into a synthetic document total.
- Preserve the forced rate-sheet decision. Use `display: "show"` for a requested preview and `display: "internal"` for metadata-only discovery.
- Omit `passenger_id` unless the user names a passenger. Always preserve `passenger_count`.
- Vehicle IDs and capacities come from Core previews/resolvers, never a static plugin catalog.

## Client output

- Never expose rate IDs, profile/passenger IDs, basis points, inventory counts, tool names, or persistence internals.
- Always show effective pricing basis, quantity, vehicle, capacity, cancellation, special-event facts, relevant warnings, and the Core total.
- Show a subtotal only when Core returned one. A percentage may be shown without inventing a dollar amount.
- Preserve valid zero values and the existing airport/flight-time behavior.
- Never ship an unlabeled stop or an internal unresolved question.

## Delivery

- Verify against `raw_quote.json` before delivery.
- Preserve layout, map, pagination, capture, and `client_notes` guards.
- No mail sending: provide copy-ready text and files in the conversation.
- Capture once after the final deliverable/feedback using the existing workflow.
