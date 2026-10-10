<!--
  MIRROR. The copy that ships is skills/quote-document/assets/plugin-root/CONTRIBUTING.md
  Editing only this file changes nothing a CSM ever sees.

  Why there are two: rebuild_plugin.py rebuilds the plugin from an INSTALLED skill mount,
  where only skills/quote-document/ exists and there is no repo. assets/plugin-root/ is
  how the build survives having no repo around it — that is what makes the weekly pass
  work from a chat with no terminal. The duplication is deliberate; don't "fix" it by
  pointing the build at the repo root, which would break rebuilding from an install.

  Change both copies. regress.py's `paired docs` guard fails if they drift.
-->
# Improving the plugin from real quotes

Two loops. Don't mix them.

| | Renderer regression | Skill behavior |
|---|---|---|
| **What breaks** | totals, labels, terms, layout | asking the wrong question, wrong unit selected, weak line notes |
| **How you know** | `regress.py` fails | a CSM had to fix something by hand |
| **Where** | anywhere (seconds) | Cowork for testing, Claude Code for changes |
| **Automated?** | fully | semi — you grade |

## Daily: CSMs use it in Cowork — nothing to do
Every deliverable the skill renders is captured once per conversation — request, engine JSON, final quote, pre-filled assertions, who ran it, any feedback, and any workaround the session had to improvise — and uploaded to the shared Drive folder set in `skills/quote-document/assets/capture.json`.

Three things about the capture that are easy to get wrong:

- **It is always compressed** (`gzip+base64`, declared in the envelope; ~15× on real captures). There is no size at which a capture stays behind — the old 25 KB ceiling meant the richest sessions were exactly the ones that never arrived.
- **It goes up on two passes**, under different titles (`.capture.snapshot.json.gz.b64` on the render pass, `.capture.json.gz.b64` after the feedback exchange), because Drive's `create_file` always creates and because a session that ends at delivery must still leave a record.
- **`~` is not the user's disk.** On claude.ai the home directory is a cloud container reclaimed with the session; on a linked desktop the shell's home is an isolated VM. The capture reports whether its local copy is durable, and when it isn't, Drive is the only destination — so a failed upload **asks** the user to switch the connector on rather than mentioning it afterwards.

CSM setup is: install the plugin, connect Google Drive in Cowork, answer the one-time "what name should I record you as?" question.

## Weekly: improve in Claude Code
1. Download the week's `*.capture*.json.gz.b64` files from the Drive folder (Drive connector or the web UI) into a scratch dir. `unpack_capture.py` reverses the envelope and prefers the post-feedback copy of a session that has both.
2. `python3 skills/quote-document/scripts/unpack_capture.py <scratch> --fixtures /tmp/week` — it lists each capture with who/what and flags the ones carrying feedback. Then `regress.py --fixtures /tmp/week` to see which of last week's real quotes the *current* renderer still reproduces.
3. Read the flagged ones. Look for the *pattern*, not the incidents. For each, decide: renderer bug or skill behavior?
4. **Renderer bugs**: promote the fixture into `evals/fixtures/`, tighten its `expected.json` so it would have caught the bug, fix the script, run `regress.py --pdf` until green.
5. **Skill behavior**: add the prompt to `evals/evals.json` if it's a new shape, then run the skill-creator eval loop (with-skill vs without, grade in the viewer). The pattern becomes **one** dated entry in `RULES.md` and **one** edit to `SKILL.md`. Resist adding five.
6. Repackage **through the build** (`--bump patch`, or `PLUGIN_VERSION=x.y.z`) and reinstall in Cowork. Never hand-edit a version — see *Why some files exist twice* below, which this step used to contradict.

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

## Rules vs history
`skills/quote-document/RULES.md` is what Claude reads before rendering — keep it short and constraint-only. `feedback-archive.md` is the dated record of what was observed and why; new findings go there, and `RULES.md` changes only when a finding creates or alters a constraint.

## Why some files exist twice

`SETUP.md`, `RUNBOOK.md`, `README.md`, `CONTRIBUTING.md` and `.mcp.json` each exist at the
repo root **and** under `skills/quote-document/assets/plugin-root/`. `plugin.json` exists
at `.claude-plugin/` and in `plugin-root/`. This looks like sloppiness and is not.

`rebuild_plugin.py` rebuilds the whole plugin **from an installed skill mount**, where only
`skills/quote-document/` exists and there is no repo at all. That is what lets the weekly
pass run from a chat with no terminal. `assets/plugin-root/` is how the build survives
having no repo around it, so pointing the build at the repo root would break rebuilding
from an install — the opposite of a fix.

**The rules:**

- **The plugin-root copy is the one that ships.** Editing only the root copy changes
  nothing a CSM ever sees. Each root copy carries an HTML comment saying so; it is
  invisible wherever markdown is rendered.
- **`README.md` is deliberately different.** The root copy is a superset — it adds a
  "Working on this repo" section a CSM should not be handed. The shipped copy is its
  opening section. The guard knows this and checks the prefix relationship rather than
  equality.
- **Never hand-edit a version.** `.claude-plugin/plugin.json` is the standard manifest
  location and therefore the obvious place to bump — and `rebuild_plugin.py` does not read
  it. Bump through the build (`--bump patch`, or `PLUGIN_VERSION=`), which writes every
  copy. Hand-editing the obvious file and building without that flag ships a package
  labelled with the new version carrying the old content.
- **`regress.py`'s `paired docs` guard enforces all of the above**, derives the file list
  rather than hardcoding it, and **fails on a duplicated file whose relationship is not
  declared** — so adding a third copy of something forces a decision instead of quietly
  creating the next drift.

This has gone wrong three times: the tool contract had two homes and shipped 0.22.0 calling
tools the server had removed; the document question set had three and kept the `fuel`
question alive for a day after it was removed; and a `RUNBOOK.md` edit went to the root
copy alone and would never have reached anyone.
