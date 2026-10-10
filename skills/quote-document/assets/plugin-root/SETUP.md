<!--
  MIRROR. The copy that ships is skills/quote-document/assets/plugin-root/SETUP.md
  Editing only this file changes nothing a CSM ever sees.

  Why there are two: rebuild_plugin.py rebuilds the plugin from an INSTALLED skill mount,
  where only skills/quote-document/ exists and there is no repo. assets/plugin-root/ is
  how the build survives having no repo around it — that is what makes the weekly pass
  work from a chat with no terminal. The duplication is deliberate; don't "fix" it by
  pointing the build at the repo root, which would break rebuilding from an install.

  Change both copies. regress.py's `paired docs` guard fails if they drift.
-->
# Setup

Two audiences, two lists. The CSM's part takes five minutes in the app and needs no Terminal. IT's part is optional and makes PDFs native.

---

## Part 1 — What the CSM does (in the app, ~5 minutes, once)

**1. Install the plugin.** Download the `.plugin` file and import it in Claude. If an older version is installed, remove it first.

**2. Connect Savoya.** The first time Claude prices something it will ask you to sign in. Sign in with your Savoya account — there is nothing to paste and no secret to fill in. If Claude still shows a client ID or secret field, leave both blank. If sign-in works but quoting fails, your account needs the `access:savoya_mcp` permission — ask engineering.

**3. Connect Google Drive.** In Claude's settings, turn on the Google Drive connector and sign in with your Savoya Google account. This is how your quote sessions get saved to the shared folder so the tool keeps improving. Nothing else uses it.

**4. Tell Claude your name, once.** The first time it saves a session it will ask what name to record you as. Answer once; it remembers.

**5. Check it worked.** Say to Claude: **"check my quoting setup"**. It will confirm the Savoya connection, confirm saving works, and write a small test entry to the shared folder to prove your account can actually write to it. Do this once now — a connector that is switched on but can't write to the folder looks exactly like one that works, and the only symptom is that nobody ever sees your sessions.

That's it. You can quote, produce client documents, and draft emails.

---

## Part 2 — What IT / the plugin owner does (once per machine, optional)

Everything works without this. It only unlocks native PDF output, full document verification, and route maps.

Run on the machine:
```
python3 skills/quote-document/scripts/preflight.py --admin
```
It prints exactly what's missing with the right commands for that OS. For reference:

| Capability | macOS | Windows | Linux |
|---|---|---|---|
| **PDF output** | `pip3 install playwright && python3 -m playwright install chromium` | `pip install playwright && python -m playwright install chromium` | same as macOS |
| **Full verification, PDF covers** | `brew install poppler` | `choco install poppler` (or scoop) | `sudo apt install poppler-utils` |
| **Route maps** | `pip3 install pillow` | `pip install pillow` | `pip3 install pillow` |

Chromium is ~150 MB and takes a minute or two; the rest is seconds.

**Also grant Drive access.** Each CSM needs **Editor** on the shared capture folder — their Drive connector uploads as their own Google account, so Viewer isn't enough. The folder id lives in `skills/quote-document/assets/capture.json`. Add people explicitly rather than relying on a share link.

> The captures contain client names, addresses and pricing. Keep the folder restricted to the team, and move it to a Savoya Workspace shared drive before rolling out widely — a personal Google account can't be administered by the company.

---

## If something is skipped

| Skipped | Effect |
|---|---|
| Savoya connector | Nothing works — this one is required |
| Google Drive | Everything still works; sessions save locally instead, and Claude says so at the end of each document until it's connected. The improvement loop gets nothing in the meantime |
| **Editor** on the folder | Looks identical to working: the connector is on, uploads just fail. Step 5 is the only thing that catches it |
| Step 5 | You won't know any of the above went wrong. This happened: the tool ran for weeks and nothing reached the shared folder |
| Name | Sessions save anonymously; you can't tell whose workflow produced what |
| Part 2 installs | No native PDF (the document comes as a web page — Print → Save as PDF gives an identical file), verification runs structural checks only, no route maps |

## What CSMs should never see
Install commands, package managers, Terminal. If a CSM asks why there's no PDF, the answer is "it's a one-time setup on this computer — I can note it for IT." Claude is instructed not to paste commands at them.
