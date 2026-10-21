// Convert a quote response captured before GREEN-380 (raw Core payload, with or without
// a version 1 presentation) into the response the MCP sends now: the compact quote view,
// presentation version 2. It uses the MCP's own mapping rather than a copy of it, so a
// pre-GREEN-380 capture (for example one from the Drive capture folder) can still become
// a fixture. The plugin reads version 2 only.
//
// Run with Node 24 from a checkout of savoya-quote-mcp that carries presentation
// version 2, with its node_modules installed:
//
//   cd /path/to/savoya-quote-mcp
//   npx tsx /path/to/Savoya-Plugin/tests/tools/make_v2_fixture.mts <old.json> <raw_quote.json> [<in> <out> ...]
//
// A blocked result names the failing trip only when the request's unit label is known;
// the capture does not carry the request, so name it by hand in the fixture's input if needed.
//
// The tool is chosen from the response's shape, as the MCP would have been called:
// options[] -> generate_quote_options, previews[] -> preview_rate_batch, anything else
// -> calculate_quote_units (calculate_temporary_quote_units maps identically). The
// output mirrors tools.ts `toMilestoneToolResult`: a successful result is exactly
// { presentation }, a blocked result keeps its recovery fields. Keys the PLUGIN adds
// to a saved response (handoff.py's `merged_packages`, `_ingest`) are not Core's and
// are carried over unchanged, so a merged handoff fixture stays a merged handoff.
//
// A file ending in .mts because tsx compiles a .ts file outside an ESM package as CJS,
// which rejects the top-level await below.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

type Json = Record<string, any>;

const PLUGIN_KEYS = ["merged_packages", "_ingest"];

const presentationModule = pathToFileURL(join(process.cwd(), "src", "domains", "quotes", "presentation.ts")).href;
const { addPresentation, QUOTE_PRESENTATION_VERSION } = await import(presentationModule);
if (QUOTE_PRESENTATION_VERSION !== 2) {
  throw new Error(`This MCP checkout is at presentation version ${QUOTE_PRESENTATION_VERSION}; check out the version 2 branch.`);
}

function toolFor(raw: Json): string {
  if (Array.isArray(raw.options)) return "generate_quote_options";
  if (Array.isArray(raw.previews)) return "preview_rate_batch";
  return "calculate_quote_units";
}

// preview_rate_batch reads the request for each group's date; the capture kept it only
// inside its v1 presentation, so the request is rebuilt from there. Other tools need none.
function inputFor(tool: string, raw: Json): Json {
  if (tool !== "preview_rate_batch") return {};
  const groups: Json[] = raw.presentation?.data?.groups ?? [];
  return {
    previews: raw.previews.map((preview: Json, index: number) => {
      const group = groups.find((g) => g.key === preview.key) ?? groups[index] ?? {};
      // The v1 view stored the request date classified ({kind, value}); the request sent the value.
      const date = typeof group.date === "object" && group.date ? group.date.value : group.date;
      return { key: preview.key, label: preview.label ?? group.label, ...(date ? { date } : {}) };
    })
  };
}

const args = process.argv.slice(2);
if (!args.length || args.length % 2) {
  console.error("usage: make_v2_fixture.mts <old.json> <raw_quote.json> [<in> <out> ...]");
  process.exit(2);
}
let failed = 0;
for (let i = 0; i < args.length; i += 2) {
  try {
    const source: Json = JSON.parse(readFileSync(args[i], "utf8"));
    const { presentation: _v1, ...raw } = source;
    const tool = toolFor(raw);
    const presented = addPresentation(tool, raw, inputFor(tool, source));
    const view = presented.presentation.view;
    const out: Json = view === "blocked" || view === "location_confirmation" ? presented : { presentation: presented.presentation };
    for (const key of PLUGIN_KEYS) if (key in source) out[key] = source[key];
    writeFileSync(args[i + 1], JSON.stringify(out, null, 2) + "\n");
    console.log(`${args[i + 1]}: ${tool} -> ${view} (${presented.presentation.status})`);
  } catch (error) {
    // A capture the MCP's schema rejects is reported, not patched here: fix the input
    // faithfully and record why, or re-capture the quote from the live MCP.
    failed += 1;
    const issues = (error as { issues?: Array<{ path: unknown[]; message: string }> }).issues;
    console.error(`${args[i]}: REJECTED by the MCP schema`);
    for (const issue of issues ?? [{ path: [], message: String(error) }]) {
      console.error(`  - ${issue.path.join(".") || "(root)"}: ${issue.message}`);
    }
  }
}
process.exit(failed ? 1 : 0);
