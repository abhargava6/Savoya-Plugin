# Vehicle types — dimensions, terminology, and candidate policy

**Core is the authority on vehicles.** `resolve_vehicle_types` returns `id`, `name`,
`capacity`, `classification`, `greeter`, `bus`, `limited_availability` and
`client_can_book`. Call it once per quote (node C) and read those from the response.

This file holds the two things Core has no concept of — **physical dimensions** and **our
candidate policy** — plus the names, so a human and the engine can talk about the same
vehicle.

> **Why this changed.** This used to be a static table used *instead of* calling Core, to
> save a per-quote tool call. That trade collapsed when the table turned out to be wrong
> rather than merely stale: it gave Exec Van a capacity of "~10" where Core says **14**,
> and it omitted seven types entirely — MPV, Premier European Touring, three armored
> classes, and both greeters. A saved call against a wrong answer is not a saving.

## Dimensions — the one thing only this file knows

| id | Type | Approx. length × width |
|---|---|---|
| 1 | Sedan | 16 × 6 ft |
| 143 | Premium Sedan | 17 × 6 ft |
| 8 | SUV | 17 × 6.5 ft |
| 11 | MPV | 18 × 6.5 ft |
| 25 | Executive Van | 20 × 7 ft |
| 26 | Mercedes Sprinter Van | 24 × 7 ft |
| 7 | Mini Bus | 35 × 8 ft |
| 6 | Coach Bus | 45 × 8.5 ft |

Dimensions are typical, **not contractual** — they exist to **rule vehicles out** when a
client states a physical constraint, never to promise a size. Confirm anything tight with
dispatch. **Capacity is deliberately not in this table**; read it from
`resolve_vehicle_types`.

Armored classes (Armored Sedan 15, Armored SUV 21, Armored MPV 199) and Premier European
Touring (198) have no dimensions recorded here. They are rare, and guessing a figure that
rules a vehicle in or out is worse than having none — ask dispatch.

## Greeters are vehicle types, not a document line

| id | Type |
|---|---|
| 12 | Hourly Greeter/Coordinator |
| 13 | Single Greet |

Both come back with `greeter: true` and `capacity: null`, so Core does not try to size a
fleet from them — don't pass the group headcount to a greeter unit.

They are **absent from `preview_rate_batch`** and are not listed in
`missing_vehicle_type_ids` either, so the rate sheet cannot tell you whether a greeter rate
exists in a market. The only way to find out is to price one.

A greeter unit is **pickup + an `as_directed` stop carrying a `duration` in hours**. A
`duration` on the dropoff is ignored and the unit collapses to the 2-hour minimum. Core
then adds a constant **+1.25 h** of positioning time, so a 4-hour greeter bills 5.25 hours
— show what Core billed, never back-solve the duration.

## Access and size constraints
When the request states one — a parking-pass size limit, a low clearance, a narrow
driveway, a loading-dock restriction, a venue that won't admit coaches — it is a **blocking
question**, because it changes which vehicles can be quoted at all:

> *"Your parking passes cap vehicles at 9 × 18 ft. That rules out our Mini Bus (35 ft) and
> Coach Bus (45 ft), and a Sprinter is about 24 ft. Quote SUVs, or check with the venue?"*

Never quote a vehicle the stated constraint excludes, and never silently ignore the
constraint — the client gave it for a reason, and a coach turned away at the gate is worse
than a higher price. Record the resolution as an ambiguity in the handoff.

## Candidate policy — ours, not Core's

What goes in `vehicle_type_ids` for "best" and "options". These ids are **our choice of
which classes to offer**, which is a policy decision; the capacity that decides how many
of them get quoted is Core's.

| Headcount | ids |
|---|---|
| 1–3 | [1, 8] |
| 4–6 | [8, 26] |
| 7–13 | [26, 8] |
| 14–41 | [7, 26] |
| 42+ | [6, 7] |

Core sets quantity from `passenger_count` when `quantity` is omitted, so a 120-pax unit
with `[7, 26]` prices as Mini Buses against Sprinters and takes the lower total. Verified
at 80 passengers: 2 Mini Bus / 14 SUV / 7 Sprinter, each `capacity_adjusted: true`, from a
single call.

**Eligibility is a field, not a memory.** `client_can_book: false` on Mini Bus and Coach
Bus is something we once learned by hand and now read. `limited_availability: true` shows
up on greeter types and is worth surfacing before a CSM promises one.

Headcount bands above are expressed against today's capacities. If a band and Core's
capacity ever disagree, **Core wins** — and the band is the thing to fix here.
