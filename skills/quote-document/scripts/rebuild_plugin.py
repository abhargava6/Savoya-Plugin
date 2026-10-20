#!/usr/bin/env python3
"""Reassemble a full plugin tree from an installed (or working) skill folder.

The installed plugin exposes only skills/quote-document/; the plugin-root files
(plugin.json, .mcp.json, README, CONTRIBUTING) are kept in assets/plugin-root/
so the plugin can be rebuilt and repackaged from any environment where the
skill is mounted — e.g. a claude.ai / Cowork chat doing the weekly pass.

Usage: rebuild_plugin.py <skill_dir> <out_dir> [--bump patch|minor|major] [--package out.plugin]
                         [--mcp-url https://public-tunnel/mcp] [--package-version x.y.z-local.n]

--mcp-url and --package-version change only the assembled copy, for a local test build:
the checked-in .mcp.json stays on acceptance and no repo manifest is rewritten.
`build.py` at the repo root sets both from .env; prefer it over calling this directly.
"""
import argparse, json, os, shutil, zipfile

def bump(v, part):
    a = [int(x) for x in v.split(".")]
    i = {"major": 0, "minor": 1, "patch": 2}[part]
    a[i] += 1
    for j in range(i + 1, 3): a[j] = 0
    return ".".join(map(str, a))

ap = argparse.ArgumentParser()
ap.add_argument("skill_dir"); ap.add_argument("out_dir")
ap.add_argument("--bump", choices=["patch", "minor", "major"], default=None)
ap.add_argument("--package", default=None)
ap.add_argument("--mcp-url", default=None)
ap.add_argument("--package-version", default=None)
a = ap.parse_args()
if a.mcp_url and (not a.mcp_url.startswith("https://") or "localhost" in a.mcp_url or "127.0.0.1" in a.mcp_url):
    ap.error("--mcp-url must be a public HTTPS URL; Claude cannot reach localhost.")
if a.package_version and (a.bump or os.environ.get("PLUGIN_VERSION")):
    ap.error("--package-version labels a test build only; it cannot be combined with --bump or PLUGIN_VERSION.")

root = a.out_dir
if os.path.exists(root): shutil.rmtree(root)
os.makedirs(os.path.join(root, ".claude-plugin"))
import glob
skill_dst = os.path.join(root, "skills", "quote-document")
shutil.copytree(a.skill_dir, skill_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
# sibling skills: source tree (skills/<name>) or installed mounts (savoya-quoting:<name>)
parent = os.path.dirname(os.path.abspath(a.skill_dir))
siblings = [d for d in glob.glob(os.path.join(parent, "*")) if os.path.isdir(d) and os.path.exists(os.path.join(d, "SKILL.md"))
            and os.path.abspath(d) != os.path.abspath(a.skill_dir)]
for d in siblings:
    name = os.path.basename(d).split(":")[-1]
    if name.startswith("savoya-quoting") or name == "quote-document":
        continue
    if not os.path.basename(d).startswith("savoya-quoting:") and os.path.basename(parent) != "skills":
        continue  # installed mount: only take our own plugin's skills
    shutil.copytree(d, os.path.join(root, "skills", name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    print(f"  + skill {name}")
pr = os.path.join(skill_dst, "assets", "plugin-root")
shutil.copy(os.path.join(pr, ".mcp.json"), os.path.join(root, ".mcp.json"))
if a.mcp_url:
    mcp = json.load(open(os.path.join(root, ".mcp.json")))
    mcp["mcpServers"]["savoya"]["url"] = a.mcp_url
    json.dump(mcp, open(os.path.join(root, ".mcp.json"), "w"), indent=2)
shutil.copy(os.path.join(pr, "README.md"), os.path.join(root, "README.md"))
shutil.copy(os.path.join(pr, "CONTRIBUTING.md"), os.path.join(root, "CONTRIBUTING.md"))
for extra in ("RUNBOOK.md", "SETUP.md"):
    if os.path.exists(os.path.join(pr, extra)):
        shutil.copy(os.path.join(pr, extra), os.path.join(root, extra))
manifest = json.load(open(os.path.join(pr, "plugin.json")))
ap_version = os.environ.get("PLUGIN_VERSION")
if ap_version:
    manifest["version"] = ap_version
elif a.bump:
    manifest["version"] = bump(manifest["version"], a.bump)
if ap_version or a.bump:
    # Write EVERY copy of the manifest that exists, not just the one this script reads.
    #
    # The version lives in two places at different paths: assets/plugin-root/plugin.json,
    # which this script reads, and <repo>/.claude-plugin/plugin.json, which is the
    # standard manifest location and therefore the one a person edits. This script never
    # read the second, so bumping the obvious file and building without PLUGIN_VERSION
    # shipped a package labelled with the new version and carrying the old content. The
    # build is now the single writer: bump through --bump or PLUGIN_VERSION and every
    # copy moves together.
    source_root = os.path.dirname(os.path.dirname(os.path.abspath(a.skill_dir)))
    for dest in (os.path.join(pr, "plugin.json"),
                 os.path.join(a.skill_dir, "assets", "plugin-root", "plugin.json"),
                 os.path.join(source_root, ".claude-plugin", "plugin.json")):
        if not os.path.isdir(os.path.dirname(dest)):
            continue          # installed mount: no repo around it
        try:
            with open(dest, "w") as fh:
                json.dump(manifest, fh, indent=2)
        except OSError:
            pass  # installed mounts are read-only; the packaged copy carries the version
if a.package_version:
    manifest["version"] = a.package_version   # the packaged copy only; nothing in the repo moves
json.dump(manifest, open(os.path.join(root, ".claude-plugin", "plugin.json"), "w"), indent=2)
print(f"Rebuilt {root} at version {manifest['version']}")
if a.package:
    with zipfile.ZipFile(a.package, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d != "__pycache__"]
            for f in fn:
                if f.endswith(".pyc") or f == ".DS_Store": continue
                p = os.path.join(dp, f); z.write(p, os.path.relpath(p, root))
    print(f"Packaged {a.package} ({os.path.getsize(a.package)//1024} KB)")
