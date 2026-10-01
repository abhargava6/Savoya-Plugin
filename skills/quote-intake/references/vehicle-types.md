# Vehicle guidance (non-authoritative)

Vehicle IDs, names, availability, and passenger capacities must come from `preview_rates`, `preview_rate_batch`, or `resolve_vehicle_types` for the current Core environment. Never copy an ID or capacity from this file into a tool request.

Useful physical guidance only:

- Passenger count is not the same as comfortable luggage capacity. Airport groups with substantial luggage may need a larger class or an extra luggage vehicle.
- Sprinters, executive vans, minibuses, and motor coaches can differ materially by market and operator. Resolve the exact Core vehicle type before quoting.
- ADA access, child seats, oversized equipment, meet-and-greet service, and unusual staging are operational requirements. Record them explicitly and do not turn them into locally priced additions.
- When the user says “however many are needed,” omit request quantity and let Core size the fleet from `passenger_count` and current capacity data.
- When the user specifies an exact fleet count, pass it as requested and disclose any Core warning.
