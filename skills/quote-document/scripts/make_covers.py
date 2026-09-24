#!/usr/bin/env python3
"""Pre-render marketing cover PDFs to JPEGs the print renderer embeds directly.
Run once when a cover is added or changed — never at quote time (it costs ~20s per cover).

Usage: make_covers.py <covers-src-dir> [--out assets/covers] [--dpi 170] [--quality 84]
Reads <key>.pdf files, writes <key>.jpg next to catalog.json, and sets each catalog entry's
"file" to the jpg. Requires pdftoppm (poppler) and Pillow.
"""
import argparse, json, os, subprocess, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("--out", default=os.path.join(HERE, "..", "assets", "covers"))
ap.add_argument("--dpi", type=int, default=170); ap.add_argument("--quality", type=int, default=84)
a = ap.parse_args()
cat_path = os.path.join(a.out, "catalog.json"); cat = json.load(open(cat_path))
for c in cat["covers"]:
    if not c.get("file") and c["key"] != "custom" or c["key"] == "custom":
        continue
    pdf = os.path.join(a.src, f"{c['key']}.pdf")
    if not os.path.exists(pdf):
        print(f"  skip {c['key']}: no {pdf}"); continue
    stem = os.path.join(a.out, c["key"])
    subprocess.run(["pdftoppm", "-r", str(a.dpi), "-png", "-singlefile", pdf, stem], check=True)
    Image.open(stem + ".png").convert("RGB").save(stem + ".jpg", "JPEG", quality=a.quality, optimize=True)
    os.remove(stem + ".png"); c["file"] = f"{c['key']}.jpg"
    print(f"  {c['key']}.jpg  {os.path.getsize(stem + '.jpg')//1024} KB")
json.dump(cat, open(cat_path, "w"), indent=2)
print("catalog updated")
