#!/usr/bin/env python3
"""Package the plugin for the MCP named in .env.

    python3 build.py                # build for whatever .env points at
    python3 build.py --bump patch   # acceptance release: bump every manifest copy, then build
    PLUGIN_VERSION=0.27.0 python3 build.py   # acceptance release at an explicit version

.env holds one setting, SAVOYA_MCP_URL (see .env.example). An environment variable of the
same name overrides the file.

- Empty: an acceptance build. The package uses the checked-in endpoint and the current
  version, or the one from --bump or PLUGIN_VERSION, which rewrite every manifest copy
  as rebuild_plugin.py always does.
- Set: a local test build against that public HTTPS tunnel. The package is labelled
  <version>-local.<timestamp>; nothing in the repo changes, so --bump and
  PLUGIN_VERSION are refused.

The package lands in build/ (gitignored) and is checked before the path is printed.
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
ACCEPTANCE_URL = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["savoya"]["url"]


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
    parser.add_argument("--bump", choices=["patch", "minor", "major"])
    args = parser.parse_args()

    mcp_url = env_setting("SAVOYA_MCP_URL")
    local = bool(mcp_url) and mcp_url != ACCEPTANCE_URL
    if local and (args.bump or os.environ.get("PLUGIN_VERSION")):
        sys.exit("--bump and PLUGIN_VERSION are for acceptance releases. Clear SAVOYA_MCP_URL in .env to build one.")
    if local and (not mcp_url.startswith("https://") or "localhost" in mcp_url or "127.0.0.1" in mcp_url):
        sys.exit(f"SAVOYA_MCP_URL must be a public HTTPS tunnel; Claude cannot reach {mcp_url}.")

    command = [sys.executable, str(SKILL / "scripts" / "rebuild_plugin.py"), str(SKILL), str(BUILD / "plugin")]
    if local:
        current = json.loads((SKILL / "assets" / "plugin-root" / "plugin.json").read_text())["version"]
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        command += ["--mcp-url", mcp_url, "--package-version", f"{current}-local.{stamp}"]
    elif args.bump:
        command += ["--bump", args.bump]

    BUILD.mkdir(exist_ok=True)
    staging = BUILD / "savoya-quoting.plugin.partial"
    if subprocess.run(command + ["--package", str(staging)]).returncode != 0:
        sys.exit("rebuild_plugin.py failed; see its output above.")

    version = json.loads((BUILD / "plugin" / ".claude-plugin" / "plugin.json").read_text())["version"]
    package = BUILD / f"savoya-quoting-{version}.plugin"
    staging.replace(package)
    verify(package, mcp_url if local else ACCEPTANCE_URL, version)
    print(f"\n{'Local' if local else 'Acceptance'} build {version} -> {mcp_url if local else ACCEPTANCE_URL}")
    print(package.relative_to(ROOT))


if __name__ == "__main__":
    main()
