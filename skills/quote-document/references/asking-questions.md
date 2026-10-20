# Asking questions — always the picker, never bare prose

Every question in either skill that has enumerable answers **must** be asked with the `ask_user_input_v0` tool, which renders tappable options. A question typed as prose leaves the user guessing at the vocabulary and is the reason the flow has felt inconsistent.

## Rules
- **One tool call per question.** The tool ends your turn; the answer arrives as the next message. That's exactly the one-question-at-a-time cadence both skills require.
- **Always include a short lead-in sentence** before the call — context, not just buttons.
- **2–4 options, short labels.** More than four doesn't fit; see the cover question below.
- **Free-form answers are still fine** — the user can type instead of tapping. Handle both.
- Only ask in plain prose when the answer genuinely can't be enumerated (an intro note's wording, a logo URL, a specific percentage after they've said "yes, a discount").

## The questions, with their options

**Intake**

| Question | Options |
|---|---|
| Ambiguous stop | the 2–4 candidates, labeled by what distinguishes them |
| Several client profiles | the profile names (+ ids where names repeat) |
| No client found | `Use a no-discount client` (then ask which) · `Give me another name or id` — with the R101 tip in the lead-in |
| Blocking gap: missing year | the 2–3 plausible years |
| Blocking gap: headcount range | the endpoints, e.g. `Size for 75` · `Size for 50` |
| Blocking gap: flight-derived pickup | `12:30pm — domestic (2h)` · `11:30am — international (3h)` · `Another time` |
| Rate sheet? | `Rate sheet first` · `Straight to the quote` |
| Quote mode | `Best — one per leg` · `Options — value & elevated` · `I'll pick the vehicles` |
| Nearby markets (F2), after every lookup | one ready-made split per **newly listed** market that covers the gap alone, nearest first, at most three (`3 Orange County + 5 Los Angeles`), then `More choices`. No stated vehicle count → the market names instead. Never a market from an earlier lookup, and never marked recommended |
| Nearby markets → `More choices` | `Show 3 more markets` · `Split differently` · `Override <primary> inventory` — the first only while fewer than twelve markets have been shown, the last only when the primary market is short |
| Core returned `market_inventory_shortfall` (R95) | `Split differently` · `Show 3 more markets` · `Override inventory` |
| Refine and hand off (node I), one option or best mode | `Customize it` · `Go on to the client document` · `Just the quote, thanks` — one question; the format (PDF, email copy, …) is asked by the document flow, never here |
| Refine and hand off (node I), two or more options | `Both options → client document` (recommended; `All N options` past two) · `Option A only → client document` · `Option B only → client document` · `Customize first` · `Just the quote, thanks`. Past four options: `All options` · `Choose which` · `Customize first` · `Just the quote, thanks`. One question; it replaces the old detail-card question (G2) |

**Document** — `decide.py --next` prints the question text; wrap it in the picker:

| Key | Options |
|---|---|
| discount_pct | `No discount` · `10%` · `20%` · `Other…` (then ask the number in prose) |
| fuel (on the quote) | `Keep it` · `Take it off` |
| fuel (not on the quote) | `Add 5%` · `Leave it off` |
| greeter_cost *(only when the client asked)* | `Leave it off — note it as arranged separately` · `Add a cost…` (then ask the amount in prose) |
| format | `Email copy` · `Email copy + PDF` · `PDF` · `Printable document` — with `Word`, `Excel` and `HTML email` behind `Show all`. On a machine with no PDF engine the PDF options silently become the printable document |
| cover | your recommendation first, then two plausible alternates, then `Show all / upload my own` → if chosen, list the rest in prose |
| personalization | `Use those defaults` · `Change something` |
| map | `Add the route map` · `Skip it` |

The cover question is the only one that exceeds four options — hence the `Show all` escape hatch rather than cramming.

## Multi-part questions
The tool takes up to three questions in one call. **Don't use that** for the quoting or document flows — both are deliberately one at a time. The only acceptable multi-part call is a batch of stop ambiguities, which is one decision the user makes in one pass.
