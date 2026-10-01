#!/usr/bin/env python3
"""Regression runner for quote-document fixtures.

Walks evals/fixtures/*/ (or a capture dir), rebuilds each quote through the
real scripts, and checks expected.json. Deterministic — run before every
repackage. Exit code 1 on any failure.

Usage:
  regress.py                 # all fixtures, HTML + print HTML checks
  regress.py --pdf           # also render PDFs and check page counts (slower)
  regress.py --only boston-offsite
  regress.py --fixtures ~/.savoya-quoting/captures   # run against captured sessions

Fixture layout:
  <slug>/request.md        the client's request (for humans)
  <slug>/raw_quote.json    engine output  (normalize runs)   -- or --
  <slug>/quote.json        already-normalized (normalize skipped)
  <slug>/expected.json     see README in evals/

expected.json keys (all optional):
  normalize: {client, prepared_by, title}
  edits: {meta: {...}, personalization: {cover: "event-planners", ...}, legs: {<key>: {label, client_notes, stops: {"<index>": {label}}}}}
  engine_subtotal_cents, total_cents, leg_count
  contains / not_contains: strings checked against HTML + print HTML (+ PDF text with --pdf)
  pdf_pages: int (only with --pdf)
"""

import argparse
import glob
import sys as _sys

_sys.dont_write_bytecode = True
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DEFAULT_FIXTURES = os.path.join(SKILL, "evals", "fixtures-v23")


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def apply_edits(q, edits):
    for k, v in (edits.get("meta") or {}).items():
        q["meta"][k] = v
    for k, v in (edits.get("personalization") or {}).items():
        q.setdefault("personalization", {})[k] = v
    for key, e in (edits.get("legs") or {}).items():
        leg = next((l for l in q["legs"] if l["key"] == key), None)
        if not leg:
            raise ValueError(f"edit targets unknown leg {key}")
        for k, v in e.items():
            if k == "stops":
                for idx, sv in v.items():
                    leg["stops"][int(idx)].update(sv)
                    leg["stops"][int(idx)].pop("needs_label", None)
            else:
                leg[k] = v
    return q


def check_fixture(fx, want_pdf):
    name = os.path.basename(fx.rstrip("/"))
    exp_path = os.path.join(fx, "expected.json")
    if not os.path.exists(exp_path):
        return (
            name,
            None,
            ["no expected.json (capture only — add assertions to promote)"],
        )
    exp = json.load(open(exp_path, encoding="utf-8"))
    fails, work = [], tempfile.mkdtemp(prefix=f"regress-{name}-")
    try:
        qpath = os.path.join(work, "quote.json")
        if exp.get("handoff") and os.path.isdir(os.path.join(fx, "handoff")):
            n = exp.get("normalize", {})
            cmd = [
                sys.executable,
                os.path.join(HERE, "normalize_quote.py"),
                "--from-handoff",
                os.path.join(fx, "handoff"),
                qpath,
            ]
            if n.get("prepared_by"):
                cmd += ["--prepared-by", n["prepared_by"]]
            if n.get("title"):
                cmd += ["--title", n["title"]]
            rc, out = run(cmd, work)
            if rc:
                return name, False, [f"normalize --from-handoff failed:\n{out}"]
        elif os.path.exists(os.path.join(fx, "raw_quote.json")):
            n = exp.get("normalize", {})
            cmd = [
                sys.executable,
                os.path.join(HERE, "normalize_quote.py"),
                os.path.join(fx, "raw_quote.json"),
                qpath,
                "--client",
                n.get("client", "Client"),
            ]
            if n.get("prepared_by"):
                cmd += ["--prepared-by", n["prepared_by"]]
            if n.get("select"):
                cmd += ["--select", n["select"]]
            if n.get("title"):
                cmd += ["--title", n["title"]]
            for alt in n.get("alternative", []):
                cmd += ["--alternative", alt]
            rc, out = run(cmd, work)
            if rc:
                return name, False, [f"normalize failed:\n{out}"]
        elif os.path.exists(os.path.join(fx, "quote.json")):
            shutil.copy(os.path.join(fx, "quote.json"), qpath)
        else:
            return name, False, ["no raw_quote.json or quote.json"]

        q_ = json.load(open(qpath, encoding="utf-8"))
        if (q_.get("route_map") or {}).get("png") == "ROUTE_MAP_PNG":
            stub = os.path.join(work, "map.png")
            try:
                from PIL import Image, ImageDraw

                # Deliberately NOT a flat fill: a uniform image is exactly what a failed
                # tile fetch produces, so a flat stub made the blank-map bug invisible here.
                im = Image.new("RGB", (1100, 620), (235, 232, 228))
                d = ImageDraw.Draw(im)
                for i in range(0, 1100, 40):
                    d.line([(i, 0), (i - 200, 620)], fill=(206, 214, 200), width=9)
                for j in range(0, 620, 55):
                    d.line([(0, j), (1100, j + 40)], fill=(222, 216, 206), width=7)
                d.line(
                    [(90, 540), (400, 300), (760, 360), (1010, 120)],
                    fill=(184, 115, 51),
                    width=6,
                )
                im.save(stub)
                q_["route_map"]["png"] = stub
            except ImportError:
                q_.pop("route_map", None)
            json.dump(q_, open(qpath, "w", encoding="utf-8"), indent=2)
        if exp.get("edits"):
            q = json.load(open(qpath, encoding="utf-8"))
            q = apply_edits(q, exp["edits"])
            json.dump(q, open(qpath, "w", encoding="utf-8"), indent=2)

        q = json.load(open(qpath, encoding="utf-8"))
        for k in ("engine_subtotal_cents", "total_cents"):
            if k in exp and q.get(k) != exp[k]:
                fails.append(f"{k}: expected {exp[k]} got {q.get(k)}")
        if "leg_count" in exp and len(q["legs"]) != exp["leg_count"]:
            fails.append(f"leg_count: expected {exp['leg_count']} got {len(q['legs'])}")

        html_path = os.path.join(work, "email.html")
        rc, out = run(
            [sys.executable, os.path.join(HERE, "render_html.py"), qpath, html_path],
            work,
        )
        if rc:
            fails.append(f"render_html failed:\n{out}")
        pdf_path, print_html = os.path.join(work, "quote.pdf"), os.path.join(
            work, "quote.print.html"
        )
        if want_pdf:
            rc, out = run(
                [
                    sys.executable,
                    os.path.join(HERE, "render_print.py"),
                    qpath,
                    pdf_path,
                    "--html",
                    print_html,
                ],
                work,
            )
            if rc:
                fails.append(f"render_print failed:\n{out}")
        else:
            # print HTML only, no PDF engine
            sys.path.insert(0, HERE)
            import render_print  # noqa

            open(print_html, "w", encoding="utf-8").write(render_print.render_html(q))

        corpus = ""
        for p in (html_path, print_html):
            if os.path.exists(p):
                corpus += open(p, encoding="utf-8").read()
        if want_pdf and os.path.exists(pdf_path) and shutil.which("pdftotext"):
            corpus += subprocess.run(
                ["pdftotext", pdf_path, "-"], capture_output=True, text=True
            ).stdout
            if "pdf_pages" in exp and shutil.which("pdfinfo"):
                info = subprocess.run(
                    ["pdfinfo", pdf_path], capture_output=True, text=True
                ).stdout
                pages = next(
                    (
                        int(l.split()[-1])
                        for l in info.splitlines()
                        if l.startswith("Pages:")
                    ),
                    None,
                )
                if pages != exp["pdf_pages"]:
                    fails.append(f"pdf_pages: expected {exp['pdf_pages']} got {pages}")
        if want_pdf and os.path.exists(pdf_path):
            rc, out = run(
                [
                    sys.executable,
                    os.path.join(HERE, "verify_document.py"),
                    qpath,
                    "--pdf",
                    pdf_path,
                ],
                work,
            )
            if rc:
                fails.append("verify_document failed:\n" + out.strip())
        for s in exp.get("contains", []):
            if s not in corpus:
                fails.append(f"missing: {s!r}")
        for s in exp.get("not_contains", []):
            if s in corpus:
                fails.append(f"present but forbidden: {s!r}")
        return name, not fails, fails
    finally:
        shutil.rmtree(work, ignore_errors=True)


_BARE = re.compile(r"(?<![\w/${.-])((?:scripts|references|assets)/[A-Za-z0-9._/-]+)")
_SKIP = ("…verbatim from",)


def lint_paths():
    """Bare `scripts/x.py` in an instruction file resolves against the SESSION's
    working directory, not the skill folder, so it always fails at runtime.
    Every such path must be anchored to ${CLAUDE_PLUGIN_ROOT}."""
    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    bad = []
    for owner in ("quote-intake", "quote-document"):
        base = os.path.join(skills, owner)
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("evals", "assets", "__pycache__")]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(root, fn)
                with open(p) as fh:
                    for i, line in enumerate(fh, 1):
                        if any(s in line for s in _SKIP):
                            continue
                        for m in _BARE.finditer(line):
                            bad.append(
                                f"{os.path.relpath(p, skills)}:{i}: {m.group(1)}"
                            )
    missing = []
    root = os.path.normpath(os.path.join(skills, ".."))
    for owner in ("quote-intake", "quote-document"):
        for dirpath, dirs, files in os.walk(os.path.join(skills, owner)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dirpath, fn)
                with open(p) as fh:
                    text = fh.read()
                for ref in re.findall(
                    r"\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9._/-]+)", text
                ):
                    if not os.path.exists(os.path.join(root, ref)):
                        missing.append(f"{os.path.relpath(p, skills)}: {ref}")
    if bad or missing:
        print("  ✗ instruction paths")
        for b in bad:
            print(f"      - unanchored (resolves against the user's folder): {b}")
        for m in sorted(set(missing)):
            print(f"      - anchored but does not exist: {m}")
        return False
    print("  ✓ instruction paths")
    return True


def lint_route_guards():
    """A blank route map and a collapsed drive time both reached a client once.
    Prove the verifier still rejects them — no network needed."""
    import subprocess
    import tempfile

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  ○ route guards: Pillow unavailable, skipped")
        return True
    missed = []
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(DEFAULT_FIXTURES, "ordinary", "raw_quote.json")
        normalized = os.path.join(td, "quote.json")
        made = subprocess.run(
            [
                sys.executable,
                os.path.join(HERE, "normalize_quote.py"),
                raw,
                normalized,
                "--client",
                "Route guard",
            ],
            capture_output=True,
            text=True,
        )
        if made.returncode:
            print("  ✗ route guards")
            print(
                "      - could not create guard fixture: "
                + (made.stdout + made.stderr).strip()
            )
            return False
        q = json.load(open(normalized, encoding="utf-8"))
        blank = os.path.join(td, "blank.png")
        im = Image.new("RGB", (1100, 620), (235, 232, 228))
        ImageDraw.Draw(im).line([(10, 10), (900, 600)], fill=(184, 115, 51), width=5)
        im.save(blank)
        q["route_map"] = {"png": blank, "attribution": "x"}
        q["legs"][0]["route"] = {"distance_mi": 0.0, "drive_min": 0, "segments": 0}
        bad = os.path.join(td, "bad.json")
        json.dump(q, open(bad, "w", encoding="utf-8"), indent=2)
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "verify_document.py"), bad],
            capture_output=True,
            text=True,
        )
        out = r.stdout + r.stderr
        if r.returncode == 0:
            missed.append("verifier passed a document it should have failed")
        if "single colour" not in out:
            missed.append("blank route map not caught")
        if "drive time of 0 min" not in out:
            missed.append("collapsed drive time not caught")

        # client_notes as a bare string: iterating it yields one character per item,
        # which printed the note as a vertical column of letters down the page.
        q2 = json.load(open(normalized, encoding="utf-8"))
        q2.pop("route_map", None)
        q2["legs"][0][
            "client_notes"
        ] = "Hotel lobby staff to direct guests to the shuttles."
        strp = os.path.join(td, "strnote.json")
        json.dump(q2, open(strp, "w", encoding="utf-8"), indent=2)
        r2 = subprocess.run(
            [sys.executable, os.path.join(HERE, "verify_document.py"), strp],
            capture_output=True,
            text=True,
        )
        if "client_notes is a string" not in (r2.stdout + r2.stderr):
            missed.append("client_notes-as-string not caught")
        # and the renderer must survive it rather than emit a column of letters
        htmlp = os.path.join(td, "s.html")
        r3 = subprocess.run(
            [sys.executable, os.path.join(HERE, "render_html.py"), strp, htmlp],
            capture_output=True,
            text=True,
        )
        if r3.returncode == 0 and os.path.exists(htmlp):
            body = open(htmlp, encoding="utf-8").read()
            if "Hotel lobby staff" not in body:
                missed.append("renderer mangled a string client_notes")
        else:
            missed.append("render_html failed on a string client_notes")
        # PDF-only questions must not be asked once the format rules them out.
        sys.path.insert(0, HERE)
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_decide", os.path.join(HERE, "decide.py")
        )
        try:
            _d = importlib.util.module_from_spec(spec)
            sys.argv = ["decide.py", "--next"]
            try:
                spec.loader.exec_module(_d)
            except SystemExit:
                pass
            for fmt, want in (
                ("email", False),
                ("html", False),
                ("word", False),
                ("excel", False),
                ("pdf", True),
                ("email+pdf", True),
                ("print", True),
            ):
                keys = _d.order_for(
                    {"client_questions": [], "decisions": {"format": fmt}}
                )
                has = ("cover" in keys) or ("map" in keys)
                if has != want:
                    missed.append(
                        f"format '{fmt}': cover/map {'asked' if has else 'skipped'}, expected "
                        f"{'asked' if want else 'skipped'}"
                    )
            if "cover" not in _d.order_for({"client_questions": [], "decisions": {}}):
                missed.append("cover skipped when no format is stated yet")
        except Exception as ex:
            missed.append(f"could not check question gating: {ex}")

    if missed:
        print("  ✗ route guards")
        for m in missed:
            print(f"      - {m}")
        return False
    print("  ✓ route guards")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=DEFAULT_FIXTURES)
    ap.add_argument("--only", default=None)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    dirs = sorted(
        d
        for d in glob.glob(os.path.join(os.path.expanduser(a.fixtures), "*"))
        if os.path.isdir(d)
    )
    if a.only:
        dirs = [d for d in dirs if os.path.basename(d) == a.only]
    if not dirs:
        sys.exit(f"No fixtures found in {a.fixtures}")
    lint_ok = lint_paths()
    lint_ok = lint_route_guards() and lint_ok
    bad = 0
    for d in dirs:
        name, ok, msgs = check_fixture(d, a.pdf)
        if ok is None:
            print(f"  ○ {name}: {msgs[0]}")
        elif ok:
            print(f"  ✓ {name}")
        else:
            bad += 1
            print(f"  ✗ {name}")
            for m in msgs:
                print("      - " + m.replace("\n", "\n        "))
    total = sum(1 for d in dirs if os.path.exists(os.path.join(d, "expected.json")))
    print(
        f"\n{total - bad}/{total} fixtures passed"
        + (" (with PDF)" if a.pdf else "")
        + ("" if lint_ok else "  — guard checks FAILED")
    )
    sys.exit(1 if (bad or not lint_ok) else 0)


if __name__ == "__main__":
    main()
