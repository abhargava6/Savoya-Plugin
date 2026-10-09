# Savoya Quoting plugin 0.23

Claude plugin for exact, non-persisted Savoya quotes and client-ready exports.

| Component | Purpose |
|---|---|
| `.mcp.json` | Acceptance MCP endpoint with automatic OAuth client discovery |
| `quote-intake` | Resolve the request, preserve the rate-sheet choice, call exact Core-backed quote tools, select one complete option, and write handoff contract v3 |
| `quote-document` | Re-quote temporary document discounts through MCP, then render Core-returned values as PDF, email, HTML, DOCX, or XLSX |

Savoya MCP/Core owns vehicle metadata, capacity sizing, rates, discounts, and totals. The plugin owns conversation, presentation, capture, and exports. It never persists a reservation or recalculates final money.

## Supported quote paths

- Selected package: `calculate_quote_units`
- Complete comparisons: `generate_quote_options`
- Temporary rates/discounts: `calculate_temporary_quote_units`

Passenger ID is optional unless the user names a passenger. Passenger count is always preserved. Vehicle IDs/capacities come from Core previews/resolvers.

## Build

Run plugin-only checks (never Rails from this repo):

```bash
python3 skills/quote-document/scripts/regress.py --pdf
```

Acceptance package:

```bash
PLUGIN_VERSION=0.23.0 python3 skills/quote-document/scripts/rebuild_plugin.py \
  skills/quote-document /tmp/savoya-quoting-acceptance \
  --package /tmp/savoya-quoting-0.23.0.plugin
```

Local test package (public HTTPS tunnel required):

```bash
PLUGIN_VERSION=0.23.0-local.1 python3 skills/quote-document/scripts/rebuild_plugin.py \
  skills/quote-document /tmp/savoya-quoting-local \
  --mcp-url https://<active-public-tunnel>/mcp \
  --package /tmp/savoya-quoting-0.23.0-local.plugin
```

`--mcp-url` changes only the packaged build. It updates the MCP endpoint and never rewrites the checked-in acceptance config. Claude discovers its own OAuth client identity. Claude cannot reach localhost; the tunnel host must match the MCP's `SAVOYA_MCP_PUBLIC_URL` and Auth0 audience. Clear the developer cache, reconnect OAuth, and test in a brand-new conversation after switching environments.

See `SETUP.md`, `RUNBOOK.md`, `CONTRIBUTING.md`, and `docs/0.23-mcp-migration.md`.
