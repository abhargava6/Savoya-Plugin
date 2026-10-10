<!--
  MIRROR. The copy that ships is skills/quote-document/assets/plugin-root/RUNBOOK.md
  Editing only this file changes nothing a CSM ever sees.

  Why there are two: rebuild_plugin.py rebuilds the plugin from an INSTALLED skill mount,
  where only skills/quote-document/ exists and there is no repo. assets/plugin-root/ is
  how the build survives having no repo around it — that is what makes the weekly pass
  work from a chat with no terminal. The duplication is deliberate; don't "fix" it by
  pointing the build at the repo root, which would break rebuilding from an install.

  Change both copies. regress.py's `paired docs` guard fails if they drift.
-->
# Runbook

Two things you run from a Claude chat, neither needing a terminal. **Verify a build** takes
two minutes and answers "does this work here". **The weekly pass** is the improvement loop.

---

## Verify a build — on any machine, in two minutes

Open a **new chat** (the plugin loads at session start, so an open chat keeps the previous
version) and paste:

> Run the savoya-quoting regression suite — `regress.py --pdf` from the installed plugin —
> and report anything that fails. Don't change anything you find.

Naming the plugin loads the skill, which is what makes the script path resolve. The suite
runs against the **installed copy**, which is the point: it tests what is actually on that
machine, not what is in the repo.

- **`--pdf` is the real gate.** Without it the suite checks structure only; with it, all
  ten fixtures render and their PDFs are checked. It needs a working PDF engine, so it is
  the one step that genuinely cannot run everywhere — which is exactly why it has to run
  somewhere before a release.
- **Never let the session fix what it finds.** The installed plugin is a build artifact and
  the next rebuild overwrites it. Bring failures back to the repo.
- IT can run the same line on a CSM's machine to answer "does this build work *here*". For
  what a CSM should run themselves, that is the setup check — *"check my quoting setup"* —
  which is a different thing: connectors and saving, not the test suite.

---

## Weekly pass — the improvement loop

Open a **new chat in the Quoting MCP project** and paste:

> Run the weekly pass for the savoya-quoting plugin: rebuild the source from the installed skill, pull this week's captures from the Drive capture folder, unpack and regress them, and report the patterns before changing anything.

Claude will:
1. Copy the installed skill (`/mnt/skills/plugins/savoya-quoting:quote-document`) into a working folder and run `scripts/rebuild_plugin.py` to reassemble the full plugin tree.
2. List `*.capture.json` in the Drive folder (`assets/capture.json` → `drive_folder_id`) via the Google Drive connector, download the new ones, and run `scripts/unpack_capture.py` + `scripts/regress.py --pdf` against them.
3. Report: which captures rebuild cleanly, which don't, and what the feedback/placeholder fields say. It stops here and waits for you.

Then you say what to fix. Claude edits scripts / `RULES.md` / SKILL.md, promotes any capture that covers a new shape into `evals/fixtures/`, runs `regress.py --pdf` until green, and hands you a versioned `.plugin` file. You install it in Cowork.

## If there are many captures
The Drive connector returns each file through the chat, which is fine for a handful. Past ~15, zip the folder and attach it to the chat instead — Claude unzips it from uploads.

## Terminal equivalent (optional)
Verifying a build is one line from the repo root:
```
python3 skills/quote-document/scripts/regress.py --pdf
```

The weekly pass, same scripts and same order, from `skills/quote-document/`:
```
python3 scripts/unpack_capture.py <captures-dir> --fixtures /tmp/week
python3 scripts/regress.py --fixtures /tmp/week --pdf
# …fix…
python3 scripts/regress.py --pdf
python3 scripts/rebuild_plugin.py . /tmp/build --bump patch --package ~/Desktop/savoya-quoting.plugin
```
