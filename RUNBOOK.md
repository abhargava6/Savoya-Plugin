# Weekly pass — run it from a Claude chat

You don't need a terminal. Open a **new chat in the Quoting MCP project** and paste:

> Run the weekly pass for the savoya-quoting plugin: rebuild the source from the installed skill, pull this week's captures from the Drive capture folder, unpack and regress them, and report the patterns before changing anything.

Claude will:
1. Copy the installed skill (`/mnt/skills/plugins/savoya-quoting:quote-document`) into a working folder and run `scripts/rebuild_plugin.py` to reassemble the full plugin tree.
2. List `*.capture.json` in the Drive folder (`assets/capture.json` → `drive_folder_id`) via the Google Drive connector, download the new ones, and run `scripts/unpack_capture.py` + `scripts/regress.py --pdf` against them.
3. Report: which captures rebuild cleanly, which don't, and what the feedback/placeholder fields say. It stops here and waits for you.

Then you say what to fix. Claude edits scripts / `feedback.md` / SKILL.md, promotes any capture that covers a new shape into `evals/fixtures/`, runs `regress.py --pdf` until green, and hands you a versioned `.plugin` file. You install it in Cowork.

## If there are many captures
The Drive connector returns each file through the chat, which is fine for a handful. Past ~15, zip the folder and attach it to the chat instead — Claude unzips it from uploads.

## Terminal equivalent (optional)
Same scripts, same order, from `skills/quote-document/`:
```
python3 scripts/unpack_capture.py <captures-dir> --fixtures /tmp/week
python3 scripts/regress.py --fixtures /tmp/week --pdf
# …fix…
python3 scripts/regress.py --pdf
python3 scripts/rebuild_plugin.py . /tmp/build --bump patch --package ~/Desktop/savoya-quoting.plugin
```

For a local MCP, replace the last line with a `PLUGIN_VERSION=...-local...` build and add `--mcp-url https://<active-public-tunnel>/mcp`. Never point a package at localhost and never rewrite the checked-in acceptance config.
