# Handoff contract — intake → document

Intake writes a `handoff/` folder in the working directory. The document skill reads it and asks nothing about the quote. Both skills treat it as the single source of truth for a conversation.

```
handoff/
  request.md        the client's message, verbatim (becomes the eval prompt later)
  raw_quote.json    the engine result as the MCP returned it (latest re-quote) — from
                    generate_quote_options, calculate_quote_units, or
                    calculate_temporary_quote_units: the MCP's compact view (presentation
                    version 2). A merged package or a saved option is written in that shape
  intake.json       everything intake decided + everything the document flow decides
  blocked.json      present only while a write is refused (R92): the gate, the reason and the fix.
                    The document step stops while it exists; a successful write removes it
```

## intake.json
```jsonc
{
  "contract": 3,
  "written_by": "handoff.py write",   // only the checked step writes this file; never build it by hand
  "client":        {"name": "Yerdle", "profile_id": 201890, "source": "cache|resolve|user"},
  "units": [        // one per quote unit sent to the engine, in order
    {"key": "offsite_9_16", "date": "2026-09-16T17:45:00-04:00", "passenger_count": 120,
     "structure": "out-and-back-block|transfer|hourly-block|as-directed",
     "rationale": "Out-and-back with 2.25h wait → one hourly unit, not two transfers",
     "alternative_of": null,
     "vehicle_type_ids": [7, 26], "quantity": null, "duration_hours": 6}
  ],
  "quote_mode": "best|options|defined",       // node E answer
  "rate_sheet_shown": false,
  "ambiguities": [{"stop": "Classic Harbor Line", "resolution": "took first of 2 same-place candidates"}],
  "placeholders": ["departure flight time 14:30 assumed (TBD)"],
  "final": true,                               // user said the quote is final (node I)
  "selection": {"select": ["offsite_9_16"], "alternatives": {"jun9_s2": "jun9_s1"}},
  "decisions": {                               // filled by the DOCUMENT flow, one key per question
    "discount_pct": 0,
    "greeter_cost": null,                      // only asked when a client question mentions a greeter
    "commission_pct": 5,                       // or absent/none — stated on the document, changes no number
    "format": "pdf|email+pdf|html|docx|xlsx",    // asked before cover and map (R110)
    "cover": "event-planners|custom|<uploaded-path>",
    "personalization": {"event_name": "...", "intro_note": "...", "contact": true, "client_logo_url": null, "leg_notes": {}, "closing_note": null},
    "map": false
  },
  "log": [{"ts": "...", "step": "E", "note": "user chose options"}]
}
```

## Rules
- Intake writes `client`, `units`, `quote_mode`, `rate_sheet_shown`, `ambiguities`, `placeholders`, `final`, `selection`. It never writes `decisions`. `time_readings` (optional, additive; no contract bump): per airport unit `{unit, kind, client_time, pickup, airport_target?, lead_hours?, drive_minutes?, computed_pickup?, priced_pickup?, arrival?, window_min?}` (`pickup` is the time priced; R105 accepts an arrival 0 to `window_min` minutes before `airport_target`); the document prints the pickup and the airport arrival target (R34). Also optional and additive: `overlap_decisions` (R97), `placeholder_stops` (R98), `flight_details` (R74), `venue_names` (R62), `user_supplied_facts` (R35), and `decisions.request:<n>` (R72/R73).
- Document writes `decisions` **one key at a time, as each question is answered**, so a dropped conversation resumes at the first unanswered key.
- A re-quote (node I refine loop, or a discount applied in document) overwrites `raw_quote.json` and appends to `log`; it never edits `units` in place — it replaces them.
- If `handoff/` exists but `final` is false, the document skill refuses to start and says the quote isn't final.
- If `handoff/` doesn't exist (a quote brought from elsewhere), the document skill falls back to its own Stage 1 and asks its questions from scratch.

---

## Contract versions

| v | Written by | What changed |
|---|---|---|
| 1 | ≤ 0.22.0 | original |
| 2 | 0.22.x | `tool`, `estimate_type`, `rate_sheet_shown` |
| **3** | **0.23.0** | the fields below. **A handoff with a lower `contract` is rejected, not interpreted.** |

**`decisions` keys are `decide.py`'s `BASE_ORDER`, in that order, plus the conditional
`greeter_cost`.** They are listed above for shape only — `decide.py` is the authority, and
the question-set guard checks this file against it. There is **no `fuel` key**: the fuel
question was removed on 7 Oct (fuel is market-scoped and engine-applied, and nothing in the
contract subtracts it). This block carried one until 10 Oct, three days after the code
stopped writing it.

**Why reject rather than read what you can.** A v1 or v2 handoff was written against the
previous MCP contract, where `estimate_type` could be `approximate`, a passenger id was
always present, and the sourcing warning arrived on the quote. Reading those fields as if
they meant what they mean now produces a document that looks right. Refusing produces a
sentence a CSM can act on: *re-run the quote.*

### What v3 adds

- **`source_tool`** — which tool produced `raw_quote.json`: `calculate_quote_units`,
  `generate_quote_options` or `calculate_temporary_quote_units`. The document says different
  things about each, and only this field distinguishes them.
- **`persisted: false`** — always, and stated rather than assumed. A temporary quote is never
  saved in Savoya, and a client document built from one must say so.
- **`temporary_pricing`** — `{rate: {...}, discount: {...}, label}` when either was supplied,
  else `null`. The label is what Core echoes into its own warning, so it reaches the client
  document; it has to be written as if read.
- **`aggregate_total`** — Core's figure (the view's `total_amount`), carried verbatim. The document fails closed if its
  own total doesn't match (C4), and that check needs Core's number from the source rather
  than re-derived.
- **`warnings`** — the unit-level warnings, **as Core sent them**, minus the single named
  suppression. Includes anything we don't recognise.
- **`sourcing`** — `{market, excess_drive_time}` captured from
  `resolve_itinerary_stops`. **This is the one field intake must carry because the document
  cannot get it any other way:** the "No local providers" warning naming the market appears
  only on stop resolution, while the quote response carries just
  `excess_drive_time: true`. Without it a Whistler job billing 12 hours against a requested
  8 can only tell the client "a neighbouring market". See `ENGINEERING.md` G4 — if Core
  starts returning the warning on the quote, this field becomes redundant rather than wrong.
- **`passenger`** — `{id, name}` only when the **user named one**. Omitted otherwise; Core
  attaches an eligible passenger to the unsaved calculation itself.

