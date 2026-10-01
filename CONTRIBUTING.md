# Improving the plugin from real quotes

Two loops. Don't mix them.

| | Renderer regression | Skill behavior |
|---|---|---|
| **What breaks** | totals, labels, terms, layout | asking the wrong question, wrong unit selected, weak line notes |
| **How you know** | `regress.py` fails | a CSM had to fix something by hand |
| **Where** | anywhere (seconds) | Cowork for testing, Claude Code for changes |
| **Automated?** | fully | semi — you grade |

## Daily: CSMs use it in Cowork — nothing to do
Every deliverable the skill renders is captured automatically as one `<slug>.capture.json` (~30 KB: request, engine JSON, final quote, pre-filled assertions, who ran it, any feedback) and uploaded to the shared Drive folder set in `skills/quote-document/assets/capture.json`. Revisions version as `-v2`, `-v3`. If Drive isn't connected the file stays in `~/.savoya-quoting/captures/`; `scripts/export_captures.py` zips it for hand-off.

CSM setup is: install the plugin, connect Google Drive in Cowork, answer the one-time "what name should I record you as?" question.

## Weekly: improve in Claude Code
1. Download the week's `*.capture.json` files from the Drive folder (Drive connector or the web UI) into a scratch dir.
2. `python3 skills/quote-document/scripts/unpack_capture.py <scratch> --fixtures /tmp/week` — it lists each capture with who/what and flags the ones carrying feedback. Then `regress.py --fixtures /tmp/week` to see which of last week's real quotes the *current* renderer still reproduces.
3. Read the flagged ones. Look for the *pattern*, not the incidents. For each, decide: renderer bug or skill behavior?
4. **Renderer bugs**: promote the fixture into `evals/fixtures/`, tighten its `expected.json` so it would have caught the bug, fix the script, run `regress.py --pdf` until green.
5. **Skill behavior**: add the prompt to `evals/evals.json` if it's a new shape, then run the skill-creator eval loop (with-skill vs without, grade in the viewer). The pattern becomes **one** dated entry in `RULES.md` and **one** edit to `SKILL.md`. Resist adding five.
6. Bump `version` in `.claude-plugin/plugin.json`, repackage, reinstall in Cowork.

## Promoting a capture to a permanent fixture
Only if it adds a shape `evals/README.md` doesn't list, or it caught a real bug. Otherwise leave it in captures — the regression suite should stay fast enough to run without thinking.

## Rules that came from real documents
Conventions like "fuel compounds after discount" and "seven terms bullets" were found by reading a CSM's PDF, not by testing. Record the source next to the rule in `RULES.md` so a billing-policy change can be traced to every rule that depends on it.

## When git arrives
- `regress.py --pdf` becomes a pre-commit hook.
- Version bumps become tags.
- `~/.savoya-quoting/captures` stays outside the repo; only promoted fixtures come in.

## Covers
Marketing cover PDFs live in `covers-src/` (plugin root, not shipped). The skill ships pre-rendered JPEGs in `skills/quote-document/assets/covers/`. After adding or replacing a PDF: `python3 skills/quote-document/scripts/make_covers.py covers-src`, then repackage.

## Two skills, one regression
`quote-document/scripts/regress.py` covers both: rendering fixtures and the `handoff/` fixture that proves the intake → document path yields the same numbers as the manual path. Intake's behavior evals are in `quote-intake/evals/evals.json` (skill-creator loop; they assert on tool-call sequence and unit structure, not rendering).

Pricing assertions must compare copied fields directly with exact MCP fixtures. Never add a test or renderer that recomputes an aggregate from line totals; Core owns that arithmetic. Do not run Rails tests from this repository.

## Rules vs history
`skills/quote-document/RULES.md` is what Claude reads before rendering — keep it short and constraint-only. `feedback-archive.md` is the dated record of what was observed and why; new findings go there, and `RULES.md` changes only when a finding creates or alters a constraint.
