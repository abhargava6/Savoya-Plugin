#!/usr/bin/env python3
"""Capture a deliverable as a single JSON document, ready for Drive upload.

Called automatically after every rendered deliverable (PDF, email draft, HTML).
Produces <dir>/<slug>.capture.json containing everything needed to rebuild and
re-check the quote: the client's request, raw engine JSON, final quote.json,
a pre-filled expected.json, user identity, and feedback (if any yet).

The skill then uploads the files to the shared Drive folder in assets/capture.json
via the Google Drive connector (textContent, application/json).

The full capture is ALWAYS compressed and ALWAYS uploadable. It used to stay local
above 25 KB, which meant the richest sessions were precisely the ones that never
arrived: a 16-leg World Cup quote capture was 192 KB and was lost with its container,
along with a 36 KB London one, on 10 Oct 2026. Measured on those same files, gzip gives
15x and base64 for Drive's textContent still leaves 17 KB, so there is no size at which
a real quote cannot be sent and the threshold is gone.

`~` is not the user's computer. On claude.ai the home directory is a cloud container
reclaimed when the session ends, and on a linked desktop the shell's `~` is an isolated
VM -- only a connected folder is really the user's disk. So the output states whether
the local copy is durable and the skill is told to pass --dir inside a connected folder
when the session has one. Nothing here can see Drive; see `--mark-uploaded`.

Usage:
  capture_session.py --slug yerdle-boston-offsite --client Yerdle --deliverable pdf \
      --request request.md --quote quote.json [--raw raw_quote.json] [--select k1,k2] \
      [--user "Daniel Mullican"] [--worked "…"] [--change "…"] [--dir DIR] [--pdf out.pdf]
  capture_session.py --mark-uploaded <slug> --file-id <id> [--file-id <id>] [--dir DIR]
Re-running with the same slug creates -v2, -v3 …
"""
import argparse, base64, datetime as dt, glob, gzip, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.expanduser("~/.savoya-quoting/config.json")
ASSET_CFG = os.path.join(HERE, "..", "assets", "capture.json")


def load_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


# Paths whose contents do not survive the session. `~` under any of these is a
# container or an isolated VM, never the user's own disk.
_EPHEMERAL_PREFIXES = ("/home/claude", "/sessions/", "/root", "/tmp", "/var/folders")


def durability_of(path):
    """Is a capture written here still here tomorrow?

    Not a detail. Two real captures -- 192 KB and 36 KB -- were written to
    `~/.savoya-quoting/captures/` on 10 Oct 2026, reported as saved, and lost when the
    container was reclaimed, because `~` was the container. The same trap sits one level
    down on a linked desktop, where the shell's home is an isolated VM and only a
    connected folder is the user's disk.
    """
    real = os.path.realpath(path)
    for pre in _EPHEMERAL_PREFIXES:
        if real == pre.rstrip("/") or real.startswith(pre if pre.endswith("/") else pre + "/"):
            return False, (f"{real} is inside {pre}, which is this session's own "
                           f"storage and goes away with it")
    return True, None


def count_pdf_pages(path):
    """Pages in the delivered PDF, measured.

    `expected.pdf_pages` was the literal 3 for every capture ever taken. The three real
    deliverables on 10 Oct 2026 were 4, 5 and 8 pages, and the fixtures in this repo
    legitimately run from 3 to 9. So promoting a captured session to a fixture started
    red on a number nobody had measured, which invites correcting the expectation to
    match whatever came out -- the exact habit the sixteen-leg fixture note warns
    against. Unmeasurable means absent, never a guess.
    """
    if not path or not os.path.exists(path):
        return None
    if shutil.which("pdfinfo"):
        try:
            out = subprocess.run(["pdfinfo", path], capture_output=True, text=True,
                                 timeout=20)
            m = re.search(r"^Pages:\s+(\d+)", out.stdout, re.M)
            if m:
                return int(m.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
    try:  # no pdfinfo: count page objects, good enough for our own renderer's output
        with open(path, "rb") as fh:
            blob = fh.read()
        n = blob.count(b"/Type /Page") - blob.count(b"/Type /Pages")
        return n if n > 0 else None
    except OSError:
        return None


# Named capture_root, not resolve_*: that prefix belongs to the MCP tool
# namespace (resolve_client, resolve_service_areas, ...) and the tool-contract
# guard rightly flags anything there that is not in mcp-contract.md.
def capture_root(a, cfg):
    return (a.dir or cfg.get("capture_dir") or os.environ.get("SAVOYA_QUOTE_CAPTURE_DIR")
            or os.path.expanduser("~/.savoya-quoting/captures"))


def mark_uploaded(a):
    """Record that Drive has the files, without needing `rm`.

    The marker is what makes a skipped upload visible to the next session instead of
    vanishing with this one, and clearing it was a shell delete -- which the auto-mode
    classifier denies. So on 10 Oct 2026 a capture that HAD been uploaded still counted
    as outstanding, and the nudge shown to the user ("that's 4 sessions now that haven't
    reached the team folder") stated a number that was not true.

    A Drive id is required, so this cannot be used to make the backlog look clean
    without an upload behind it.
    """
    cfg = load_json(CONFIG, {})
    root = capture_root(a, cfg)
    slug = re.sub(r"[^a-z0-9-]+", "-", a.mark_uploaded.lower()).strip("-")
    if not a.file_ids:
        sys.exit("--mark-uploaded needs at least one --file-id from Drive's create_file "
                 "result. The marker is the only record that an upload is outstanding; "
                 "clearing it without an id would hide a capture that never arrived.")
    cleared, receipts = [], os.path.join(root, f"{slug}.uploaded.json")
    for marker in (os.path.join(root, f"{slug}.pending-upload"),
                   os.path.join(root, f"{slug}.snapshot.pending-upload")):
        if os.path.exists(marker):
            try:
                os.remove(marker)
                cleared.append(os.path.basename(marker))
            except OSError as ex:
                print(f"WARNING: could not clear {marker}: {ex}", file=sys.stderr)
    try:
        prior = load_json(receipts, {}) or {}
        ids = sorted(set((prior.get("drive_file_ids") or []) + list(a.file_ids)))
        json.dump({"slug": slug, "drive_file_ids": ids,
                   "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
                  open(receipts, "w", encoding="utf-8"), indent=1)
    except OSError as ex:
        print(f"WARNING: could not write the upload receipt: {ex}", file=sys.stderr)
    still = len(glob.glob(os.path.join(root, "*.pending-upload")))
    print(json.dumps({"status": "recorded as uploaded", "slug": slug,
                      "drive_file_ids": list(a.file_ids),
                      "markers_cleared": cleared,
                      "captures_still_never_uploaded": still}, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None); ap.add_argument("--client", default=None)
    ap.add_argument("--deliverable", default=None, help="pdf | email-draft | html | docx | xlsx")
    # NOT required. The one path where a session most needs to report something is the
    # path where it improvised, and node K's documented fallback (a quote brought from
    # elsewhere) has no handoff and therefore no request.md at all. This argument being
    # mandatory meant the capture crashed with a traceback exactly then, silently, because
    # the capture step is specified as "say nothing to the user". A capture missing the
    # original request is still worth everything else it carries.
    ap.add_argument("--request", default=None)
    ap.add_argument("--quote", default=None)
    ap.add_argument("--raw", default=None); ap.add_argument("--select", default=None)
    ap.add_argument("--user", default=None)
    ap.add_argument("--worked", default=None); ap.add_argument("--change", default=None)
    ap.add_argument("--fixed", default=None, help="what you changed in-session in response to --change")
    ap.add_argument("--workaround", default=None,
                    help="YOUR OWN note about anything outside the documented path. Never put this in "
                         "--change: that field is the user's words, and mixing the two makes it "
                         "impossible to tell a CSM request from a defect Claude patched itself.")
    ap.add_argument("--skipped", action="store_true", help="user declined to answer the feedback question")
    ap.add_argument("--auto", action="store_true",
                    help="render-triggered snapshot: a document was delivered and no feedback exists yet. "
                         "Written and uploaded straight after delivery so a session that ends there is "
                         "still recorded.")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--new-version", action="store_true",
                    help="keep the previous capture and write a new numbered one (rare; default is overwrite)")
    ap.add_argument("--pdf", default=None,
                    help="the delivered PDF, so expected.pdf_pages is MEASURED. Omitted "
                         "when absent; never guessed.")
    ap.add_argument("--mark-uploaded", dest="mark_uploaded", default=None, metavar="SLUG",
                    help="clear the pending-upload marker for SLUG after Drive has "
                         "returned an id for every file. Requires --file-id. This exists "
                         "because clearing it meant `rm`, which the auto-mode classifier "
                         "denies -- so an upload that DID succeed still looked outstanding "
                         "to the next session and the backlog count lied to the user.")
    ap.add_argument("--file-id", dest="file_ids", action="append", default=[],
                    help="a Drive file id returned by create_file. Repeatable. Required "
                         "with --mark-uploaded: without it a session could clear the "
                         "marker without having uploaded anything.")
    a = ap.parse_args()

    if a.mark_uploaded:
        return mark_uploaded(a)

    for name in ("slug", "client", "deliverable", "quote"):
        if not getattr(a, name):
            sys.exit(f"--{name} is required (only --mark-uploaded may be used without it)")
    cfg = load_json(CONFIG, {})
    asset = load_json(ASSET_CFG, {})
    user = a.user or cfg.get("user")
    if not user:
        print("WARNING: no --user and no 'user' in ~/.savoya-quoting/config.json — captures will be anonymous", file=sys.stderr)
    root = capture_root(a, cfg)
    os.makedirs(root, exist_ok=True)
    durable, why_not = durability_of(root)

    slug = re.sub(r"[^a-z0-9-]+", "-", a.slug.lower()).strip("-")
    # P2: one capture per conversation — overwrite the same slug rather than versioning.
    # Pass --new-version only when the user explicitly wants a second record.
    existing = sorted(glob.glob(os.path.join(root, f"{slug}*.capture.json")))
    if a.new_version and existing:
        version = len(existing) + 1
        name = f"{slug}-v{version}"
    else:
        version = 1
        name = slug
    out = os.path.join(root, f"{name}.capture.json")

    q = load_json(a.quote, None)
    if q is None:
        sys.exit(f"Cannot read quote.json at {a.quote}")

    def slim_raw(raw):
        """Keep only what regress.py needs to rebuild the quote: per unit, stops,
        the chosen option, warnings, dates. Drops vehicle_options/elevated_option
        (duplicates of value_option) and the presentation block. ~3x smaller."""
        if not raw:
            return None
        out = {k: v for k, v in raw.items() if k not in ("presentation", "quote_units")}
        out["quote_units"] = []
        for u in raw.get("quote_units", []):
            su = {k: v for k, v in u.items() if k not in ("vehicle_options", "elevated_option")}
            opt = su.get("value_option")
            if opt:
                su["value_option"] = {k: v for k, v in opt.items() if k != "warnings"}
                su["vehicle_options"] = [su["value_option"]]
            out["quote_units"].append(su)
        return out
    expected = {
        "normalize": ({"client": a.client, "prepared_by": q["meta"].get("prepared_by"),
                       "select": a.select, "title": q["meta"].get("title")} if a.raw else None),
        "edits": {"personalization": {"cover": (q.get("personalization") or {}).get("cover", "general")}},
        "adjustments": [f"{x['label']}|{x['type']}|{x['value']:g}" + (f"|{x['applies_to']}" if x.get("applies_to") else "")
                        for x in q.get("adjustments", [])],
        "engine_subtotal_cents": q.get("engine_subtotal_cents"),
        "total_cents": q.get("total_cents"),
        "leg_count": len(q.get("legs", [])),
        "contains": [f"${q.get('total_cents', 0)/100:,.2f}", "This is a quoting tool"],
        "not_contains": ["Stop 2", "hourly fallback", "rate_id"],
    }
    pages = count_pdf_pages(a.pdf)
    if pages:
        expected["pdf_pages"] = pages
    if expected["normalize"] is None:
        expected.pop("normalize")

    request_text, request_missing = None, None
    if not a.request:
        request_missing = "no --request given (document flow entered without a handoff)"
    else:
        try:
            with open(a.request, encoding="utf-8") as fh:
                request_text = fh.read()
        except OSError as ex:
            request_missing = f"{a.request}: {ex.strerror}"

    capture = {
        "capture_version": 2,
        "slug": name, "version": version,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "user": user, "client": a.client, "deliverable": a.deliverable,
        "request": request_text,
        "request_missing": request_missing,
        "raw_quote": slim_raw(load_json(a.raw, None)) if a.raw else None,
        "quote": q,
        "expected": expected,
        "trigger": "render" if a.auto else "feedback",
        "feedback": {"worked": a.worked,
                     # the user's words only — Claude's own notes go in `workaround`
                     "change": a.change,
                     "fixed": a.fixed,
                     "workaround": a.workaround,
                     "resolved_in_session": bool(a.fixed),
                     "asked": not a.auto,
                     "answered": bool(a.worked or a.change),
                     "declined": bool(a.skipped)},
        "placeholders": q.get("internal", {}).get("placeholders", []),
        "intake": {k: v for k, v in (load_json("handoff/intake.json", {}) or {}).items() if k != "log"} or None,
        "plugin_version": load_json(os.path.join(HERE, "..", "..", "..", ".claude-plugin", "plugin.json"), {}).get("version"),
    }
    json.dump(capture, open(out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    size = os.path.getsize(out)

    # The full capture is compressed, and therefore always sendable. The old rule kept
    # it local above 25 KB, which lost the two biggest captures of 10 Oct 2026 (192 KB
    # and 36 KB) along with the container they sat in -- the richest sessions being
    # exactly the ones that never arrived. Measured on those files gzip gives 15x and
    # base64 for Drive's textContent still leaves 17 KB, so there is no realistic quote
    # whose capture cannot be uploaded in one call, and no threshold left to strand it.
    #
    # The envelope is JSON so Drive takes it as text and so the weekly pass can read the
    # header without decompressing. `unpack_capture.py` reverses it. The small feedback
    # file stays plain, readable JSON, because that is the one a person skims.
    raw_bytes = open(out, "rb").read()
    packed = {
        "capture_version": 2,
        "encoding": "gzip+base64",
        "slug": name,
        "ts": capture["ts"],
        "user": user,
        "client": a.client,
        "plugin_version": capture.get("plugin_version"),
        "raw_bytes": len(raw_bytes),
        "data": base64.b64encode(gzip.compress(raw_bytes, 9)).decode("ascii"),
    }
    packed_path = os.path.join(root, f"{name}.capture.json.gz.b64")
    try:
        json.dump(packed, open(packed_path, "w", encoding="utf-8"), separators=(",", ":"))
        packed_size = os.path.getsize(packed_path)
    except OSError as ex:
        print(f"WARNING: could not write the compressed capture: {ex}", file=sys.stderr)
        packed_path, packed_size = None, 0


    # P1 + P6: a small feedback file is always written and is always what gets uploaded first.
    #
    # The render snapshot and the post-feedback run are two different records, and they
    # must not share a filename. Drive's create_file always creates, so uploading the
    # same title twice does not replace anything — it leaves two files with one name,
    # and the documented flow runs both steps on *every* quote, so this was not an
    # occasional collision but the normal outcome. Separate titles also turn the
    # duplicate into signal: a folder holding only a snapshot for some slug is a
    # session that delivered a document and never came back for the feedback.
    fb_path = os.path.join(root, f"{name}.feedback.snapshot.json" if a.auto
                           else f"{name}.feedback.json")
    fb = {"feedback_version": 2, "slug": name, "ts": capture["ts"], "user": user,
          "client": a.client, "deliverable": a.deliverable,
          "trigger": capture["trigger"],
          "plugin_version": capture.get("plugin_version"),
          "request": (capture["request"] or "")[:1500] or None,
          "request_missing": capture["request_missing"],
          "totals": {"engine_subtotal_cents": q.get("engine_subtotal_cents"),
                     "total_cents": q.get("total_cents"),
                     "option_b_total_cents": (q.get("option_b") or {}).get("total_cents")},
          "leg_count": len(q.get("legs", [])),
          "decisions": (load_json(os.path.join("handoff", "intake.json"), {}) or {}).get("decisions"),
          "placeholders": q.get("internal", {}).get("placeholders", []),
          "feedback": capture["feedback"],
          # Deliberately NOT called "uploaded": this file is written before any upload
          # happens, so that name recorded an intention as a fact. The weekly pass read
          # `uploaded: true` in the Drive copy and took the full capture to be in the
          # folder; nothing here can know whether the session ever made the call.
          # `should_be_uploaded` is now always true: the capture is compressed, so there
          # is no size at which it stays behind. It used to be a 25 KB test, and the two
          # largest captures of 10 Oct 2026 failed it and were lost with their container.
          "full_capture": {"path": out, "bytes": size,
                           "compressed": packed_path, "compressed_bytes": packed_size,
                           "should_be_uploaded": bool(packed_path)},
          "local_copy_durable": durable}
    json.dump(fb, open(fb_path, "w", encoding="utf-8"), indent=1)

    # The richer record supersedes the snapshot, so the local snapshot and any upload
    # still outstanding for it go away. The Drive copy stays — nothing here can delete
    # it — but the weekly pass prefers `<slug>.feedback.json` over
    # `<slug>.feedback.snapshot.json`, so it is read as superseded rather than as a
    # second opinion.
    if not a.auto:
        for stale in (os.path.join(root, f"{name}.feedback.snapshot.json"),
                      os.path.join(root, f"{name}.snapshot.pending-upload")):
            try:
                os.remove(stale)
            except OSError:
                pass

    # On a render-triggered snapshot, upload only the small feedback file: one Drive call
    # per delivered document. The full capture rides along with the feedback run at the end.
    send_full = bool(packed_path) and not a.auto
    if a.auto:
        note = ("Render snapshot — upload ONLY the feedback file (one call). The full capture "
                "goes up with the feedback run once the user has answered.")
    elif not packed_path:
        note = ("The compressed capture could not be written — upload the feedback file and "
                "say so. Never split a capture across multiple uploads.")
    else:
        note = (f"Upload both files. The capture is {packed_size // 1024 or 1} KB compressed "
                f"({size // 1024 or 1} KB raw), so one call carries all of it.")
    # This script writes files. It has no Drive access and never uploads anything.
    # That was not obvious enough: a session ran the capture, read this block as a
    # completion summary and stopped — "I treated the local save as the end of the
    # step" — so the one channel back from a live quote went quiet again, and it was
    # noticed only because Ayush asked why nothing was in the folder. The status comes
    # first and says what has NOT happened, and a marker is left on disk so that a
    # skipped upload is still discoverable afterwards instead of vanishing with the
    # session.
    # Named off fb_path so the snapshot run and the final run keep separate markers,
    # the same way they keep separate titles.
    marker = os.path.join(root, ("%s.snapshot.pending-upload" % name) if a.auto
                          else ("%s.pending-upload" % name))
    pending = [p for p in glob.glob(os.path.join(root, "*.pending-upload"))
               if os.path.abspath(p) != os.path.abspath(marker)]
    try:
        json.dump({"ts": capture["ts"], "slug": name, "user": user,
                   "files": [fb_path] + ([packed_path] if send_full else []),
                   "clear_with": f"capture_session.py --mark-uploaded {name} --file-id <id>"},
                  open(marker, "w", encoding="utf-8"), indent=1)
    except OSError:
        marker = None

    print(json.dumps({
        "status": "NOTHING IS UPLOADED YET — this script only wrote the files below",
        "next_step": "Upload each file in `upload` to drive_folder_id with the Google Drive "
                     "connector, then run `capture_session.py --mark-uploaded " + name +
                     " --file-id <id>` with the ids it returned. The capture step is not "
                     "done until the connector has returned an id for every file.",
        "upload": [
            {"path": fb_path, "title": os.path.basename(fb_path), "bytes": os.path.getsize(fb_path)},
        ] + ([{"path": packed_path, "title": os.path.basename(packed_path),
               "bytes": packed_size}] if send_full else []),
        "clear_when_uploaded": marker,
        "clear_with": f"capture_session.py --mark-uploaded {name} --file-id <id>",
        # Where the local copy lives and whether it will still be there tomorrow. `~` is
        # the session's own storage on claude.ai and an isolated VM on a linked desktop;
        # two real captures were reported saved and then lost with their container.
        "local_copy": {"dir": root, "durable": durable, "why_not": why_not,
                       "full_capture": out, "compressed": packed_path},
        "note": note,
        "pdf_pages_measured": expected.get("pdf_pages"),
        "earlier_captures_never_uploaded": len(pending),
        "drive_folder_id": asset.get("drive_folder_id"), "user": user}, indent=2))
    if not durable:
        print(f"CAPTURE IS NOT ON DURABLE STORAGE: {why_not}.\n"
              f"  Upload it this session, or re-run with --dir inside a folder connected "
              f"to the user's computer. A capture that is only in this session's home "
              f"directory is a bug report that disappears with the session.",
              file=sys.stderr)


if __name__ == "__main__":
    # The capture is the ONLY channel from a live session back to whoever maintains this
    # plugin, and the instruction that runs it says to say nothing to the user. So a
    # traceback here is not an error anybody sees — it is a bug report that silently never
    # happened. Two real defects reached a client PDF and were diagnosed only because the
    # CSM happened to paste them into a chat days later.
    #
    # Nothing below is allowed to make the capture the reason a session gives up: on an
    # unexpected failure, write down what went wrong where the weekly pass will find it,
    # tell the session plainly, and exit 0. An argparse failure (SystemExit) still exits
    # as argparse intends, so a genuinely malformed call is still visible.
    try:
        main()
    except SystemExit as ex:
        # argparse and the explicit sys.exit()s above are deliberate, and they still end
        # the process as intended. But on 10 Oct 2026 a capture was called with --dir and
        # no --slug; argparse printed usage to stderr, nobody read it, and the session
        # recorded nothing at all -- "the first capture call used wrong args and failed
        # silently". The instruction that runs this step says to say nothing to the user,
        # so a usage error is a bug report that never happened. It now leaves the same
        # discoverable record an unexpected failure would, and then exits as before.
        code = ex.code if isinstance(ex.code, int) else (0 if ex.code is None else 1)
        if code:
            try:
                fb = os.path.expanduser("~/.savoya-quoting/captures")
                os.makedirs(fb, exist_ok=True)
                # microseconds, not seconds: two refused calls in one second used to
                # collide on the filename and one record silently replaced the other.
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                with open(os.path.join(fb, f"capture-refused-{stamp}.json"), "w",
                          encoding="utf-8") as fh:
                    json.dump({"capture_version": 2, "ts": stamp, "failed": True,
                               "error": f"bad arguments: {ex.code}",
                               "argv": sys.argv[1:]}, fh, indent=1)
            except Exception:  # noqa: BLE001 — a failure here must not mask the real one
                pass
        raise
    except Exception as ex:  # noqa: BLE001 — deliberately broad; see above
        import traceback
        fallback = os.path.expanduser("~/.savoya-quoting/captures")
        try:
            os.makedirs(fallback, exist_ok=True)
            # microseconds, not seconds: two failures in one second used to collide
            # on the filename and one record silently replaced the other.
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            path = os.path.join(fallback, f"capture-failed-{stamp}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"capture_version": 2, "ts": stamp, "failed": True,
                           "error": f"{type(ex).__name__}: {ex}",
                           "argv": sys.argv[1:],
                           "traceback": traceback.format_exc()[-4000:]}, fh, indent=1)
            print(f"CAPTURE DEGRADED: {type(ex).__name__}: {ex}\n"
                  f"  A failure record was written to {path}.\n"
                  f"  Upload it with the other captures — a capture that fails is a bug "
                  f"report that never arrives.", file=sys.stderr)
        except Exception:
            print(f"CAPTURE FAILED and could not be recorded: {type(ex).__name__}: {ex}",
                  file=sys.stderr)
        sys.exit(0)
