# Handoff contract — intake → document

Intake writes a `handoff/` folder in the working directory. The document skill reads it and asks nothing about the quote. Both skills treat it as the single source of truth for a conversation.

```
handoff/
  request.md        the client's message, verbatim (becomes the eval prompt later)
  raw_quote.json    the engine result, verbatim (latest re-quote) — from
                    generate_quote_options, calculate_quote_units, or
                    calculate_temporary_quote_units
  intake.json       everything intake decided + everything the document flow decides
```

## intake.json
```jsonc
{
  "contract": 1,
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
    "discount_bps": 0,
    "fuel": "keep|waive|add|none",
    "cover": "event-planners|custom|<uploaded-path>",
    "personalization": {"event_name": "...", "intro_note": "...", "contact": true, "client_logo_url": null, "leg_notes": {}, "closing_note": null},
    "map": false,
    "format": "pdf|email+pdf|html|docx|xlsx"
  },
  "log": [{"ts": "...", "step": "E", "note": "user chose options"}]
}
```

## Rules
- Intake writes `client`, `units`, `quote_mode`, `rate_sheet_shown`, `ambiguities`, `placeholders`, `final`, `selection`. It never writes `decisions`.
- Document writes `decisions` **one key at a time, as each question is answered**, so a dropped conversation resumes at the first unanswered key.
- A re-quote (node I refine loop, or a discount applied in document) overwrites `raw_quote.json` and appends to `log`; it never edits `units` in place — it replaces them.
- If `handoff/` exists but `final` is false, the document skill refuses to start and says the quote isn't final.
- If `handoff/` doesn't exist (a quote brought from elsewhere), the document skill falls back to its own Stage 1 and asks its questions from scratch.
