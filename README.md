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
| `.mcp.json` | Savoya quoting MCP URL for the environment this package was built for. Each CSM signs in individually with their Savoya account; the plugin bundles no OAuth client. |
| `skills/quote-intake` | Client request → **exact** engine quote (`generate_quote_options` / `calculate_quote_units`): resolve client + stops (parallel), two questions, value/elevated summary, refine loop, handoff |
| `skills/quote-document` | Handoff → client-facing document: six forced questions (discount, commission, format, cover, personalization, map), then PDF / email copy / HTML / DOCX / XLSX |

## Who it's for
Savoya ops, sales, and CSMs building quotes for clients. Not for client-side coordinators.

## Connecting to Savoya (every CSM, first use)
The plugin registers the Savoya MCP server for the environment it was built for; the URL is in the plugin's `.mcp.json`. On first tool call Cowork starts a sign-in on that environment's Savoya login page.

Sign in with your Savoya account. **There is no client ID to paste and no secret to fill in** — Claude discovers its own OAuth client identity, and the plugin bundles neither. If a client ID or secret field still appears, leave both blank. If sign-in succeeds but tool calls fail with 403, ask engineering to check your Savoya role and that environment's Auth0 setup; it's not a plugin problem.

For **Claude Code**, use `claude mcp add --transport http savoya <MCP URL from .mcp.json>`. It signs in with Claude Code's own client identity, which works only where engineering has imported that identity into the environment's Auth0 tenant.

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

---

## Working on this repo

The plugin is edited here and installed as a packaged `.plugin` file. Nothing is
installed from this folder directly.

```bash
# 1. make changes under skills/

# 2. the suite must be green before any repackage — it renders real PDFs
python3 skills/quote-document/scripts/regress.py --pdf

# 3. build AND bump in one step -- never hand-edit a version number
python3 build.py --bump patch
```

`build.py` packages for one MCP environment:

```bash
python3 build.py                                  # whatever SAVOYA_MCP_URL in .env names
python3 build.py --env staging --bump patch       # a named environment, ignoring .env
python3 build.py --mcp-url https://<tunnel>/mcp   # a local tunnel, ignoring .env
```

Without `--env` or `--mcp-url`, it uses `SAVOYA_MCP_URL` from the environment or `.env`
(copy `.env.example`), and falls back to the checked-in `.mcp.json` (acceptance).
The named environments are listed in `ENVIRONMENTS` at the top of `build.py`:
`acceptance` is `https://mcp-acceptance.savoya.net/mcp` and `staging` is `https://mcp-staging.savoya.net/mcp`.

A named environment is a release build, packaged as `savoya-quoting-<version>-<env>.plugin`.
Any other URL is a local test build labelled `<version>-local.<timestamp>`; it never changes a
version in the repo, so it refuses `--bump`. Only the packaged `.mcp.json` changes; the
checked-in one stays on acceptance. The package lands in `build/` and is checked before its
path is printed.

**Never bump a version by hand.** The build reads
`skills/quote-document/assets/plugin-root/plugin.json`; `.claude-plugin/plugin.json` is the
standard manifest location, so it is the obvious file to edit, and it is the one the build
never reads. Edit the obvious file and the package comes out labelled with the new version
carrying the old content. `--bump major|minor|patch` or `PLUGIN_VERSION=x.y.z` writes every
copy. The paired-docs guard catches the mismatch now; the habit is the real control.

Upload the package from `build/` over the existing plugin.
Every environment's package is named `savoya-quoting`, so a Claude organization holds one
environment at a time; uploading another environment's package replaces it. **Plugin content is read into a session's container when that session
starts**, so test in a brand-new chat — an open one keeps the old copy.

### What the regression suite checks
Beyond the ten fixtures, `regress.py` runs **28 guards** -- 38 checks in all. Each exists
because the thing it checks either reached a CSM once, or was found shipping during a
migration. A sample of them:

- **instruction paths** — every `scripts/` / `references/` path is anchored and resolves.
- **tool contract** — no instruction file or script names an MCP tool outside the twelve
  in `mcp-contract.md`, which is the contract the suite enforces. It matches a *pattern*
  for tool-shaped names rather than a list of known-removed tools, so it catches the next
  removal as well as the last.
- **warning surfacing** — one Core warning is suppressed, by name, and an *unrecognised*
  warning still reaches the CSM.
- **presentation render** — Core's `presentation` block renders from real captures, falls
  back when absent, and surfaces a total that disagrees with its own units.
- **airport shape** — an airport stop is recognised in both response shapes, so the flight
  object and the "to be confirmed" disclosure survive.
- **positioned-from** — a job sourced from a neighbouring market tells the client so.
- **money ownership** — the total equals Core's exactly, by construction, and a gap refuses
  to render.
- **greeter leg** — a greeter carries no drive time but keeps its price.
- **handoff contract** — a handoff from an older build is refused, not reinterpreted.
- **route guards** — a blank route map and a collapsed drive time are both still rejected
  by the verifier, and the question gating is correct across the formats.
- **client_notes** — a bare string is caught rather than rendered one character per line.

A guard that cannot fail is decoration. If you change one, break it on purpose first and
confirm the suite goes red.

### Client data in this repo
The eval fixtures carry real client names, addresses and pricing, and
`skills/quote-document/assets/email-voice/samples/` holds real client emails used as the
house voice reference. **Keep this repository private.** The `.gitignore` covers the
working files a live session produces, but the fixtures are committed deliberately —
they are the regression suite.

### Documents
- `SETUP.md` — CSM setup (in-app, no terminal) and the optional IT installs
- `RUNBOOK.md` — the weekly improvement pass
- `CONTRIBUTING.md` — conventions for the skills themselves
- `CHANGELOG.md` — what changed and why

- `CLAUDE.md` — working conventions, read automatically by Claude Code in this folder

`ENGINEERING.md` (open items for Savoya engineering) lives in this repo and is **the single
canonical list** as of 2026-10-10, when the repo copy and a separate vault copy were merged
— they had carried colliding item ids. It is not part of the packaged plugin. It opens with
a "what to pick up first" ordering, because what engineering still owes is the point of the
file and 26 open items in filing order is not that.
