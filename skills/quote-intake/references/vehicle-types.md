# Vehicle types — static table (no tool call needed)

| id | Type | Capacity | Approx. length × width | Default for headcount |
|---|---|---|---|---|
| 1 | Sedan | 3 | 16 × 6 ft | 1–3 |
| 143 | Premium Sedan | 3 | 17 × 6 ft | on request |
| 8 | SUV | 6 | 17 × 6.5 ft | 4–6 |
| 26 | Mercedes Sprinter Van | 13 | 24 × 7 ft | 7–13 |
| 25 | Executive Van | ~10 | 20 × 7 ft | on request (often unrated) |
| 7 | Mini Bus | 41 | 35 × 8 ft | 14–41 |
| 6 | Coach Bus | 50–55 | 45 × 8.5 ft | 42+ |

Dimensions are typical, not contractual — they exist to **rule vehicles out** when a client states a physical constraint, never to promise a size. Confirm anything tight with dispatch.

## Access and size constraints
When the request states one — a parking-pass size limit, a low clearance, a narrow driveway, a loading-dock restriction, a venue that won't admit coaches — it is a **blocking question**, because it changes which vehicles can be quoted at all:
> *"Your parking passes cap vehicles at 9 × 18 ft. That rules out our Mini Bus (35 ft) and Coach Bus (45 ft), and a Sprinter is about 24 ft. Quote SUVs, or check with the venue?"*

Never quote a vehicle the stated constraint excludes, and never silently ignore the constraint — the client gave it for a reason and a coach turned away at the gate is worse than a higher price. Record the resolution as an ambiguity in the handoff.

**Candidate sets by headcount** (what goes in `vehicle_type_ids` for "best" and "options"):
| Headcount | ids |
|---|---|
| 1–3 | [1, 8] |
| 4–6 | [8, 26] |
| 7–13 | [26, 8] |
| 14–41 | [7, 26] |
| 42+ | [6, 7] |

The engine sets quantity from `passenger_count` when `quantity` is omitted, so a 120-pax unit with [7, 26] prices as 3 Mini Buses vs 10 Sprinters and picks the lower for `value_option`.

Call `resolve_vehicle_types` **only** when the user names a type not in this table (MPV, electric, greeter, a class in an international market). Add the result to this table when it recurs.
