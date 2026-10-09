#!/usr/bin/env python3
"""Report whether this machine's quoting setup is actually working.

Exists because it was possible for a CSM to finish setup, believe they were done,
quote for weeks, and for nothing to reach the shared folder — with no symptom on
either side. Everything the capture does to tell someone about a problem happens
*after* the capture script runs, so when that step didn't happen, or Drive was
never connected, or the account lacked Editor on the folder, the result was the
same: silence for the CSM and an empty folder for whoever owns the loop.

This script covers only what a local script can see: identity, the capture folder,
the backlog of sessions that never went anywhere, and whether anything crashed.
Whether the Savoya and Google Drive connectors are actually reachable can only be
settled by calling them, which the session does — see references/setup-check.md.

Prints a CSM-readable report. Never prints a path, a command or a package name.
Always exits 0: this is a status report, not a gate.
"""
import datetime as dt
import glob
import json
import os
import sys

CONFIG = os.path.expanduser("~/.savoya-quoting/config.json")
CAPTURES = os.path.expanduser("~/.savoya-quoting/captures")
HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def ago(ts):
    try:
        d = dt.datetime.fromtimestamp(ts)
    except (OSError, OverflowError, ValueError):
        return "unknown"
    days = (dt.datetime.now() - d).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


def main():
    cfg = load_json(CONFIG, {})
    user = cfg.get("user")

    captures = sorted(glob.glob(os.path.join(CAPTURES, "*.capture.json")))
    feedback = sorted(glob.glob(os.path.join(CAPTURES, "*.feedback.json")))
    failed = sorted(glob.glob(os.path.join(CAPTURES, "capture-failed-*.json")))

    writable = True
    try:
        os.makedirs(CAPTURES, exist_ok=True)
        probe = os.path.join(CAPTURES, ".write-probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError:
        writable = False

    version = load_json(
        os.path.join(HERE, "..", "..", "..", ".claude-plugin", "plugin.json"), {}
    ).get("version")

    lines, actions = [], []

    if user:
        lines.append(f"Saved sessions are recorded under your name, {user}.")
    else:
        lines.append("Saved sessions are being recorded anonymously — no name set yet.")
        actions.append("Tell me what name to record you as, and I'll remember it.")

    if not writable:
        lines.append("This computer isn't letting the tool save sessions at all.")
        actions.append("This one needs IT — I can write up what to tell them.")
    elif captures or feedback:
        newest = max(os.path.getmtime(p) for p in (captures + feedback))
        oldest = min(os.path.getmtime(p) for p in (captures + feedback))
        n = len(set(os.path.basename(p).split(".")[0] for p in (captures + feedback)))
        lines.append(
            f"{n} saved session{'s' if n != 1 else ''} on this computer, "
            f"the newest {ago(newest)} and the oldest {ago(oldest)}."
        )
    else:
        lines.append("No saved sessions on this computer yet.")

    if failed:
        lines.append(
            f"{len(failed)} session{'s' if len(failed) != 1 else ''} failed to save "
            f"properly, the most recent {ago(max(os.path.getmtime(p) for p in failed))}."
        )
        actions.append("Worth reporting — I can summarise what went wrong.")

    print("\n".join("  " + ln for ln in lines))
    if actions:
        print("\n  Worth doing:")
        print("\n".join("    - " + a for a in actions))

    # For the session, not the CSM. The connector checks are the session's job and
    # the local backlog number is what makes the Drive nudge concrete rather than
    # generic: "3 sessions haven't reached the team folder" lands, "consider
    # connecting Drive" does not.
    print("\n<<<setup-check")
    print(json.dumps({
        "plugin_version": version,
        "user_set": bool(user),
        "captures_dir_writable": writable,
        "local_sessions": len(set(os.path.basename(p).split(".")[0]
                                  for p in (captures + feedback))),
        "failed_captures": len(failed),
        "still_to_check_by_calling_them": ["savoya_mcp", "google_drive", "folder_write"],
    }, indent=1))
    print("setup-check>>>")
    sys.exit(0)


if __name__ == "__main__":
    main()
