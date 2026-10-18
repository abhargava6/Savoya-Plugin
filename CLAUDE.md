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
python3 skills/quote-document/scripts/sync_plugin_root.py  # if you touched a root doc
python3 skills/quote-document/scripts/regress.py --pdf     # must be green
python3 skills/quote-document/scripts/rebuild_plugin.py \
    skills/quote-document /tmp/build --bump patch \
    --package /tmp/savoya-quoting.plugin
```

**Never hand-edit a version number.** The build reads
`assets/plugin-root/plugin.json`; `.claude-plugin/plugin.json` is the obvious file to
bump and the one the build never reads. Bump the obvious file, build without `--bump` or
`PLUGIN_VERSION=`, and the package is labelled with the new version carrying the old
content. `--bump major|minor|patch` and `PLUGIN_VERSION=x.y.z` write every copy. The
paired-docs guard catches the mismatch now, but the habit is the real control.

`--pdf` renders every fixture and **measures** each printed page as well as counting
them. Counting alone cannot see the worst failures here: `.page` is a fixed box with
`overflow:hidden`, so content that does not fit is cut rather than flowed, and
`pdftotext` still extracts the cut text. Run `measure_pages.py` against a real
`quote.json` to see per-page fill before changing anything about pagination.

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
- **Money is Core's, not ours.** The plugin presents totals; it does not compute them.
  Engine line amounts are pinned to Core's own granularity (per hour, per vehicle) and the
  fuel line is the remainder, so standard + lines equals Core's aggregate by construction.
  A mismatch **refuses to render** — the old code absorbed the gap into the last engine
  line, which made the document reconcile *and* made that line misstate its percentage, and
  it put a 5-vehicle Boston job 30 cents above Savoya's quote. Document **percentage** lines
  are refused outright; flat lines are fine. Whatever arithmetic remains lives in Python, is
  deterministic and is tested.
  **This covers comparisons too.** Asked which option is cheapest, price the candidates
  through Core or say a quote is needed — never answer from a rate sheet. A live session
  did rate-sheet arithmetic and said sourcing a Mini Bus from Austin would save about $80;
  the real quote came back **$707.18 more expensive**, because the arithmetic had missed
  the positioning drive time that sourcing exists to pay for. It corrected itself, but only
  after the CSM had been given a number to relay. Choosing which candidates to price is
  fine; stating a price for one you have not priced is not, however it is hedged.
- **Hours are Core's too.** `duration` is the lever, not the answer: an as-directed stop
  sent `duration: 4` bills **5.25** hours, a constant +1.25 h of positioning. Send what the
  user asked for, show what Core billed, name the difference. Never back-solve the duration.
- **Drive times come from the engine.** `normalize_quote.py` reads the engine's
  `travel_times`; `route_map.py` contributes distance and the drawn line only. The public
  router was silently overwriting authoritative numbers, and dropping unresolved stops
  produced confident 0-minute drives.
- **A degraded output is never shipped as if fine.** No basemap → draw the offline
  overview or no map, never a blank panel. A leg that lost a stop gets no drive time
  rather than an understated one. **Partial is a kind of degraded**: when the public
  router answered for 8 of 16 legs, half the distance column printed miles and half an
  em dash, and every check passed because each looked at one leg and a leg with no
  distance is individually valid. The column is published for every routable leg or for
  none. Before adding a per-item check, ask what the comparison *between* items would
  have to look like to be wrong.
- **`client_notes` is a list of strings.** A bare string iterates character by character
  and printed one letter per line down a client's PDF.
- **The fuel surcharge is market-scoped** — 5% in most markets, 10% in London and others.
  Never hardcode it; read it from the quote. Two separate bugs came from a literal `5%`.
  It is also **no longer adjustable**: Core applies it, we present it. The document flow has
  no fuel question.
- **A signal moving is as dangerous as a signal breaking.** Three live bugs in 0.23 were the
  same shape — the connector moved something and the plugin kept reading the old place, with
  no error. Airport stops moved from a top-level `airport` key to `location.type` and every
  airport stop quietly became an address, taking the flight object and the "to be confirmed"
  disclosure with it. The sourcing warning moved off the quote response to stop resolution,
  and a job billing 12 hours against a requested 8 stopped telling the client why. Two tools
  vanished and 0.22.0 kept calling them. **When a response field matters, guard both shapes
  and assert against a real capture** — a fixture written in the old shape cannot catch any
  of this.
- **Every enumerable question uses `ask_user_input_v0`, one per message.** Asking in prose
  or folding two into one sentence is how questions get skipped.
- **CSMs are not technical.** Never surface install commands, file paths, scripts or
  Terminal instructions to them. Setup is a one-time IT task; the only technical
  instruction a CSM ever gets is Print → Save as PDF.

## Guards

`regress.py` runs **37 guards** beyond the twelve fixtures — 49 checks in all. Run it; the
list below is for orientation, not for counting:

| Group | Guards |
|---|---|
| Contracts | instruction paths · **the tool contract** · handoff contract · paired docs · path resolution |
| Money | money ownership · discount attribution · email reconciles · Option B is Core's · commission · no own arithmetic |
| Client-safe | client-safe labels · sourced line · positioned-from · warning surfacing · airport shape · core coordinates · passenger count |
| Flow | the question set · greeter leg · email headings · instructions match the code · no hand editing · flight line · client requests · confirm items · capture at delivery · refusals and mechanics questions |
| Output | page fit · map honesty · route guards · presentation render · capture resilience |

With `--pdf` it also **measures every printed page** and fails on content crossing the
footer. **A guard that cannot fail is decoration.** If
you add or change one, break it on purpose first and confirm the suite goes red — the map
stub was for months a flat fill in exactly the colour a failed tile fetch produces, so the
suite could never have caught a blank map.

**The tool contract guard** fails if any instruction file or script names an MCP tool
outside the current **twelve**. `skills/quote-intake/references/mcp-contract.md`'s fenced
` ```tools ` block *is* the contract, and a second ` ```tools-removed ` block records what
left it — when the server changes, edit those and let the suite tell you what else has to
move. The guard **raises rather than defaulting** if the block is missing or empty: a guard
that silently allows everything when its input disappears is worse than no guard, because
it still prints a tick. It matches a
pattern rather than a list of tools known to be gone, so it catches the next removal as
well as the last one. `feedback-archive.md`, `CHANGELOG.md` and `regress.py` itself are
exempt, each for a reason stated in the code: the first two are dated history and
rewriting them to satisfy a guard would falsify the record; the third holds the contract
and issues no tool calls.

## Documentation comes before implementation

**Decided 2026-10-10.** The three project documents are the base the work runs off, not a
record written after it:

- `Requirements_Quoting_Pilot.md` (the **PRD**, R1–R94) — what the product must do. A new
  requirement is written here *first*, with a status, before anything is built.
- `PRD_TDD_Quoting_MCP.md` (the **TDD**) — how it is built. Updated in the same pass as the
  code, not later.
- `ENGINEERING.md` — what Savoya engineering still owes. The only list of that.

So: write the requirement, then the design, then the code. That order is a gate: the requirement is shown as a diff and approved before any file in this repo changes, and the first edit of a change is preceded by one line, "Requirement: R__, PRD diff approved: yes/no". A fix that restores a behavior an existing requirement states needs only a Notes edit, shown with the fix. When a change lands, the doc
update is part of the change rather than a follow-up — the follow-up is the thing that
doesn't happen. The cost of getting this wrong is already measured twice in this repo: a
`SKILL.md` that contradicted the code for three days and sent sessions into a hard refusal
mid-money-handling, and a `handoff-contract.md` that documented a `fuel` key for three days
after the code stopped writing one. **An instruction the code refuses is worse than a wrong
default**, because the session doesn't get a wrong answer — it gets a dead end, and then it
improvises.

## Parallel sessions — read the board, claim, then build

Several sessions can build at once. The rules that keep them from colliding:

1. **Read before building.** The Status column in `Requirements_Quoting_Pilot.md` says what is built and what is left; `BUILD_BOARD.md` (same vault folder) says who is building what now. Both are read first, every time.
2. **Check before proposing.** Search the whole requirements file for the behavior before proposing a new requirement. If one covers it, cite or amend it. Name the requirements checked.
3. **Claim, then build.** Add a row to `BUILD_BOARD.md` (item, session, branch, date) before touching code. Build only claimed items. A claim older than a day with no commits can be taken over; say so on the board.
4. **One worktree per session.** `git worktree add ../savoya-quoting-<item> -b <item>`; do not build two sessions in one checkout.
5. **Docs in the same change.** Requirement, then design, then code; set the Status when the code lands.
6. **Only the release session bumps the version, RULES and CHANGELOG, and builds the package.** Other sessions add their CHANGELOG line under "(unreleased)" and leave the version alone.
7. **Run the suite before handing back** and say which checks ran.

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
- **Special-event pricing has no fixture.** `three-city-suv-special-event` is now a misnomer;
  reproducing that path needs a service date with a known event.
- **A comparison where no option has a stored rate cannot be captured.**
  `generate_quote_options` accepts no temporary pricing fields.
- Word and Excel output has never been exercised in a real session.
- No airline resolver, so flights always go as `commercial_tbd: true` — see
  `ENGINEERING.md` item B7 (PRD R14), and B7b for the FBO sibling (PRD R52).
- **The three team diagram artifacts** (decision tree, flow, architecture) still describe
  0.26.1. Their sources are to be imported into `docs/artifacts/` and refreshed (PRD R89);
  until then `artifacts.json` marks them unmanaged and one statement in them (that the
  commission amount is never calculated) is wrong.
- A coverage audit has never been done: roughly 40 documented flags (`--remove`,
  `--cover-file`, `--no-map`, `--final`, `--rate-sheet-shown`, the personalization setters)
  are exercised by nothing in the suite. Two axes worth checking — operations nothing
  exercises, and instructions nothing validates. The second is what the three-day
  `SKILL.md` drift was.

## Claude artifacts (PRD R86–R90)

`docs/artifacts/` holds the HTML for the artifacts we publish, `artifacts.json` (the one
home for their URLs, the release each reflects and the release last published) and
`sync_artifacts.py`. The CSM help page is rendered from
`skills/quote-intake/references/help.md`, the same file the skills answer questions from.
It is open to everyone at Savoya, so it never carries a price, a client name, a tool or
script name, or anything about Savoya's internals — a guard checks.

- **Edit the content in `help.md`, then run `sync_artifacts.py render` and `hashes`.** Never
  edit `help.html` by hand; the guard fails if it is not the render.
- **Before a release:** run `sync_artifacts.py check`. It fails when a managed artifact's
  sources changed, and lists what to republish.
- **Publishing is a session step.** Publish each listed file to its URL with the Artifact
  tool, then `sync_artifacts.py published <key> <release>`.
