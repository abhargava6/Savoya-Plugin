# Blocking vs non-blocking clarifications

A client request usually carries two very different kinds of open question. Routing them wrongly is how a quote ends up built on a guess, or how an internal question leaks into a client's PDF.

## Blocking — resolve with the internal user during intake, before quoting

Anything that would **change the quote itself**:

| Gap | Ask |
|---|---|
| Date with no year, or an ambiguous date ("Jun 9" with no year, "next Thursday") | which year / which date |
| Headcount given as a range or a guess ("50–75", "about 80") | which number to size the fleet on |
| Location that resolves to several genuinely different places, or is too vague to resolve ("downtown", "the Marriott") | which one |
| Service shape the request doesn't settle (one vehicle all day vs. two for half a day, when the client didn't say) | which to quote, or quote both as scenarios |
| A **physical or access constraint** on vehicles (parking-pass dimensions, low clearance, narrow driveway, no coaches at the venue) | which vehicles it leaves available — see `vehicle-types.md`. Never quote a vehicle the constraint excludes |
| A client time whose **kind** the wording does not settle (flight departure, pickup, or airport arrival target) | which it is. A departure becomes a pickup after the 2h/3h lead time and Core's drive time (time reading, R18/R34). It changes billable hours, so it changes the price |

**Never** paper over these with a placeholder and **never** push them into the document as a client-facing "please confirm". The internal user is in the chat and can answer in one tap; the client is not.

The one true exception stays: a **flight time** for an airport leg. It doesn't change the price, the reservation is built before flights are booked, and "flight details to be confirmed" is a normal client-facing line. Keep the placeholder, record it, disclose it.

## Non-blocking — carry through, answer in the document

The client's own questions that **don't change the pricing math**. They never block intake or quoting. Record them with `--client-question` so the document stage can answer them.

| The client asks | Handled by |
|---|---|
| "Is tax included?" / "Is gratuity included?" | the standard terms block already answers it — no extra work |
| "What's your cancellation policy?" | the terms block plus the per-leg cancellation column — no extra work |
| "Can you provide on-site staff / a greeter?" | **Price it through Core — never ask a human for a number Core has.** Greeters are vehicle types (12 Hourly Greeter/Coordinator, 13 Single Greet). Always check the rate first by attempting to price it; where it is then handled depends on who raised it — see the greeter node in `decision-tree.md`. The client asked here, so if a rate exists it belongs in **intake**, as a quote unit. Only a market with no greeter rate falls back to asking the user for a cost. A hand-entered figure on an Irvine quote was **$940** against Core's **$404.20**. |
| Signage, PA system, luggage vehicle, waiting area, lobby staff, an electric vehicle: anything Core cannot answer | the **document stage asks the user** how to respond (included, not included, extra cost, confirm, or their own words) and prints the answer beside the request (R72/R73). Record the request here with `--client-question`; never answer it at intake |

## Data-answered — the quote already contains the answer; say it out loud

The third kind, and the easiest to miss. The client asks something the **quote data itself answers**, so nothing is blocked and no boilerplate covers it — but the answer sits implicit in the line items and the client has to dig it out.

| The client asks | Where the answer already is | What the document must do |
|---|---|---|
| "Can you suggest pick-up times?" | each leg's `pickup_date` | a **Suggested pickup times** callout: per date, per pickup area, the time |
| "How long is the drive?" / "When will we arrive?" | `route.drive_min`, each stop's `drive_minutes` | state drive time per leg where it matters, not only in the route table |
| "How many vehicles?" | `vehicle.quantity` per leg | say it in the intro note when it's the client's actual question |
| "How long will we have the vehicle?" | `billable_hours`, `minimum_hours` | state the block per leg in plain words |

**Rule:** if the client asked it and the answer is in the data, it gets an explicit callout in **both** the PDF (top of the first quote page, usually via `personalization.intro_note`) and the email — near the top, before the line-item breakdown. Never make a client reconstruct an answer from sixteen timestamps.

Record these with `--client-question` like the others; the document stage decides where the callout goes.

The split in one line: **blocking questions are ours to ask; boilerplate ones are already answered; data-answered ones we must surface.**
