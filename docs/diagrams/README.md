# Flow diagrams

Mermaid source for the three flows, with each one rendered beside it, regenerated for **0.23.1** (register item F1).

| Source | Rendered | Covers |
|---|---|---|
| `seller-flow.mmd` | `seller-flow.png` | the conversation as a seller experiences it — no tools, no scripts |
| `intake-flow.mmd` | `intake-flow.png` | `decision-tree.md` nodes A–J |
| `document-flow.mmd` | `document-flow.png` | nodes K–Q |

**Hand sales `seller-flow.png`.** The PNGs are committed precisely so that replacing a
stale copy needs no terminal and no install — open the file, send the file. Re-render only
when the tree changes.

**The copies circulating with sales were drawn from the 0.22 tree and are wrong** wherever
Groups A–D changed it — they still show the approximate fallback, a passenger resolved on
every quote, six document questions including fuel, and no greeter node. Replace them from
here rather than redrawing.

## Rendering

```bash
npm install @mermaid-js/mermaid-cli@11.4.2
echo '{"args":["--no-sandbox","--disable-dev-shm-usage"]}' > pc.json
for f in seller-flow intake-flow document-flow; do
  npx mmdc -i "$f.mmd" -o "$f.png" -p pc.json -b white -s 2
done
```

Render through a **browser** — `mmdc` does, and so does any Mermaid viewer. Mermaid draws
node labels as HTML inside `<foreignObject>`, which standalone SVG rasterisers
(cairosvg, rsvg) cannot lay out: they produce a picture with the boxes in the right places
and the text overlapping itself. The diagram is not broken when that happens; the
rasteriser is.

Two Mermaid constraints these files had to work around, both of which fail as parse errors
rather than anything readable:

- **a node id cannot contain `?`** — `B?` is not a valid id, so the decision nodes are
  `BQ`, `FQ`, `GQ`, `GREETQ`
- **`call`, `note`, `end`, `class`, `style` and friends are reserved** — a `classDef` named
  `call` parses as a callback. The classes here are `toolcall`, `question`, `aside`, `halt`.
- **a semicolon ends a statement.** Inside a quoted flowchart label (`A["a; b"]`) it is
  safe, but a `sequenceDiagram` message is unquoted, so `A->>B: one thing; another` parses
  the second half as garbage. Two sequence diagrams in the architecture page were cut in
  half by exactly this. Use a comma or an em dash.

## Legend

| Shape / colour | Meaning |
|---|---|
| Dark blue rectangle, double border | an MCP tool call or a bundled script |
| Brown hexagon | a question put to the user, one per message |
| Diamond | a branch the flow decides, no user input |
| Green parallelogram | something deliberately *not* done, with the reason |
| Dark red parallelogram | a refusal — the flow stops and says why |
