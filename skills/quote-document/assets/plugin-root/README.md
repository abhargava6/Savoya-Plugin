# Savoya Quoting plugin 0.23

Claude plugin for exact, non-persisted Savoya quotes and client-ready exports.

| Component | Purpose |
|---|---|
| `.mcp.json` | Matching acceptance MCP endpoint and OAuth client ID |
| `quote-intake` | Resolve requests, preserve the rate-sheet choice, call exact Core-backed tools, select one complete option, and write handoff contract v3 |
| `quote-document` | Re-quote temporary document discounts through MCP, then render Core-returned values as PDF, email, HTML, DOCX, or XLSX |

Savoya MCP/Core owns vehicle metadata, capacity sizing, rates, discounts, and totals. The plugin owns conversation, presentation, capture, and exports. It never persists a reservation or recalculates final money.

## Supported quote paths

- Selected package: `calculate_quote_units`
- Complete comparisons: `generate_quote_options`
- Temporary rates/discounts: `calculate_temporary_quote_units`

## Build

```bash
python3 skills/quote-document/scripts/regress.py --pdf
PLUGIN_VERSION=0.23.0 python3 skills/quote-document/scripts/rebuild_plugin.py \
  skills/quote-document /tmp/savoya-quoting-acceptance \
  --package /tmp/savoya-quoting-0.23.0.plugin
```

For local testing, add `--mcp-url https://<active-public-tunnel>/mcp`. It changes the packaged MCP endpoint and OAuth client ID to the same public host without modifying the checked-in config. Claude cannot reach localhost; the tunnel must match the MCP public URL and Auth0 audience. Clear the developer cache, reconnect OAuth, and start a new conversation after switching environments.
