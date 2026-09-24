#!/usr/bin/env python3
"""Check what this machine can actually produce. Run once per conversation, before the first render.

Exit 0 = everything available · 1 = degraded (some formats unavailable) · never fails hard.
Prints a plain-language report plus the exact install commands for anything missing.
"""
import importlib.util
import platform
import shutil
import sys

from preflight_helpers import (MAC, WIN, PY_CMD, PIP_CMD, os_label, cmd_pdf_engine,
                                cmd_poppler, cmd_pillow, print_to_pdf_hint, shell_name)
import sys as _s, os as _o
_s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))

def has_mod(m):
    try:
        return importlib.util.find_spec(m) is not None
    except (ImportError, ValueError):
        return False

def chromium_ready():
    if not has_mod("playwright"):
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); b.close()
        return True
    except Exception:
        return False

ADMIN = "--admin" in _s.argv

checks = {
    "PDF engine (Chromium)": chromium_ready(),
    "PDF engine (wkhtmltopdf fallback)": bool(shutil.which("wkhtmltopdf")),
    "PDF text tools (poppler)": all(shutil.which(b) for b in ("pdftotext", "pdfinfo")),
    "Image tools (Pillow)": has_mod("PIL"),
    "PDF page tools (pdftoppm)": bool(shutil.which("pdftoppm")),
}
pdf_ok = checks["PDF engine (Chromium)"] or checks["PDF engine (wkhtmltopdf fallback)"]

print(f"Machine check — {os_label()}:")
for k, v in checks.items():
    print(f"  {'✓' if v else '✗'} {k}")

print("\nWhat you can produce right now:")
print(f"  {'✓' if True else '✗'} Quote in chat, email copy, HTML document  (no dependencies)")
print(f"  {'✓' if pdf_ok else '✗'} PDF proposal" + ("" if pdf_ok else f"  — HTML is produced instead; {print_to_pdf_hint()}"))
print(f"  {'✓' if checks['PDF text tools (poppler)'] else '✗'} Full document verification" + ("" if checks["PDF text tools (poppler)"] else "  — only structural checks run; text checks are skipped"))
print(f"  {'✓' if checks['Image tools (Pillow)'] else '✗'} Route map" + ("" if checks["Image tools (Pillow)"] else "  — skipped"))
import json as _json
_cfg_path = _o.path.expanduser("~/.savoya-quoting/config.json")
try:
    _cfg = _json.load(open(_cfg_path, encoding="utf-8"))
except Exception:
    _cfg = {}
_named = bool(_cfg.get("user"))
print(f"  {'✓' if _named else '✗'} Session logging identity" + ("" if _named else "  — Claude will ask your name once, then remember it"))
print(f"  {'✓' if checks['Image tools (Pillow)'] and checks['PDF page tools (pdftoppm)'] else '✗'} Uploaded custom cover from a PDF" + ("" if checks["Image tools (Pillow)"] and checks["PDF page tools (pdftoppm)"] else "  — an image file still works"))

missing = []
if not pdf_ok:
    missing.append(("PDF output", cmd_pdf_engine()))
if not checks["PDF text tools (poppler)"] or not checks["PDF page tools (pdftoppm)"]:
    missing.append(("Full verification and PDF covers", cmd_poppler()))
if not checks["Image tools (Pillow)"]:
    missing.append(("Route maps", cmd_pillow()))

if missing and ADMIN:
    print(f"\n[admin] One-time setup — paste into {shell_name()}:")
    for what, c in missing:
        print(f"  # {what}\n  {c}")
elif missing:
    print("\nNothing is broken. Everything above marked ✗ needs a one-time setup on this computer,")
    print("which IT or whoever set up Claude for you can do in a couple of minutes.")
    if not pdf_ok:
        print(f"\nIn the meantime you still get the full document as a web page:")
        print(f"  {print_to_pdf_hint()} — it produces the same document.")
sys.exit(0 if (pdf_ok and all(checks[k] for k in ("PDF text tools (poppler)", "Image tools (Pillow)"))) else 1)
