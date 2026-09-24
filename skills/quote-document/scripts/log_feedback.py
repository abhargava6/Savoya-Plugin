#!/usr/bin/env python3
"""Append a session feedback entry to the shared JSONL log.

Usage:
  log_feedback.py --format html --client "Yerdle" --worked "…" --change "…" [--skipped]

Path: $SAVOYA_QUOTE_FEEDBACK_PATH or ~/.savoya-quoting/feedback.jsonl
"""
import argparse, datetime as dt, json, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", default=None, help="html|docx|pdf|xlsx")
    ap.add_argument("--client", default=None)
    ap.add_argument("--worked", default=None, help="What worked / what needed hand-fixing")
    ap.add_argument("--change", default=None, help="What the document should do differently")
    ap.add_argument("--skipped", action="store_true", help="User declined to answer")
    ap.add_argument("--note", default=None, help="Anything else (free text)")
    args = ap.parse_args()

    path = os.environ.get("SAVOYA_QUOTE_FEEDBACK_PATH") or os.path.expanduser("~/.savoya-quoting/feedback.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "skill": "quote-document",
        "format": args.format,
        "client": args.client,
        "skipped": args.skipped,
        "worked": args.worked,
        "change": args.change,
        "note": args.note,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Logged feedback to {path}")

if __name__ == "__main__":
    main()
