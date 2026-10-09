# Setup

Two audiences, two lists. The CSM's part takes five minutes in the app and needs no Terminal. IT's part is optional and makes PDFs native.

---

## Part 1 — What the CSM does (in the app, ~5 minutes, once)

**1. Install the plugin.** Download the `.plugin` file and import it in Claude. If an older version is installed, remove it first.

**2. Connect Savoya.** The first time Claude prices something it will ask you to sign in. Claude discovers its own OAuth client identity; no custom client ID or secret is bundled. Sign in with your Savoya account. If sign-in works but quoting fails, your account needs the `access:savoya_mcp` permission — ask engineering.

**3. Connect Google Drive.** In Claude's settings, turn on the Google Drive connector and sign in with your Savoya Google account. This is how your quote sessions get saved to the shared folder so the tool keeps improving. Nothing else uses it.

**4. Tell Claude your name, once.** The first time it saves a session it will ask what name to record you as. Answer once; it remembers.

That's it. You can quote, produce client documents, and draft emails.

## Developer environment switching

Acceptance remains the checked-in default. For local testing, build with `rebuild_plugin.py --mcp-url https://<active-public-tunnel>/mcp`; the packaged MCP endpoint switches to that host; Claude discovers its own OAuth client identity. The override affects only the packaged copy. Claude cannot reach `localhost`. The public tunnel must match the MCP's `SAVOYA_MCP_PUBLIC_URL` and Auth0 audience.

Before switching environments, run `handoff.py clear-cache`, import the new package, reconnect OAuth on that same tunnel host, and test in a brand-new conversation. Passenger cache data from older versions is cleared with the client cache; unrelated user configuration is preserved.

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
| Google Drive | Everything still works; sessions save locally instead, and the improvement loop gets nothing until they're collected by hand (`scripts/export_captures.py` zips them) |
| Name | Sessions save anonymously; you can't tell whose workflow produced what |
| Part 2 installs | No native PDF (the document comes as a web page — Print → Save as PDF gives an identical file), verification runs structural checks only, no route maps |

## What CSMs should never see
Install commands, package managers, Terminal. If a CSM asks why there's no PDF, the answer is "it's a one-time setup on this computer — I can note it for IT." Claude is instructed not to paste commands at them.
