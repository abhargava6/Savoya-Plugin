#!/usr/bin/env python3
"""Package the plugin for one Savoya MCP environment.

    python3 build.py                     # build for whatever .env points at
    python3 build.py --env staging       # build for a named environment, ignoring .env
    python3 build.py --mcp-url https://<tunnel>/mcp   # local test build against a tunnel
    python3 build.py --env staging --bump patch       # release: bump every manifest copy, then build
    PLUGIN_VERSION=0.27.0 python3 build.py --env acceptance   # release at an explicit version
    python3 build.py --env production --bump patch    # production release

The MCP is chosen by, in order: --env or --mcp-url, then SAVOYA_MCP_URL from the
environment, then SAVOYA_MCP_URL in .env (see .env.example), then the checked-in .mcp.json.

- A URL in ENVIRONMENTS is a release build for that environment. The package uses the
  current version, or the one from --bump or PLUGIN_VERSION, which rewrite every manifest
  copy as rebuild_plugin.py always does.
- Any other URL is a local test build against that public HTTPS tunnel. The package is
  labelled <version>-local.<timestamp>; nothing in the repo changes, so --bump and
  PLUGIN_VERSION are refused.

The checked-in .mcp.json stays on the default environment; a build for any other MCP
rewrites only the packaged copy. The package lands in build/ and is checked before the
path is printed.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
SKILL = ROOT / "skills" / "quote-document"
BUILD = ROOT / "build"
ENVIRONMENTS = {
    "acceptance": "https://mcp-acceptance.savoya.net/mcp",
    "staging": "https://mcp-staging.savoya.net/mcp",
    "production": "https://mcp-core.savoya.net/mcp",
}
DEFAULT_URL = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["savoya"]["url"]


def env_setting(name):
    if os.environ.get(name):
        return os.environ[name].strip()
    env_file = ROOT / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip("'\"")
    return ""


def target(args):
    """Return (environment name, MCP URL); the name is "local" for a tunnel."""
    if args.env:
        return args.env, ENVIRONMENTS[args.env]
    url = args.mcp_url or env_setting("SAVOYA_MCP_URL") or DEFAULT_URL
    for name, known in ENVIRONMENTS.items():
        if url == known:
            return name, url
    return "local", url


def verify(package, mcp_url, version):
    with zipfile.ZipFile(package) as z:
        if z.testzip() is not None:
            sys.exit(f"{package} is corrupt.")
        server = json.loads(z.read(".mcp.json"))["mcpServers"]["savoya"]
        packaged_version = json.loads(z.read(".claude-plugin/plugin.json"))["version"]
        names = set(z.namelist())
    problems = []
    if server["url"] != mcp_url:
        problems.append(f"MCP URL is {server['url']}, expected {mcp_url}")
    if "oauth" in server:
        problems.append("the package bundles an OAuth client; Claude must use its own identity")
    if packaged_version != version:
        problems.append(f"version is {packaged_version}, expected {version}")
    for skill in ("quote-intake", "quote-document"):
        if f"skills/{skill}/SKILL.md" not in names:
            problems.append(f"skill {skill} is missing")
    if problems:
        sys.exit("Package check failed:\n- " + "\n- ".join(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    choose = parser.add_mutually_exclusive_group()
    choose.add_argument("--env", choices=sorted(ENVIRONMENTS), help="build for a named MCP environment")
    choose.add_argument("--mcp-url", help="build a local test package against this public HTTPS tunnel")
    parser.add_argument("--bump", choices=["patch", "minor", "major"])
    args = parser.parse_args()

    if DEFAULT_URL not in ENVIRONMENTS.values():
        sys.exit(f".mcp.json points at {DEFAULT_URL}, which is not in build.py's ENVIRONMENTS.")
    env, mcp_url = target(args)
    local = env == "local"
    if local and (args.bump or os.environ.get("PLUGIN_VERSION")):
        sys.exit("--bump and PLUGIN_VERSION are for release builds. Pick an environment with --env to build one.")
    if local and (not mcp_url.startswith("https://") or "localhost" in mcp_url or "127.0.0.1" in mcp_url):
        sys.exit(f"The MCP URL must be a public HTTPS tunnel; Claude cannot reach {mcp_url}.")

    command = [sys.executable, str(SKILL / "scripts" / "rebuild_plugin.py"), str(SKILL), str(BUILD / "plugin")]
    if mcp_url != DEFAULT_URL:
        command += ["--mcp-url", mcp_url]
    if local:
        current = json.loads((SKILL / "assets" / "plugin-root" / "plugin.json").read_text())["version"]
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        command += ["--package-version", f"{current}-local.{stamp}"]
    elif args.bump:
        command += ["--bump", args.bump]

    BUILD.mkdir(exist_ok=True)
    partial = BUILD / "savoya-quoting.plugin.partial"
    if subprocess.run(command + ["--package", str(partial)]).returncode != 0:
        sys.exit("rebuild_plugin.py failed; see its output above.")

    version = json.loads((BUILD / "plugin" / ".claude-plugin" / "plugin.json").read_text())["version"]
    package = BUILD / (f"savoya-quoting-{version}.plugin" if local else f"savoya-quoting-{version}-{env}.plugin")
    partial.replace(package)
    verify(package, mcp_url, version)
    print(f"\n{env.capitalize()} build {version} -> {mcp_url}")
    print(package.relative_to(ROOT))


if __name__ == "__main__":
    main()
