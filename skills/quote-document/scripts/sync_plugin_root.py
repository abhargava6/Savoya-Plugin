#!/usr/bin/env python3
"""Bring the shipped copies under assets/plugin-root/ back in line with the repo root.

Several files have two homes — see CONTRIBUTING, "Why some files exist twice". The
duplication is load-bearing: `rebuild_plugin.py` is built to run against an *installed
skill mount* with no repository present, so everything it ships has to travel inside the
skill folder. `regress.py`'s paired-docs guard already **detects** drift between the two
copies. Nothing until now **fixed** it, so the answer to a red guard was to hand-copy a
file and hope, which is the same manual step that caused the drift.

The relationships are not duplicated here: this imports `_PAIRED_DOCS` and
`_CROSS_PATH_PAIRS` from `regress.py`, so the guard and the fixer can never disagree
about which files are paired or how. A list of the duplicates kept in two places would
be the very thing this is about.

Only `same` pairs are written. A `prefix` pair is reported and left alone, deliberately:
the shipped README is the root README cut off before "Working on this repo", and where
to cut is an editorial decision, not something a script should guess. Regenerating it
mechanically would paste the build instructions back into the file a CSM is handed —
exactly what that truncation exists to prevent.

    python3 skills/quote-document/scripts/sync_plugin_root.py [--check]

`--check` reports without writing and exits 1 on drift.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, ".."))
REPO = os.path.normpath(os.path.join(SKILL, "..", ".."))
SHIPPED = os.path.join(SKILL, "assets", "plugin-root")

sys.path.insert(0, HERE)
try:
    from regress import _CROSS_PATH_PAIRS, _PAIRED_DOCS
except ImportError as ex:  # pragma: no cover - only if the guard moves
    sys.exit(f"cannot read the pair declarations from regress.py: {ex}")


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 instead of writing")
    a = ap.parse_args()

    if not os.path.isdir(SHIPPED):
        sys.exit(f"no shipped directory at {SHIPPED}")

    pairs = [(n, os.path.join(REPO, n), os.path.join(SHIPPED, n), _PAIRED_DOCS[n])
             for n in sorted(_PAIRED_DOCS)]
    pairs += [(root_rel, os.path.join(REPO, root_rel), os.path.join(SHIPPED, shipped_rel),
               "json") for root_rel, shipped_rel in _CROSS_PATH_PAIRS]

    changed, manual, missing = [], [], []
    for name, src, dst, rel in pairs:
        if not os.path.exists(src) or not os.path.exists(dst):
            missing.append(name)
            continue
        if rel == "prefix":
            if not read(src).startswith(read(dst)):
                manual.append(name)
            continue
        if rel == "json":
            # The manifest's one writer is the build. Syncing it here would make a
            # hand-edit look correct, which is the failure the guard exists to catch.
            if json.loads(read(src)) != json.loads(read(dst)):
                manual.append(name)
            continue
        if read(src) == read(dst):
            continue
        changed.append(name)
        if not a.check:
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(read(src))

    for n in missing:
        print(f"  skipped {n}: not present in both locations")
    for n in changed:
        print(f"  {'out of sync' if a.check else 'updated'}: assets/plugin-root/{n}")
    for n in manual:
        if n.endswith(".json"):
            print(f"  {n}: the two manifests disagree. Do NOT edit either by hand — "
                  f"rebuild with --bump or PLUGIN_VERSION=, which writes every copy.")
        else:
            print(f"  {n}: the shipped copy is no longer the opening section of the root "
                  f"copy. Fix this by hand — the cut point is editorial, and the text "
                  f"below it is repo-only and must not reach a CSM.")

    if a.check:
        print(f"{len(changed) + len(manual)} file(s) need attention" if (changed or manual)
              else "shipped copies are in sync")
        return 1 if (changed or manual) else 0
    if changed:
        print(f"{len(changed)} file(s) updated")
    if manual:
        print(f"{len(manual)} file(s) need a human — nothing was written for those")
    elif not changed:
        print("already in sync")
    return 1 if manual else 0


if __name__ == "__main__":
    sys.exit(main())
