// Turn a captured v1 quote response (raw Core payload + presentation v1, or raw Core
// payload alone) into the response the MCP sends at presentation version 2, using the
// MCP's own mapping rather than a copy of it.
//
// Run with Node 24 from a checkout of savoya-quote-mcp that carries presentation
// version 2 (branch ethan/green-380-compact-quote-view at 400b1d4 or later), with its
// node_modules installed:
//
//   cd /path/to/savoya-quote-mcp
//   npx tsx /path/to/Savoya-Plugin/tests/tools/make_v2_fixture.mts <raw_quote.json> <raw_quote.v2.json>
//
// Several pairs may be given in one run: <in1> <out1> <in2> <out2> ...
//
// To regenerate every fixture in the plugin (each raw_quote.json under
// skills/*/evals/fixtures gets a raw_quote.v2.json beside it):
//
//   npx tsx /path/to/Savoya-Plugin/tests/tools/make_v2_fixture.mts --all /path/to/Savoya-Plugin
//
// LEGACY_V1_ONLY lists captures that predate the current Core contract. The MCP's schema
// rejects them, so they have no v2 form and stay v1-only (unversioned raw Core payloads,
// which the plugin still reads). Any other rejection fails the run.
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
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";

type Json = Record<string, any>;

const PLUGIN_KEYS = ["merged_packages", "_ingest"];
const LEGACY_V1_ONLY = ["skills/quote-document/evals/fixtures/boston-exact-path/raw_quote.json"];

function rawFixtures(root: string): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (name === "raw_quote.json") found.push(path);
    }
  };
  for (const skill of ["quote-document", "quote-intake"]) walk(join(root, "skills", skill, "evals", "fixtures"));
  return found;
}

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

let args = process.argv.slice(2);
let root: string | undefined;
if (args[0] === "--all" && args.length === 2) {
  root = args[1];
  args = rawFixtures(root)
    .filter((path) => !LEGACY_V1_ONLY.includes(relative(root!, path)))
    .flatMap((path) => [path, path.replace(/raw_quote\.json$/, "raw_quote.v2.json")]);
}
if (!args.length || args.length % 2) {
  console.error("usage: make_v2_fixture.mts <raw_quote.json> <raw_quote.v2.json> [<in> <out> ...] | --all <plugin root>");
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
    // faithfully (and record why) or leave the fixture v1-only.
    failed += 1;
    const issues = (error as { issues?: Array<{ path: unknown[]; message: string }> }).issues;
    console.error(`${args[i]}: REJECTED by the MCP schema`);
    for (const issue of issues ?? [{ path: [], message: String(error) }]) {
      console.error(`  - ${issue.path.join(".") || "(root)"}: ${issue.message}`);
    }
  }
}
process.exit(failed ? 1 : 0);
