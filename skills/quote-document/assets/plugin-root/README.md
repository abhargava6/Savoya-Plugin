<!--
  MIRROR. The copy that ships is skills/quote-document/assets/plugin-root/README.md
  Editing only this file changes nothing a CSM ever sees.

  Why there are two: rebuild_plugin.py rebuilds the plugin from an INSTALLED skill mount,
  where only skills/quote-document/ exists and there is no repo. assets/plugin-root/ is
  how the build survives having no repo around it — that is what makes the weekly pass
  work from a chat with no terminal. The duplication is deliberate; don't "fix" it by
  pointing the build at the repo root, which would break rebuilding from an install.

  Change both copies. regress.py's `paired docs` guard fails if they drift.
-->
# Savoya Quoting plugin

Bundles the Savoya MCP connector with a `quote-document` skill that turns engine quotes into client-ready documents.

## Components
| Component | Purpose |
|---|---|
| `.mcp.json` | Savoya quoting MCP — acceptance URL. For production, change the URL and bump the version (env-var expansion isn't relied on). Auth is OAuth via `dev.auth.savoya.net`, scope `access:savoya_mcp`; CSM accounts need that scope. |
| `skills/quote-intake` | Client request → **exact** engine quote (`generate_quote_options` / `calculate_quote_units`): resolve client + stops (parallel), two questions, value/elevated summary, refine loop, handoff |
| `skills/quote-document` | Handoff → client-facing document: six forced questions (discount, commission, format, cover, personalization, map), then PDF / email copy / HTML / DOCX / XLSX |

## Who it's for
Savoya ops, sales, and CSMs building quotes for clients. Not for client-side coordinators.

## Connecting to Savoya (every CSM, first use)
The plugin registers the Savoya MCP server at `https://mcp-acceptance.savoya.net/mcp`. On first tool call Cowork starts an OAuth sign-in with `dev.auth.savoya.net`.

Sign in with your Savoya account. **There is no client ID to paste and no secret to fill in** — Claude discovers its own OAuth client identity, and the plugin bundles neither. If a client ID or secret field still appears, leave both blank. Your account must carry the `access:savoya_mcp` scope — if sign-in succeeds but tool calls fail with 403, ask engineering to grant that scope; it's not a plugin problem.

For **Claude Code**, use `claude mcp add --transport http savoya https://mcp-acceptance.savoya.net/mcp` and let it register its own client via Auth0's dynamic registration endpoint.

## Before handing this to a CSM
Run `python3 skills/quote-document/scripts/preflight.py --admin` on their machine and follow `SETUP.md`. Without it everything still works except native PDF, full verification and route maps — and CSMs are never shown install commands.

## One-time setup (plugin owner)
1. Create a shared Drive folder, e.g. `Savoya Quote Captures`, restricted to the team — captures contain client names and pricing.
2. Put its folder ID in `skills/quote-document/assets/capture.json` → `drive_folder_id`. Repackage.
3. Each CSM installs the plugin and connects Google Drive in Cowork. That's it.

## Improving it
Every session ends with a feedback exchange and one capture, compressed and uploaded to the
shared Drive folder. **Drive is the only durable destination** — `~` is a cloud container or
an isolated VM depending on where the session runs, so a capture written there is reported
as non-durable and the upload is not optional. See `CONTRIBUTING.md` for the daily/weekly
loop, and run `skills/quote-document/scripts/regress.py --pdf` before repackaging.

## Flow
`quote-intake` runs when a request is pasted; it ends with "want the client PDF or email?" — no is a valid end (quote-only capture). Yes hands `handoff/intake.json` to `quote-document`, which asks nothing about the quote. Contract: `skills/quote-intake/references/handoff-contract.md`.

## Roadmap
- A **compact response mode** is the top open engineering ask (`ENGINEERING.md` G6). It is
  not a performance wish: a 16-vehicle package returns responses too large to read in one
  call, and the workaround — hand-transcribing the engine response — defeats the document's
  fail-closed total check, because both sides of that comparison then come from the same
  typing.
- Airline and FBO resolvers (`ENGINEERING.md` B7 / B7b) are the top functional gap.
- The no-client / rack-rate route (PRD R9) is unbuilt on every path and blocks the
  standalone rate-sheet document (PRD R4) behind it.
