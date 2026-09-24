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
    ap.add_argument("--request", required=True); ap.add_argument("--quote", required=True)
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

    capture = {
        "capture_version": 1,
        "slug": name, "version": version,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "user": user, "client": a.client, "deliverable": a.deliverable,
        "request": open(a.request, encoding="utf-8").read(),
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
    fb_path = os.path.join(root, f"{name}.feedback.json")
    fb = {"feedback_version": 2, "slug": name, "ts": capture["ts"], "user": user,
          "client": a.client, "deliverable": a.deliverable,
          "trigger": capture["trigger"],
          "plugin_version": capture.get("plugin_version"),
          "request": capture["request"][:1500],
          "totals": {"engine_subtotal_cents": q.get("engine_subtotal_cents"),
                     "total_cents": q.get("total_cents"),
                     "option_b_total_cents": (q.get("option_b") or {}).get("total_cents")},
          "leg_count": len(q.get("legs", [])),
          "decisions": (load_json(os.path.join("handoff", "intake.json"), {}) or {}).get("decisions"),
          "placeholders": q.get("internal", {}).get("placeholders", []),
          "feedback": capture["feedback"],
          "full_capture": {"path": out, "bytes": size,
                           "uploaded": size <= a.max_upload_kb * 1024}}
    json.dump(fb, open(fb_path, "w", encoding="utf-8"), indent=1)

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
    print(json.dumps({
        "upload": [
            {"path": fb_path, "title": os.path.basename(fb_path), "bytes": os.path.getsize(fb_path)},
        ] + ([{"path": out, "title": os.path.basename(out), "bytes": size}] if send_full else []),
        "full_capture_kept_local": not send_full,
        "note": note,
        "drive_folder_id": asset.get("drive_folder_id"), "user": user}, indent=2))


if __name__ == "__main__":
    main()
