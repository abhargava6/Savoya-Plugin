# Flow diagrams

Mermaid source for the two flows, regenerated for **0.23.0** (register item F1).

| File | Covers |
|---|---|
| `intake-flow.mmd` | `decision-tree.md` nodes A–J |
| `document-flow.mmd` | nodes K–Q |

**The copies circulating with sales were drawn from the 0.22 tree and are wrong** wherever
Groups A–D changed it — they still show the approximate fallback, a passenger resolved on
every quote, six document questions including fuel, and no greeter node. Replace them from
here rather than redrawing.

## Rendering

```bash
npm install @mermaid-js/mermaid-cli@11.4.2
echo '{"args":["--no-sandbox"]}' > pc.json
npx mmdc -i intake-flow.mmd -o intake-flow.png -p pc.json -b white -s 2
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

## Legend

| Shape / colour | Meaning |
|---|---|
| Dark blue rectangle, double border | an MCP tool call or a bundled script |
| Brown hexagon | a question put to the user, one per message |
| Diamond | a branch the flow decides, no user input |
| Green parallelogram | something deliberately *not* done, with the reason |
| Dark red parallelogram | a refusal — the flow stops and says why |
