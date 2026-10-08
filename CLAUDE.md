# Working instructions — savoya-quoting

This repo is the `savoya-quoting` Claude plugin: two skills plus the Savoya MCP
connector, packaged as a `.plugin` file and installed into Claude. It is not an
application and nothing here runs as a service. Read this before changing anything.

Owner: Ayush Bhargava. Users: Savoya ops, sales and CSMs.

## Layout

| | |
|---|---|
| `skills/quote-intake/` | client request → exact engine quote → `handoff/intake.json` |
| `skills/quote-document/` | handoff → client PDF / email copy / HTML / DOCX / XLSX |
| `skills/quote-intake/references/decision-tree.md` | the authoritative end-to-end flow, nodes A–Q |
| `skills/quote-document/RULES.md` | plugin rules learned the hard way — read before rendering |
| `skills/quote-document/feedback-archive.md` | dated history; weekly pass only |
| `skills/quote-document/evals/fixtures/` | 10 regression fixtures — real quotes |
| `SETUP.md` · `RUNBOOK.md` · `CONTRIBUTING.md` · `CHANGELOG.md` | install · weekly pass · how to improve · what changed |

## The loop

```bash
# edit under skills/ …
python3 skills/quote-document/scripts/regress.py --pdf    # must be green
PLUGIN_VERSION=0.22.1 python3 skills/quote-document/scripts/rebuild_plugin.py \
    skills/quote-document /tmp/build
```

Zip the contents of `/tmp/build` as `savoya-quoting.plugin` and upload it over the
existing plugin. **Never edit the installed copy** — it is a build artifact and the next
rebuild overwrites it.

**Plugin content is read into a session's container when that session starts.** Test in a
brand-new chat; an open one keeps the previous version. A whole afternoon went into
diagnosing "the fix didn't work" that was really a stale session.

## Rules that exist because something reached a client

Each of these is a real incident. The regression guards enforce them; don't weaken a
guard to make a change pass.

- **Every `scripts/` and `references/` path in an instruction file is anchored to
  `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/`.** A bare `scripts/x.py` resolves against the
  session's working directory, not the skill folder, and silently fails — after which the
  session improvises the flow from memory. `regress.py` lints for this.
- **Money math lives in Python, never in prose or model arithmetic.** Anything that
  computes a total is deterministic and testable.
- **Drive times come from the engine.** `normalize_quote.py` reads the engine's
  `travel_times`; `route_map.py` contributes distance and the drawn line only. The public
  router was silently overwriting authoritative numbers, and dropping unresolved stops
  produced confident 0-minute drives.
- **A degraded output is never shipped as if fine.** No basemap → draw the offline
  overview or no map, never a blank panel. A leg that lost a stop gets no drive time
  rather than an understated one.
- **`client_notes` is a list of strings.** A bare string iterates character by character
  and printed one letter per line down a client's PDF.
- **The fuel surcharge is market-scoped** — 5% in most markets, 10% in London and others.
  Never hardcode it; read it from the quote. Two separate bugs came from a literal `5%`.
- **Every enumerable question uses `ask_user_input_v0`, one per message.** Asking in prose
  or folding two into one sentence is how questions get skipped.
- **CSMs are not technical.** Never surface install commands, file paths, scripts or
  Terminal instructions to them. Setup is a one-time IT task; the only technical
  instruction a CSM ever gets is Print → Save as PDF.

## Guards

`regress.py` runs four guards beyond the fixtures: instruction paths, **the tool
contract**, route guards (blank map, collapsed drive time, question gating across all
seven formats), and `client_notes` shape. **A guard that cannot fail is decoration.** If
you add or change one, break it on purpose first and confirm the suite goes red — the map
stub was for months a flat fill in exactly the colour a failed tile fetch produces, so the
suite could never have caught a blank map.

**The tool contract guard** fails if any instruction file or script names an MCP tool
outside the current nine. `MCP_TOOLS` in `regress.py` *is* the contract — when the server
changes, edit that set and let the suite tell you what else has to move. It matches a
pattern rather than a list of tools known to be gone, so it catches the next removal as
well as the last one. `feedback-archive.md`, `CHANGELOG.md` and `regress.py` itself are
exempt, each for a reason stated in the code: the first two are dated history and
rewriting them to satisfy a guard would falsify the record; the third holds the contract
and issues no tool calls.

## Two kinds of finding — keep them separate

- **Plugin issue** → fix it, add a dated entry to `skills/quote-document/RULES.md`,
  re-run `regress.py`, bump the version, add a `CHANGELOG.md` entry.
- **Savoya-side issue** (engine behaviour, tool interface, rate data) → `ENGINEERING.md`.

### Always ask before adding to ENGINEERING.md

When something looks like an engineer action item:

1. **Say so and explain why** — what was observed, what evidence supports it, what change
   is being asked for.
2. **Ask whether to add it.** Do not write to `ENGINEERING.md` unprompted, even when the
   finding is obviously real. Ayush decides what goes to engineering, because the doc is a
   commitment of someone else's time and he owns that relationship.
3. **On yes**, add a row to the index table and a detail section: what was observed, the
   evidence (real numbers and real tool responses, not paraphrase), and a one-line
   "Need:" stating the decision or change requested.
4. **Never mark an item done.** Move it to *Answered / closed* with the answer and date
   only when Ayush says it is resolved.

The same applies in reverse: if an engineering change lands and closes an item, say so and
ask before editing.

## Client data

The eval fixtures carry real client names, addresses and pricing, and
`skills/quote-document/assets/email-voice/samples/` holds real client emails used as the
house voice reference. **Keep this repository private.** Session captures live outside the
repo in `~/.savoya-quoting/captures/` and are uploaded to a shared Drive folder; only
promoted fixtures come in.

## Known gaps

- `covers-src/` (the source cover PDFs behind `assets/covers/*.jpg`) is not in this repo.
  `make_covers.py` needs it; ask Ayush for the originals before regenerating covers.
- `.mcp.json` points at `mcp-acceptance.savoya.net`. Production needs a URL change and a
  version bump.
- Word and Excel output has never been exercised in a real session.
- No airline resolver, so flights always go as `commercial_tbd: true` — see
  `ENGINEERING.md` item B7.
