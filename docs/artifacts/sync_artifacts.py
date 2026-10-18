#!/usr/bin/env python3
"""Keep the Claude artifacts in step with the plugin (PRD R86-R90, TDD 14.x).

  sync_artifacts.py render              render help.html from help.template.html + help.md
  sync_artifacts.py hashes              record the current source hashes and release in artifacts.json
  sync_artifacts.py check [--quiet]     exit 1 if a managed artifact is stale; list what needs publishing
  sync_artifacts.py published KEY REL   record that KEY was republished at release REL

Not shipped in the plugin. Publishing itself is a session step: the repo cannot call the
artifact tool, so `check` lists what to republish by URL and `published` records it.
"""
import argparse, ast, hashlib, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MANIFEST = os.path.join(HERE, "artifacts.json")
HELP_MD = os.path.join(ROOT, "skills", "quote-intake", "references", "help.md")
CONTRACT = os.path.join(ROOT, "skills", "quote-intake", "references", "mcp-contract.md")
TREE = os.path.join(ROOT, "skills", "quote-intake", "references", "decision-tree.md")
DECIDE = os.path.join(ROOT, "skills", "quote-document", "scripts", "decide.py")
PLUGIN_JSON = os.path.join(ROOT, "skills", "quote-document", "assets", "plugin-root", "plugin.json")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8")); h.update(b"\0")
    return h.hexdigest()[:16]


def release():
    return json.load(open(PLUGIN_JSON))["version"]


def tools():
    m = re.search(r"```tools\n(.*?)```", read(CONTRACT), re.S)
    return [t.strip() for t in m.group(1).splitlines() if t.strip()] if m else []


def question_order():
    # decide.py runs as a script when imported, so read the list by AST (as deliverables.py does)
    for n in ast.parse(read(DECIDE)).body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "BASE_ORDER" for t in n.targets):
            return list(ast.literal_eval(n.value))
    return []


def split_help():
    t = read(HELP_MD)
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    front = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1); front[k.strip()] = v.strip().strip('"')
        t = t[m.end():]
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    secs, cur = {}, None
    for line in t.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); secs[cur] = []
        elif cur is not None:
            secs[cur].append(line)
    return front, {k: "\n".join(v).strip("\n") for k, v in secs.items()}


def source_hash(key):
    if key == "help":
        _, secs = split_help()
        return sha(json.dumps(secs, sort_keys=True), ",".join(question_order()), ",".join(tools()))
    return sha(read(TREE), ",".join(tools()), ",".join(question_order()))


# ---- tiny markdown -> html (bold, code, links are all the help content uses) ----
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def blocks(md):
    out, items, kind = [], [], None
    def flush():
        nonlocal items, kind
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{kind}>")
        items, kind = [], None
    for line in md.splitlines():
        m1, m2 = re.match(r"\d+\.\s+(.*)", line), re.match(r"-\s+(.*)", line)
        if m1:
            if kind != "ol": flush(); kind = "ol"
            items.append(m1.group(1))
        elif m2:
            if kind != "ul": flush(); kind = "ul"
            items.append(m2.group(1))
        elif line.strip():
            flush(); out.append(f"<p>{inline(line.strip())}</p>")
        else:
            flush()
    flush()
    return "\n".join(out)


def faq(md):
    out = []
    for part in re.split(r"^### ", md, flags=re.M)[1:]:
        q, _, a = part.partition("\n")
        out.append(f'<details class="qa"><summary>{inline(q.strip())}</summary>{blocks(a.strip())}</details>')
    return "\n".join(out)


def render():
    front, secs = split_help()
    tpl = read(os.path.join(HERE, "help.template.html"))
    rep = {
        "{{release}}": release(),
        "<!--WHAT-->": blocks(secs["What it does"]),
        "<!--BEFORE-->": blocks(secs["Before you start"]),
        "<!--PRICE-->": blocks(secs["Before you promise a price"]),
        "<!--STEPS-->": blocks(secs["How a quote goes"]),
        "<!--QUESTIONS-->": blocks(secs["The questions it asks, and why"]),
        "<!--LIMITS-->": blocks(secs["What it cannot do yet"]),
        "<!--FAQ-->": faq(secs["Questions and answers"]),
    }
    for k, v in rep.items():
        if k not in tpl:
            sys.exit(f"template has no slot {k}")
        tpl = tpl.replace(k, v)
    left = re.findall(r"\{\{[a-z_]+\}\}", tpl)
    if left:
        sys.exit(f"unfilled placeholders: {left}")
    return tpl


def load():
    return json.load(open(MANIFEST))


def save(m):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2); f.write("\n")


def file_hash(a):
    p = os.path.join(HERE, a["file"])
    return sha(read(p)) if os.path.exists(p) else ""


def check(quiet=False):
    m, rel, bad, publish = load(), release(), [], []
    for a in m["artifacts"]:
        k = a["key"]
        if not a.get("managed"):
            if not quiet: print(f"  ○ {k}: not yet managed (file imported and refreshed in a later release)")
            continue
        if not os.path.exists(os.path.join(HERE, a["file"])):
            bad.append(f"{k}: {a['file']} is missing"); continue
        if a["source_hash"] != source_hash(k):
            bad.append(f"{k}: its sources changed since the artifact was last synced (run render/hashes, then republish)")
        if k == "help":
            if read(os.path.join(HERE, a["file"])) != render():
                bad.append("help: help.html is not the render of help.md and the template (run `render`)")
            front, _ = split_help()
            if a.get("url") and front.get("page_url") != a["url"]:
                bad.append("help: page_url in help.md does not match the manifest URL")
            if front.get("describes_release") != a["reflects_version"]:
                bad.append("help: describes_release in help.md does not match the manifest release")
        if a.get("published_version") != a["reflects_version"] or a.get("published_hash") != file_hash(a):
            publish.append(f"{k} ({a.get('url') or 'no URL yet'})")
    for b in bad: print(f"  ✗ {b}")
    if publish and not quiet:
        print("  → to publish by URL: " + "; ".join(publish))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["render", "hashes", "check", "published"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.cmd == "render":
        open(os.path.join(HERE, "help.html"), "w", encoding="utf-8").write(render()); print("rendered help.html")
    elif a.cmd == "hashes":
        m = load()
        for x in m["artifacts"]:
            if x.get("managed"):
                x["source_hash"] = source_hash(x["key"])
                x["reflects_version"] = split_help()[0]["describes_release"] if x["key"] == "help" else release()
        save(m); print("hashes recorded")
    elif a.cmd == "published":
        key, rel = a.args
        m = load()
        for x in m["artifacts"]:
            if x["key"] == key:
                x["published_version"] = rel; x["published_hash"] = file_hash(x)
        save(m); print(f"{key} recorded as published at {rel}")
    else:
        sys.exit(0 if check(a.quiet) else 1)


if __name__ == "__main__":
    main()
