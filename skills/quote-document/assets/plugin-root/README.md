# Savoya Quoting plugin

Bundles the Savoya MCP connector with a `quote-document` skill that turns engine quotes into client-ready documents.

## Components
| Component | Purpose |
|---|---|
| `.mcp.json` | Savoya quoting MCP — acceptance URL. For production, change the URL and bump the version (env-var expansion isn't relied on). Auth is OAuth via `dev.auth.savoya.net`, scope `access:savoya_mcp`; CSM accounts need that scope. |
| `skills/quote-intake` | Client request → **exact** engine quote (`generate_quote_options` / `calculate_quote_units`): resolve client + stops (parallel), one question, `plan_approximate` quote, value/elevated summary, refine loop, handoff |
| `skills/quote-document` | Handoff → client-facing document: six forced questions (discount, fuel, cover, personalization, map, format), then PDF / email copy / HTML / DOCX / XLSX |

## Who it's for
Savoya ops, sales, and CSMs building quotes for clients. Not for client-side coordinators.

## Connecting to Savoya (every CSM, first use)
The plugin registers the Savoya MCP server at `https://mcp-acceptance.savoya.net/mcp`. On first tool call Cowork starts an OAuth sign-in with `dev.auth.savoya.net`.

If Cowork asks for an **OAuth client ID**, paste exactly:
```
https://mcp-acceptance.savoya.net/oauth/clients/claude.json
```
Leave client secret blank (it's a public PKCE client). Then sign in with your Savoya account. Your account must carry the `access:savoya_mcp` scope — if sign-in succeeds but tool calls fail with 403, ask engineering to grant that scope; it's not a plugin problem.

That client document lists only the claude.ai callback URL. It works for claude.ai and Cowork. For **Claude Code**, use `claude mcp add --transport http savoya https://mcp-acceptance.savoya.net/mcp` and let it register its own client via Auth0's dynamic registration endpoint.

## Before handing this to a CSM
Run `python3 skills/quote-document/scripts/preflight.py --admin` on their machine and follow `SETUP.md`. Without it everything still works except native PDF, full verification and route maps — and CSMs are never shown install commands.

## One-time setup (plugin owner)
1. Create a shared Drive folder, e.g. `Savoya Quote Captures`, restricted to the team — captures contain client names and pricing.
2. Put its folder ID in `skills/quote-document/assets/capture.json` → `drive_folder_id`. Repackage.
3. Each CSM installs the plugin and connects Google Drive in Cowork. That's it.

## Improving it
Every session ends with a two-question check-in and a one-command capture to `~/.savoya-quoting/captures/`.
See `CONTRIBUTING.md` for the daily/weekly loop, and run `skills/quote-document/scripts/regress.py --pdf` before repackaging.

## Flow
`quote-intake` runs when a request is pasted; it ends with "want the client PDF or email?" — no is a valid end (quote-only capture). Yes hands `handoff/intake.json` to `quote-document`, which asks nothing about the quote. Contract: `skills/quote-intake/references/handoff-contract.md`.

## Roadmap
- When the MCP gains a composite quote tool or compact responses, `quote-intake`'s call plan shrinks; nothing else changes.
