#!/usr/bin/env python3
"""Capture a deliverable as a single JSON document, ready for Drive upload.

Called automatically after every rendered deliverable (PDF, email draft, HTML).
Produces <dir>/<slug>.capture.json containing everything needed to rebuild and
re-check the quote: the client's request, raw engine JSON, final quote.json,
a pre-filled expected.json, user identity, and feedback (if any yet).

The skill then uploads the file to the shared Drive folder in assets/capture.json
via the Google Drive connector (textContent, application/json). If Drive isn't
connected, the local copy in ~/.savoya-quoting/captures/ is the fallback and
export_captures.py zips it for hand-off.

Usage:
  capture_session.py --slug yerdle-boston-offsite --client Yerdle --deliverable pdf \
      --request request.md --quote quote.json [--raw raw_quote.json] [--select k1,k2] \
      [--user "Daniel Mullican"] [--worked "…"] [--change "…"] [--dir DIR]
Re-running with the same slug creates -v2, -v3 …
"""
import argparse, datetime as dt, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.expanduser("~/.savoya-quoting/config.json")
ASSET_CFG = os.path.join(HERE, "..", "assets", "capture.json")


def load_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True); ap.add_argument("--client", required=True)
    ap.add_argument("--deliverable", required=True, help="pdf | email-draft | html | docx | xlsx")
    # NOT required. The one path where a session most needs to report something is the
    # path where it improvised, and node K's documented fallback (a quote brought from
    # elsewhere) has no handoff and therefore no request.md at all. This argument being
    # mandatory meant the capture crashed with a traceback exactly then, silently, because
    # the capture step is specified as "say nothing to the user". A capture missing the
    # original request is still worth everything else it carries.
    ap.add_argument("--request", default=None)
    ap.add_argument("--quote", required=True)
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
    ap.add_argument("--max-upload-kb", type=int, default=25,
                    help="above this, the full capture stays local and only the feedback file is uploaded")
    a = ap.parse_args()

    cfg = load_json(CONFIG, {})
    asset = load_json(ASSET_CFG, {})
    user = a.user or cfg.get("user")
    if not user:
        print("WARNING: no --user and no 'user' in ~/.savoya-quoting/config.json — captures will be anonymous", file=sys.stderr)
    root = a.dir or cfg.get("capture_dir") or os.environ.get("SAVOYA_QUOTE_CAPTURE_DIR") \
        or os.path.expanduser("~/.savoya-quoting/captures")
    os.makedirs(root, exist_ok=True)

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
        "pdf_pages": 3,
    }
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
          "full_capture": {"path": out, "bytes": size,
                           "should_be_uploaded": size <= a.max_upload_kb * 1024}}
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

    too_big = size > a.max_upload_kb * 1024
    # On a render-triggered snapshot, upload only the small feedback file: one Drive call
    # per delivered document. The full capture rides along with the feedback run at the end.
    send_full = not too_big and not a.auto
    if a.auto:
        note = ("Render snapshot — upload ONLY the feedback file (one call). The full capture "
                "goes up with the feedback run once the user has answered.")
    elif too_big:
        note = (f"Full capture is {size//1024} KB (> {a.max_upload_kb} KB) — upload ONLY the feedback file. "
                f"Never split a capture across multiple uploads.")
    else:
        note = "Upload both files."
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
                   "files": [fb_path] + ([out] if send_full else [])},
                  open(marker, "w", encoding="utf-8"), indent=1)
    except OSError:
        marker = None

    print(json.dumps({
        "status": "NOTHING IS UPLOADED YET — this script only wrote the files below",
        "next_step": "Upload each file in `upload` to drive_folder_id with the Google Drive "
                     "connector, then delete `clear_when_uploaded`. The capture step is not "
                     "done until the connector has returned an id for every file.",
        "upload": [
            {"path": fb_path, "title": os.path.basename(fb_path), "bytes": os.path.getsize(fb_path)},
        ] + ([{"path": out, "title": os.path.basename(out), "bytes": size}] if send_full else []),
        "clear_when_uploaded": marker,
        "full_capture_kept_local": not send_full,
        "note": note,
        "earlier_captures_never_uploaded": len(pending),
        "drive_folder_id": asset.get("drive_folder_id"), "user": user}, indent=2))


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
    except SystemExit:
        raise
    except Exception as ex:  # noqa: BLE001 — deliberately broad; see above
        import traceback
        fallback = os.path.expanduser("~/.savoya-quoting/captures")
        try:
            os.makedirs(fallback, exist_ok=True)
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
