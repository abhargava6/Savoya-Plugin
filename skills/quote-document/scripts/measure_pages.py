#!/usr/bin/env python3
"""Measure how full each printed page actually is, and whether anything is clipped.

Why this exists. `render_print.py` paginates by *estimated* cost units, not measured
height, and `.page` is a fixed 8.5x11in box with `overflow:hidden` — so content that
does not fit is cut off rather than flowed onto the next page. Nothing downstream can
see that: `pdftotext` still extracts clipped text, so the words are all present in the
file while being invisible on the paper. A whole class of defect lived in that gap,
including three client-facing line notes that no client ever saw.

The suite could count pages but never measure them, which is how 0.23.5 shipped an
accurate route-length estimate on top of budgets calibrated for the old inaccurate one:
every page count moved, the suite went red, and the only tool available for deciding
whether the renderer or the expectation was wrong was guesswork. This is the missing
instrument. It renders the real HTML in the real browser and reports, per page, how much
of the usable box is used and whether the content runs under the footer.

    python3 measure_pages.py <quote.json> [more.json ...]

Exit code is 1 if any page overflows, so it can gate a change; the report is the point.

`regress.py --pdf` imports `measure_html()` from here and runs it over each fixture's
rendered print HTML. It deliberately does NOT re-prepare the fixtures itself: the first
version of this script did, got the route-map stub wrong, and measured a 7-page document
while the suite rendered a 9-page one. A measuring instrument with its own private idea
of the thing it measures is worse than no instrument. One preparation path, in the suite.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.normpath(os.path.join(HERE, ".."))

# Measured inside the page box: the content column starts below the top padding and
# must stop above the footer rule. Both are read from the live layout rather than
# assumed, so a CSS change to either moves this measurement with it.
#
# Only a page carrying a `.pf` footer is measured. Cover pages (`page cover`,
# `page blank`) have no footer and are laid out full-bleed on purpose — their contact
# strip runs to the paper edge, well past the content padding. Measuring them against
# a padding-derived limit reported the designed cover as "53px of clipped content",
# which is the instrument inventing a defect. A page with no footer has no content
# limit to exceed.
_JS = """() => {
  const out = [];
  document.querySelectorAll('section.page').forEach((pg, i) => {
    const foot = pg.querySelector('.pf');
    if (!foot) { out.push({page: i + 1, blank: true, available_px: 0, used_px: 0,
                           overflow_px: 0, deepest: null, text_tail: null}); return; }
    const blank = pg.classList.contains('blank') || pg.classList.contains('cover');
    const box = pg.getBoundingClientRect();
    const cs = getComputedStyle(pg);
    const top = box.top + parseFloat(cs.paddingTop);
    const limit = foot.getBoundingClientRect().top;
    let low = top, worst = null;
    pg.querySelectorAll('*').forEach(el => {
      if (el.classList.contains('pf') || el.closest('.pf')) return;
      if (!el.getClientRects().length) return;
      const r = el.getBoundingClientRect();
      if (r.height === 0 && r.width === 0) return;
      if (r.bottom > low) { low = r.bottom; worst = el; }
    });
    out.push({
      page: i + 1, blank,
      available_px: Math.round(limit - top),
      used_px: Math.round(low - top),
      overflow_px: Math.round(low - limit),
      deepest: worst ? (worst.className || worst.tagName).toString().slice(0, 40) : null,
      text_tail: worst ? (worst.textContent || '').trim().replace(/\\s+/g, ' ').slice(-70) : null,
    });
  });
  return out;
}"""


def print_html_for(quote_path, work):
    """Render the print HTML the same way the suite does."""
    out = os.path.join(work, "measure.print.html")
    pdf = os.path.join(work, "measure.pdf")
    r = subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"),
                        quote_path, pdf, "--html", out],
                       capture_output=True, text=True)
    if not os.path.exists(out):
        raise RuntimeError(f"render_print produced no HTML: {r.stderr.strip()[:300]}")
    return out


def measure_html(html_paths):
    """[(label, path_to_print_html)] -> {label: [per-page measurement, ...]}

    Takes already-rendered print HTML so that callers measure exactly the document
    they produced. See the module docstring for why that is not negotiable.
    """
    from playwright.sync_api import sync_playwright
    results = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 1400})
        for label, path in html_paths:
            pg.goto("file://" + os.path.abspath(path))
            pg.emulate_media(media="print")
            pg.wait_for_timeout(250)
            results[label] = pg.evaluate(_JS)
        b.close()
    return results


# A row's background band, a table's bottom margin and the footer's own border box do
# not line up to the pixel, so the deepest bounding rect can sit a few px below the
# footer's top while the printed page is visibly clean — checked against a raster of
# the page, not assumed. The tolerance has to stay far below one line of body text
# (8.5pt ≈ 15px): at 4px a clipped line still fails by a wide margin, which is the
# thing this measurement exists to catch. Pages inside the band are still reported.
CLIP_TOLERANCE_PX = 4


def overflows(pages):
    """The worst overflow in px across a document's real (non-cover) pages, counting
    only an overflow big enough to cut text. See CLIP_TOLERANCE_PX."""
    worst = max((p["overflow_px"] for p in pages if not p["blank"]), default=0)
    return worst if worst > CLIP_TOLERANCE_PX else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quotes", nargs="+", help="prepared quote.json file(s)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    jobs = [(os.path.basename(os.path.dirname(os.path.abspath(q))) or q, q) for q in a.quotes]

    work = tempfile.mkdtemp(prefix="measure-pages-")
    htmls, skipped = [], []
    for label, q in jobs:
        d = os.path.join(work, label)
        os.makedirs(d, exist_ok=True)
        try:
            htmls.append((label, print_html_for(q, d)))
        except Exception as ex:  # a fixture that cannot render is not this tool's problem
            skipped.append((label, str(ex)[:120]))

    results = measure_html(htmls)
    if a.json:
        print(json.dumps({"measured": results, "skipped": dict(skipped)}, indent=1))
        return 1 if any(p["overflow_px"] > 0 for ps in results.values() for p in ps) else 0

    bad = 0
    for label, pages in results.items():
        real = [p for p in pages if not p["blank"]]
        worst = overflows(pages)
        fills = [100.0 * p["used_px"] / p["available_px"] for p in real if p["available_px"]]
        print(f"\n{label}  —  {len(pages)} page(s), "
              f"fullest {max(fills, default=0):.0f}% of the usable box"
              + (f"   *** {worst}px OVERFLOW ***" if worst > 0 else ""))
        for p in pages:
            if p["blank"]:
                print(f"   p{p['page']}: cover")
                continue
            fill = 100.0 * p["used_px"] / p["available_px"] if p["available_px"] else 0
            if p["overflow_px"] > CLIP_TOLERANCE_PX:
                flag = f"  <-- clipped by {p['overflow_px']}px"
            elif p["overflow_px"] > 0:
                flag = f"  (tight: {p['overflow_px']}px into the footer band)"
            else:
                flag = ""
            print(f"   p{p['page']}: {p['used_px']:>4}/{p['available_px']}px  {fill:5.1f}%{flag}")
            if p["overflow_px"] > CLIP_TOLERANCE_PX and p["text_tail"]:
                print(f"         last thing on the page: …{p['text_tail']}")
        bad += 1 if worst > 0 else 0
    for label, why in skipped:
        print(f"\n{label}  —  skipped: {why}")
    print(f"\n{len(results)} measured, {bad} with clipped content")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
