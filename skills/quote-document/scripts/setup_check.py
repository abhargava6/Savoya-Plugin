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


# The map needs three public community services, and a corporate network may block any
# of them independently. When they are unreachable the document still renders -- it falls
# back to a basemap-free overview drawn from coordinates the engine already resolved --
# but a CSM sees straight lines on a near-white grid and reasonably reports the map as
# "blank" or "not drawing the route". Naming which service is unreachable turns that from
# a mystery into a fact somebody can act on.
MAP_SERVICES = (
    ("the map's street data", "https://tile.openstreetmap.org/0/0/0.png"),
    ("the route finder", "https://router.project-osrm.org/route/v1/driving/13.4,52.5;13.5,52.5?overview=false"),
    ("the address lookup", "https://nominatim.openstreetmap.org/search?q=test&format=json&limit=1"),
)


def reachable(url, timeout=6):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "savoya-quoting-setup-check"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def check_map():
    """Pillow plus the three services. Returns (lines, actions, machine_dict)."""
    lines, actions, detail = [], [], {}
    try:
        import PIL  # noqa: F401
        detail["pillow"] = True
    except ImportError:
        detail["pillow"] = False
        lines.append("Route maps can't be drawn on this computer at all — a one-time setup is missing.")
        actions.append("This one needs IT; I can write up what to tell them.")
        return lines, actions, detail

    down = [name for name, url in MAP_SERVICES if not reachable(url)]
    detail["map_services_unreachable"] = down
    if not down:
        lines.append("Route maps work, with real streets and the driven route.")
    elif len(down) == len(MAP_SERVICES):
        lines.append("Route maps will come out as a simple diagram of the stops in order, "
                     "not a street map — this network blocks the mapping services.")
        actions.append("Worth asking IT whether those can be allowed, if street maps matter to you.")
    else:
        lines.append("Route maps will be partly degraded on this network — "
                     + " and ".join(down) + " can't be reached from here.")
        actions.append("Worth asking IT whether that can be allowed.")
    return lines, actions, detail


def main():
    cfg = load_json(CONFIG, {})
    user = cfg.get("user")

    captures = sorted(glob.glob(os.path.join(CAPTURES, "*.capture.json")))
    feedback = sorted(glob.glob(os.path.join(CAPTURES, "*.feedback.json")))
    failed = sorted(glob.glob(os.path.join(CAPTURES, "capture-failed-*.json")))
    # A capture leaves a marker that the session deletes once Drive has returned an id,
    # so this is the real number of sessions that never reached the folder. The backlog
    # used to be "every capture on this machine", which was only right while Drive had
    # never worked at all — and it is the number the Drive nudge quotes out loud.
    pending = sorted(glob.glob(os.path.join(CAPTURES, "*.pending-upload")))

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

    if pending:
        lines.append(
            f"{len(pending)} of them never reached the team folder, the oldest "
            f"{ago(min(os.path.getmtime(p) for p in pending))}. Nothing is lost — "
            f"they're still here."
        )
        actions.append("I can send those to the team folder now, if Drive is connected.")

    if failed:
        lines.append(
            f"{len(failed)} session{'s' if len(failed) != 1 else ''} failed to save "
            f"properly, the most recent {ago(max(os.path.getmtime(p) for p in failed))}."
        )
        actions.append("Worth reporting — I can summarise what went wrong.")

    map_lines, map_actions, map_detail = check_map()
    lines += map_lines
    actions += map_actions

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
        "never_uploaded": len(pending),
        "never_uploaded_oldest": (ago(min(os.path.getmtime(p) for p in pending))
                                  if pending else None),
        "map": map_detail,
        "still_to_check_by_calling_them": ["savoya_mcp", "google_drive", "folder_write"],
    }, indent=1))
    print("setup-check>>>")
    sys.exit(0)


if __name__ == "__main__":
    main()
