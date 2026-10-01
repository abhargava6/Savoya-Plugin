---
name: quote-document
description: Turn a final contract-v3 Savoya quote handoff into client-ready PDF, email, HTML, Word, or Excel output. Use after quote-intake has selected one exact, complete, non-persisted Core package. Preserves Core quantities, rates, discounts, and totals without local pricing arithmetic.
compatibility: Requires the Savoya MCP connector, Python 3, and format-specific document tooling.
---

# Savoya quote document

This is a presentation pipeline, not a pricing engine. `handoff/raw_quote.json` is authoritative. Read `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/RULES.md` before rendering.

## 1. Validate and normalize

Require `handoff/intake.json` with `contract: 3` and `final: true`. The handoff must be exact, complete, non-persisted, and contain one selected package.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/normalize_quote.py \
  --from-handoff handoff quote.json --prepared-by "<user>"
```

Normalization copies values by field presence. It preserves legitimate zero values and copies Core's quantity, unit total, line total, aggregate total, base/effective rates, returned subtotal/temporary-discount amounts, terms, warnings, and temporary-pricing metadata. It never reconstructs pricing.

## 2. Ask document questions

Drive questions one at a time:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py --next
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/decide.py <key> <answer>
```

Order: `discount_pct`, `cover`, `personalization`, `map`, `format`. Format may remove irrelevant cover/map questions.

Fuel overrides and priced greeter fees are not supported. Keep existing Core fuel/special-handling facts visible. Turn operational requests into non-priced notes or clearly say that pricing change is unsupported.

## 3. Re-quote a document-stage discount

The discount question remains part of the experience, but its answer is implemented in Core.

For a new/changed whole-percentage discount:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py prepare-discount \
  --dir handoff --percent <whole-number> --out discount-request.json
```

Call the tool named in the command output using `discount-request.json`. Then save the MCP response and replace the handoff:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-intake/scripts/handoff.py replace \
  --dir handoff --raw discount-result.json --source-request discount-request.json \
  --tool <calculate_temporary_quote_units-or-calculate_quote_units>
```

Run normalization again. A percentage of `0` removes the temporary discount. If temporary rates remain, the helper keeps the temporary tool; otherwise it returns the standard tool. It rejects mixed packages that would leave only some units temporary.

Never use `apply_adjustments.py` to change money. It exists only as a fail-safe and rejects mutation flags.

## 4. Personalize and render

Preserve the current covers, flight-time behavior, maps, pagination, email voice, client notes, capture flow, and export formats.

Renderers use Core-returned effective rates and totals directly. Percentage-only adjustments may be labeled without inventing a dollar value. Omit a package subtotal row when Core did not return one. Never synthesize an Option B; comparisons happen through `generate_quote_options` before handoff.

Format references:

- PDF/print/email: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-print.md`
- HTML: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-html.md`
- DOCX: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-docx.md`
- XLSX: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/format-xlsx.md`

DOCX/XLSX must copy returned values. Do not add spreadsheet formulas that recalculate rates, adjustments, or totals.

## 5. Verify and deliver

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/verify_document.py \
  quote.json --raw handoff/raw_quote.json --pdf out.pdf [--email draft.txt]
```

Verification compares normalized quantity, vehicle, unit total, line total, and aggregate total directly with `raw_quote.json`. It intentionally does not require line totals to sum to `aggregate_total`; Core owns that arithmetic.

Exit 0: deliver. Exit 1: fix and rerun. Exit 2: deliver with one clear verification limitation. Keep the existing capture workflow after delivery/feedback.

## Client-facing boundaries

- Never expose internal IDs, basis points, rate records, tool names, or persistence details.
- Always show the chosen vehicle/quantity, pricing basis, effective rate, per-line total, cancellation rules, special events, relevant warnings, and final Core total.
- Preserve airport/fabricated-flight behavior unchanged.
- Operational additions without supported Core pricing are notes, not added money.
