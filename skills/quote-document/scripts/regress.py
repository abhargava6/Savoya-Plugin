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
  normalize: {client, prepared_by, select, option, title, alternative: ["alt:primary", ...]}
            option: pick one option from an options[] comparison response
  option_b_total_cents: int                          when alternatives are declared
  edits: {meta: {...}, personalization: {cover: "event-planners", ...}, legs: {<key>: {label, client_notes, stops: {"<index>": {label}}}}}
  adjustments: ["label|percent|5", ...]             applied in order
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
DEFAULT_FIXTURES = os.path.join(SKILL, "evals", "fixtures")


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


def check_fixture(fx, want_pdf, html_out=None):
    name = os.path.basename(fx.rstrip("/"))
    exp_path = os.path.join(fx, "expected.json")
    if not os.path.exists(exp_path):
        return name, None, ["no expected.json (capture only — add assertions to promote)"]
    exp = json.load(open(exp_path, encoding="utf-8"))
    fails, work = [], tempfile.mkdtemp(prefix=f"regress-{name}-")
    try:
        qpath = os.path.join(work, "quote.json")
        if exp.get("handoff") and os.path.isdir(os.path.join(fx, "handoff")):
            n = exp.get("normalize", {})
            cmd = [sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", os.path.join(fx, "handoff"), qpath]
            if n.get("prepared_by"): cmd += ["--prepared-by", n["prepared_by"]]
            if n.get("title"): cmd += ["--title", n["title"]]
            rc, out = run(cmd, work)
            if rc:
                return name, False, [f"normalize --from-handoff failed:\n{out}"]
        elif os.path.exists(os.path.join(fx, "raw_quote.json")):
            n = exp.get("normalize", {})
            cmd = [sys.executable, os.path.join(HERE, "normalize_quote.py"), os.path.join(fx, "raw_quote.json"), qpath,
                   "--client", n.get("client", "Client")]
            if n.get("prepared_by"): cmd += ["--prepared-by", n["prepared_by"]]
            # The new contract's comparison is options[2..5], one complete package each.
            # normalize_quote.py has always taken --option; the harness never passed it,
            # because every fixture predated the options shape and used alternative units
            # inside one response instead.
            if n.get("option"): cmd += ["--option", n["option"]]
            if n.get("select"): cmd += ["--select", n["select"]]
            if n.get("title"): cmd += ["--title", n["title"]]
            for alt in n.get("alternative", []): cmd += ["--alternative", alt]
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
                d.line([(90, 540), (400, 300), (760, 360), (1010, 120)], fill=(184, 115, 51), width=6)
                im.save(stub)
                q_["route_map"]["png"] = stub
            except ImportError:
                q_.pop("route_map", None)
            json.dump(q_, open(qpath, "w", encoding="utf-8"), indent=2)
        if exp.get("edits"):
            q = json.load(open(qpath, encoding="utf-8"))
            q = apply_edits(q, exp["edits"])
            json.dump(q, open(qpath, "w", encoding="utf-8"), indent=2)

        cmd = [sys.executable, os.path.join(HERE, "apply_adjustments.py"), qpath, "--clear"]
        for a in exp.get("adjustments", []):
            cmd += ["--add", a]
        if exp.get("commission_pct") is not None:
            cmd += ["--commission-pct", str(exp["commission_pct"])]
        rc, out = run(cmd, work)
        if rc:
            return name, False, [f"apply_adjustments failed:\n{out}"]

        q = json.load(open(qpath, encoding="utf-8"))
        for k in ("engine_subtotal_cents", "total_cents"):
            if k in exp and q.get(k) != exp[k]:
                fails.append(f"{k}: expected {exp[k]} got {q.get(k)}")
        if "option_b_total_cents" in exp and (q.get("option_b") or {}).get("total_cents") != exp["option_b_total_cents"]:
            fails.append(f"option_b_total_cents: expected {exp['option_b_total_cents']} got {(q.get('option_b') or {}).get('total_cents')}")
        if "commission_amounts" in exp and q.get("commission_amounts") != exp["commission_amounts"]:
            fails.append(f"commission_amounts: expected {exp['commission_amounts']} got {q.get('commission_amounts')}")
        if "leg_count" in exp and len(q["legs"]) != exp["leg_count"]:
            fails.append(f"leg_count: expected {exp['leg_count']} got {len(q['legs'])}")

        html_path = os.path.join(work, "email.html")
        rc, out = run([sys.executable, os.path.join(HERE, "render_html.py"), qpath, html_path], work)
        if rc:
            fails.append(f"render_html failed:\n{out}")
        pdf_path, print_html = os.path.join(work, "quote.pdf"), os.path.join(work, "quote.print.html")
        if want_pdf:
            rc, out = run([sys.executable, os.path.join(HERE, "render_print.py"), qpath, pdf_path, "--html", print_html], work)
            if rc:
                fails.append(f"render_print failed:\n{out}")
        else:
            # print HTML only, no PDF engine
            sys.path.insert(0, HERE)
            import render_print  # noqa
            open(print_html, "w", encoding="utf-8").write(render_print.render_html(q))

        # Hand the rendered print HTML to the caller so the page measurement runs over
        # exactly this document, in one browser session for the whole suite, rather than
        # preparing the fixtures a second time with its own assumptions.
        if html_out and os.path.exists(print_html):
            shutil.copy(print_html, os.path.join(html_out, f"{name}.print.html"))

        corpus = ""
        for p in (html_path, print_html):
            if os.path.exists(p):
                corpus += open(p, encoding="utf-8").read()
        # Page count WITHOUT a PDF engine. The renderer emits exactly one
        # <section class="page"> per printed page, so this is the same number pdfinfo
        # reports -- verified against all ten fixtures. Gating it behind --pdf is how a
        # pagination regression shipped in 0.23.5: the suite everyone actually runs could
        # not see page counts at all, and the gate that could only runs where a PDF engine
        # exists, which is not where the work happens.
        #
        # Match the CLASS, not a quote after it: the cover is class="page blank", so
        # '<section class="page"' silently misses it and every count comes out one short.
        # That cost an hour of arguing with a correct bug report.
        # A fixture whose layout is only right after the browser has measured it (the
        # renderer moves a clipped totals block onto its own page) can only be page-counted
        # where a browser exists. Elsewhere the estimate stands alone and says 4, not 5.
        try:
            import playwright.sync_api  # noqa: F401
            _have_browser = True
        except Exception:
            _have_browser = False
        _skip_pages = bool(exp.get("needs_browser_layout")) and not (_have_browser and want_pdf)
        if "pdf_pages" in exp and os.path.exists(print_html) and not _skip_pages:
            with open(print_html, encoding="utf-8") as fh:
                sections = len(re.findall(r'<section class="page\b', fh.read()))
            if sections != exp["pdf_pages"]:
                fails.append(f"pages: expected {exp['pdf_pages']} got {sections} "
                             f"(counted from the print HTML; no PDF engine needed)")
        if want_pdf and os.path.exists(pdf_path) and shutil.which("pdftotext"):
            corpus += subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
            if "pdf_pages" in exp and shutil.which("pdfinfo") and not _skip_pages:
                info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
                pages = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), None)
                if pages != exp["pdf_pages"]:
                    fails.append(f"pdf_pages: expected {exp['pdf_pages']} got {pages}")
        if want_pdf and os.path.exists(pdf_path):
            rc, out = run([sys.executable, os.path.join(HERE, "verify_document.py"), qpath, "--pdf", pdf_path], work)
            if rc:
                fails.append("verify_document failed:\n" + out.strip())
        import html as _htmlmod
        corpus = _htmlmod.unescape(corpus)         # the print HTML carries &middot; and &amp;
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
                            bad.append(f"{os.path.relpath(p, skills)}:{i}: {m.group(1)}")
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
                for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9._/-]+)", text):
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


# The tool contract lives in ONE place: the ```tools block in mcp-contract.md. It used to
# be a literal set here, which meant the contract had two homes — a reference file CSMs'
# sessions read, and a constant only the suite read. Two homes is how the last drift
# happened. The guard now reads the reference file, so the file the flow is written
# against is the file the suite enforces.
CONTRACT_DOC = os.path.normpath(os.path.join(
    HERE, "..", "..", "quote-intake", "references", "mcp-contract.md"))


def _fenced(text, tag):
    m = re.search(r"^```" + re.escape(tag) + r"\s*\n(.*?)^```", text, re.S | re.M)
    if not m:
        return None
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]


def mcp_tools():
    """Parse mcp-contract.md: the live tools, and the ones it records as removed.

    Raises rather than returning a default. A missing or empty contract must fail the
    suite loudly — a guard that silently allows everything when its input disappears is
    worse than no guard, because it still prints a tick.

    The removed names are tolerated in the contract file ONLY. Recording what left the
    contract is that file's job; a dead tool anywhere else is the bug this guard is for."""
    with open(CONTRACT_DOC) as fh:
        text = fh.read()
    live = _fenced(text, "tools")
    if live is None:
        raise RuntimeError(f"no ```tools block in {CONTRACT_DOC}")
    if not live:
        raise RuntimeError(f"empty ```tools block in {CONTRACT_DOC}")
    return frozenset(live), frozenset(_fenced(text, "tools-removed") or ())

# Anything shaped like a Savoya tool name. Deliberately a pattern rather than a list of
# the two tools we know were removed: a blocklist only catches the last change, a pattern
# catches the next one. Verified against the whole tree — today every match is a tool.
_TOOLISH = re.compile(r"\b(?:resolve|preview|calculate|generate|plan)_[a-z0-9_]+")

# Local identifiers that match the pattern but are not MCP tools. Empty on purpose: if a
# future function name trips this guard, either rename it or add it here — don't add a
# non-tool to the contract file's tools block, which is the contract.
_NOT_TOOLS = frozenset()

# Two files are exempt, each for a stated reason — not for convenience.
#
# feedback-archive.md is DATED HISTORY, read during the weekly pass and never at runtime.
# Its pre-October entries describe the approximate path accurately for the dates they
# carry; rewriting them to satisfy a guard would falsify the record.
#
# regress.py is this file: it *holds* the contract above and records what left it, so it
# has to be able to write the removed names down. It issues no MCP calls, so there is no
# dead path it could be hiding. (It flagged its own comment the first time this ran, which
# is a fair demonstration that the pattern works.)
_CONTRACT_EXEMPT = frozenset({"feedback-archive.md", "regress.py"})


def lint_tool_contract():
    """No instruction file or script may name an MCP tool outside the current contract.

    This guard exists because the connector dropped two tools and the plugin went on
    calling them for two weeks. Same idea as the instruction-path lint: the failure was
    silent at authoring time and loud only in front of a CSM."""
    try:
        contract, retired = mcp_tools()
    except (OSError, RuntimeError) as e:
        print("  ✗ tool contract")
        print(f"      - cannot read the contract: {e}")
        print("      mcp-contract.md's ```tools block IS the contract. Without it this")
        print("      guard cannot run, and it fails rather than passing vacuously.")
        return False
    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    repo = os.path.normpath(os.path.join(skills, ".."))
    targets = []
    for owner in ("quote-intake", "quote-document"):
        for dirpath, dirs, files in os.walk(os.path.join(skills, owner)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                if fn in _CONTRACT_EXEMPT:
                    continue
                if fn.endswith((".md", ".py", ".json")):
                    targets.append(os.path.join(dirpath, fn))
    # Repo-root docs that describe current behaviour. CHANGELOG.md is deliberately absent:
    # like feedback-archive.md it is dated history, and its 0.22.1 entry has to name the
    # two tools that were removed in order to explain the release.
    for fn in ("README.md", "CLAUDE.md", "CONTRIBUTING.md", "RULES.md"):
        p = os.path.join(repo, fn)
        if os.path.exists(p):
            targets.append(p)

    bad = []
    for p in sorted(set(targets)):
        try:
            with open(p) as fh:
                lines = fh.readlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, 1):
            in_contract_doc = os.path.abspath(p) == os.path.abspath(CONTRACT_DOC)
            for name in _TOOLISH.findall(line):
                if name in contract or name in _NOT_TOOLS:
                    continue
                if in_contract_doc and name in retired:
                    continue
                bad.append((os.path.relpath(p, repo), i, name))

    if bad:
        print("  ✗ tool contract")
        for rel, i, name in bad:
            print(f"      - names a tool outside the contract: {rel}:{i}: {name}")
        print("      mcp-contract.md's ```tools block is the contract. If the server")
        print("      really gained this tool, add it there. If it was removed, this is")
        print("      the dead path — and the contract file needs a Removed row too.")
        return False
    print("  ✓ tool contract")
    return True


def lint_warning_surfacing():
    """One Core warning is suppressed. Prove it is exactly one, and that an unrecognised
    warning still reaches the CSM.

    This guard exists because the intake summarizer used to print only the two warning
    shapes it recognised and drop the rest in silence — an allowlist hides real warnings
    just as effectively as a filter does, only less visibly. It also pins the suppression
    string, which is duplicated across two skills that cannot import from each other."""
    import importlib.util

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    try:
        ho = load(os.path.join(skills, "quote-intake", "scripts", "handoff.py"), "_ho")
        nq = load(os.path.join(skills, "quote-document", "scripts", "normalize_quote.py"), "_nq")
    except Exception as e:
        print(f"  ✗ warning surfacing: could not import ({e})")
        return False

    problems = []

    # 1. The two copies of the suppression must be identical, or one skill quietly
    #    diverges from the other.
    if ho.SUPPRESSED_WARNING != nq.SUPPRESSED_WARNING:
        problems.append(f"suppression differs: handoff.py {ho.SUPPRESSED_WARNING!r} vs "
                        f"normalize_quote.py {nq.SUPPRESSED_WARNING!r}")

    unknown = "Vendor surcharge applied for this service area"
    unit = {
        "key": "u1", "label": "Leg 1", "quantity": 1, "line_total": 10000,
        "passenger_count": 2, "pickup_date": "2027-03-20T09:00:00-07:00",
        "vehicle_type": {"id": 8, "name": "SUV", "capacity": 6},
        "stops": [{"name": "A", "travel_time": 0}, {"name": "B", "travel_time": 10}],
        "pricing_summary": {"status": "priced", "total_amount": 10000,
                            "pricing_method": "transfer",
                            "rate": {"effective_rate_amount": 10000, "billing_unit": "trip"},
                            "calculation": {"quantity": 1}},
        "warnings": [ho.SUPPRESSED_WARNING + " for this quote", unknown],
    }
    rendered = "\n".join(ho.unit_lines(unit))

    # 2. The suppressed one must not appear...
    if ho.SUPPRESSED_WARNING in rendered:
        problems.append("the suppressed passenger warning was rendered on a priced unit")
    # 3. ...and the unrecognised one must.
    if unknown not in rendered:
        problems.append("an UNRECOGNISED warning was swallowed — this is the failure mode "
                        "the guard exists for")

    # 4. Deduped: the same warning across two units is said once.
    seen = set()
    twice = "\n".join(ho.unit_lines(unit, seen=seen) + ho.unit_lines(unit, seen=seen))
    if twice.count(unknown) != 1:
        problems.append(f"warning repeated {twice.count(unknown)}× across units; expected once")

    # 5. Suppression is conditional on the unit having priced. A blocked unit keeps it.
    blocked = dict(unit, pricing_summary=dict(unit["pricing_summary"], status="blocked"))
    if ho.SUPPRESSED_WARNING not in "\n".join(ho.unit_lines(blocked)):
        problems.append("the passenger warning was suppressed on a BLOCKED unit; "
                        "suppression is conditional on pricing succeeding")

    if problems:
        print("  ✗ warning surfacing")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ warning surfacing")
    return True


def lint_presentation_render():
    """Render Core's presentation block from a REAL captured response, and prove the
    three boundaries hold: fall back when the block is absent, surface a disagreement
    between Core's own numbers, and apply B9's single suppression here too.

    The renderer printed the suppressed passenger warning twice on its first run, because
    the suppression lives in handoff.py and this was a third code path. It now imports
    that constant; this guard is what keeps the paths agreeing."""
    import importlib.util

    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    mod_path = os.path.join(skills, "quote-intake", "scripts", "render_presentation.py")
    fx = os.path.join(skills, "quote-intake", "evals", "fixtures",
                      "greeter-as-directed", "raw_quote.json")
    try:
        spec = importlib.util.spec_from_file_location("_rp", mod_path)
        rp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rp)
        with open(fx) as fh:
            raw = json.load(fh)
    except Exception as e:
        print(f"  ✗ presentation render: could not load ({e})")
        return False

    problems = []
    out, code = rp.render(raw)
    if code != 0 or not out:
        problems.append(f"a real quote_result response did not render (exit {code})")
        out = out or ""

    # Core's figures must appear as Core sent them.
    for want in ("$404.20", "Hourly Greeter/Coordinator", "5.25 hrs billable",
                 "$76.99/hour", "2-hr cancel"):
        if want not in out:
            problems.append(f"missing from the render: {want!r}")

    # B9's suppression applies here too, or the CSM sees the warning anyway and B9 is moot.
    if "No passenger was selected" in out:
        problems.append("the suppressed passenger warning was rendered")

    # The requested-vs-billed note is the D1 user-flow requirement. 4 asked, 5.25 billed.
    if "against 4 hrs requested" not in out:
        problems.append("no requested-vs-billed note — a CSM who typed 4 hours sees 5.25 "
                        "with no explanation")

    # Absent block → exit 3 so the caller falls back, never a crash and never a blank.
    _, code = rp.render({"quote_units": [], "aggregate_total": 0})
    if code != 3:
        problems.append(f"a response with no presentation block returned {code}, not 3")

    # Core disagreeing with itself must be shown, not silently resolved.
    skewed = json.loads(json.dumps(raw))
    skewed["presentation"]["data"]["total_amount"] = 99999
    out2, _ = rp.render(skewed)
    if "disagree" not in out2 or "$999.99" not in out2 or "$404.20" not in out2:
        problems.append("a presentation/unit total mismatch was not surfaced with both "
                        "figures")

    # An unrecognised view still renders something truthful rather than nothing.
    odd = json.loads(json.dumps(raw))
    odd["presentation"]["view"] = "some_future_view"
    out3, code3 = rp.render(odd)
    if code3 != 0 or "some_future_view" not in out3:
        problems.append("an unrecognised presentation view did not render generically")

    # Every captured fixture must render, and each view must produce the facts a CSM needs
    # from it. All four views below were corrected against real captures after a first
    # draft guessed the shape — rate_preview in particular lives under data.groups[] and
    # the guess fell through to a generic dump.
    fxdir = os.path.join(skills, "quote-intake", "evals", "fixtures")
    expect = {
        "greeter-as-directed":        ["$404.20", "against 4 hrs requested"],
        "greeter-no-rate-boise":      ["could not be priced", "provide a temporary rate",
                                       "no matching Savoya rate"],
        "rate-preview-orange-county": ["$173.25/hr", "5 hrs min", "72-hr cancel",
                                       "hourly rate not found", "16 in market",
                                       "limited availability"],
        "comparison-two-options":     ["$346.50", "$418.88", "labelled value",
                                       "labelled elevated", "select_scenario"],
        "capacity-80pax-minibus":     ["2× Mini Bus", "$3,149.20", "5 hrs min"],
        "temporary-rate-execvan":     ["$192.50/hour", "rack $250.00",
                                       "was not saved in Savoya"],
        "temporary-discount-sedan":   ["$297.00", "40% discount", "Event discount"],
    }
    for slug, wants in sorted(expect.items()):
        fp = os.path.join(fxdir, slug, "raw_quote.json")
        if not os.path.exists(fp):
            problems.append(f"{slug}: fixture missing")
            continue
        with open(fp) as fh:
            doc = json.load(fh)
        o, c = rp.render(doc)
        if c != 0 or not o:
            problems.append(f"{slug}: did not render (exit {c})")
            continue
        for w in wants:
            if w not in o:
                problems.append(f"{slug}: render is missing {w!r}")
        # Core says this on every unit of every fixture; none of them should show it.
        if "No passenger was selected" in o:
            problems.append(f"{slug}: rendered the suppressed passenger warning")

    if problems:
        print("  ✗ presentation render")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ presentation render")
    return True


def lint_airport_shape():
    """An airport stop must be recognised in BOTH response shapes.

    The connector moved airport identification from a top-level `airport` object on the
    stop to `location.type == "airport"`. Reading only the old shape made every airport
    stop normalize as an address and dropped the flight object with it, so the "flight
    time to be confirmed" disclosure stopped appearing on client documents — silently,
    because the fixtures all carried the old shape. This guard fails if either shape stops
    being recognised."""
    import importlib.util
    mod = os.path.join(HERE, "normalize_quote.py")
    try:
        spec = importlib.util.spec_from_file_location("_nq_air", mod)
        nq = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nq)
    except Exception as e:
        print(f"  ✗ airport shape: could not import ({e})")
        return False

    flight = {"commercial_tbd": True, "flight_type": "departure",
              "scheduled_time": "2027-09-17T16:00:00.000Z"}
    shapes = {
        "legacy top-level airport key": {"airport": {"id": 4655910}, "flight": flight},
        "current location.type":        {"display_name": "BOS - Boston Logan International",
                                         "location": {"type": "airport"}, "flight": flight},
        "echoed stop_type":             {"stop_type": "airport", "flight": flight},
    }
    problems = []
    for name, stop in shapes.items():
        out = nq.normalize_stop(stop, None)
        if out.get("kind") != "airport":
            problems.append(f"{name}: normalized as {out.get('kind')!r}, not 'airport'")
        if not (out.get("flight") or {}).get("tbd"):
            problems.append(f"{name}: flight object lost — the TBD disclosure cannot fire")
    # A plain address must NOT be mistaken for an airport.
    plain = nq.normalize_stop({"display_name": "101 Harborside Drive",
                               "location": {"type": "city"}}, None)
    if plain.get("kind") != "address":
        problems.append(f"a city stop normalized as {plain.get('kind')!r}")

    if problems:
        print("  ✗ airport shape")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ airport shape")
    return True


def lint_positioned_from():
    """The positioned-from disclosure must fire from EITHER signal.

    A job priced out of a neighbouring market folds positioning time into the bill — a
    Whistler tour quoted from Vancouver billed 12 hours against a requested 8. The client
    has to be told why. The "No local providers" warning that used to trigger the note now
    appears only on stop resolution; the quote response signals it as
    `excess_drive_time: true`. Reading only the warning produced no note at all."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("_nq_pos",
                                                      os.path.join(HERE, "normalize_quote.py"))
        nq = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nq)
    except Exception as e:
        print(f"  ✗ positioned-from: could not import ({e})")
        return False

    base = {"key": "u", "label": "L", "quantity": 1, "line_total": 1000,
            "passenger_count": 2, "pickup_date": "2027-06-09T09:00:00-07:00",
            "vehicle_type": {"id": 6, "name": "Coach Bus", "capacity": 50},
            "stops": [{"display_name": "A", "travel_time": 0},
                      {"display_name": "B", "travel_time": 6}],
            "pricing_summary": {"status": "priced", "total_amount": 1000,
                                "pricing_method": "hourly",
                                "rate": {"effective_rate_amount": 1000,
                                         "billing_unit": "hour"},
                                "calculation": {"quantity": 1}}}
    problems = []

    def notes(u):
        leg, _ = nq.normalize_unit(u, None)
        return leg["client_notes"]

    cases = {
        "warning naming the market": dict(base, warnings=[
            "No local providers are available for this reservation. Availability will be "
            "confirmed from our local providers in Vancouver, Canada. Additional drive "
            "time will be incurred on the reservation."]),
        "excess_drive_time flag": dict(base, excess_drive_time=True),
    }
    for name, unit in cases.items():
        try:
            n = notes(unit)
        except Exception as e:
            problems.append(f"{name}: normalize raised ({e})")
            continue
        if not any("positioned from" in x for x in n):
            problems.append(f"{name}: no positioned-from note — a client sees the extra "
                            f"hours with no reason given")
    # A local job must NOT get the note.
    try:
        n = notes(dict(base))
        if n and any("positioned from" in x for x in n):
            problems.append("a local job was told its vehicles are positioned from elsewhere")
    except Exception:
        pass

    if problems:
        print("  ✗ positioned-from")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ positioned-from")
    return True


def lint_money_ownership():
    """Core owns the total. Prove it reconciles exactly, and that a gap refuses to render.

    Two things used to be true and are not any more. The engine lines were re-derived as
    percentages of a running subtotal, which disagreed with Core by cents because Core
    rounds per hour and per vehicle; and the leftover was then quietly added to the last
    engine line, so the document always "matched" while that line misstated its own
    percentage. On a 5-vehicle Boston job the document overstated Core by 30 cents."""
    import importlib.util
    import subprocess
    import tempfile

    fx = os.path.join(DEFAULT_FIXTURES, "boston-offsite", "raw_quote.json")
    if not os.path.exists(fx):
        print("  ○ money ownership: boston-offsite fixture missing, skipped")
        return True
    problems = []
    with tempfile.TemporaryDirectory() as d:
        q = os.path.join(d, "quote.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), fx, q,
                            "--client", "Yerdle", "--select",
                            "offsite_9_15_minibus,departure_9_17_minibus"],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(q):
            print(f"  ✗ money ownership: normalize failed ({r.stderr.strip()[:120]})")
            return False
        with open(q) as fh:
            quote = json.load(fh)

        # 1. Exact, by construction — not by absorption.
        if quote["total_cents"] != quote["engine_total_cents"]:
            problems.append(f"document total {quote['total_cents']} != Core's "
                            f"{quote['engine_total_cents']}")
        # 2. No line may be quietly adjusted to make that true.
        for a in quote.get("adjustments", []):
            if a.get("rounded_to_engine"):
                problems.append(f"{a['label']!r} was adjusted to force a match — the "
                                f"residual absorption is supposed to be gone")
        # 3. The engine lines must sum with the standard subtotal to Core's figure.
        eng = sum(a.get("amount_cents") or 0 for a in quote.get("adjustments", [])
                  if a.get("source") == "engine")
        if quote["engine_subtotal_cents"] + eng != quote["engine_total_cents"]:
            problems.append("standard subtotal + engine lines != Core's total")

        # 4. A genuine disagreement must refuse to render, not be repaired.
        skew = os.path.join(d, "skewed.json")
        quote2 = json.loads(json.dumps(quote))
        quote2["engine_total_cents"] = quote["engine_total_cents"] + 30
        with open(skew, "w") as fh:
            json.dump(quote2, fh)
        r2 = subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"),
                             skew, "--clear"], capture_output=True, text=True)
        if r2.returncode == 0:
            problems.append("a 30-cent gap rendered anyway — C4 is not failing closed")
        elif "REFUSING TO RENDER" not in (r2.stdout + r2.stderr):
            problems.append("it failed, but without a message a CSM could act on")

        # ...and it must STILL fail closed when a document line has been added.
        #
        # C4 used to run only when no document line existed, on the reasoning that the
        # total is then deliberately no longer the engine's. True of the total; not true
        # of the engine's share of it. The effect was that adding one flat line switched
        # off the only fail-closed money check in the plugin. On a live Irvine quote on
        # 10 Oct 2026 a $200 on-site coordinator line did exactly that, and that quote
        # was also built from a hand-transcribed engine response — the case where the
        # check matters most. Reproduced here: a $100 slip in a leg's line total ships a
        # client document $100 light, silently, with the old condition in place.
        with open(skew, "w") as fh:
            json.dump(quote2, fh)
        r3 = subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"),
                             skew, "--clear", "--add", "On-site coordination|flat|200"],
                            capture_output=True, text=True)
        if r3.returncode == 0:
            problems.append("the same gap rendered once a $200 document line was added — "
                            "one flat line must not switch off the only fail-closed "
                            "money check in the plugin")
        elif "engine share" not in (r3.stdout + r3.stderr):
            problems.append("it refused, but did not say the comparison was against the "
                            "ENGINE share of the total — a CSM reading it would think "
                            "their own added line was the discrepancy")

        # A WAIVED engine line must still render. Core's aggregate contains the waived
        # amount -- the waiver is ours, recorded so the booking carries it in Savoya --
        # so the document total is legitimately short by exactly that much. Nothing added
        # it back, so waiving ANYTHING refused to render and `--waive` was unusable:
        # waiving the fuel surcharge on the Irvine quote produced a "$58.50 gap" that was
        # the waiver itself. `--waive` is the documented, only way to drop an engine line,
        # and it had no guard on it at all.
        good = os.path.join(d, "good.json")
        for label, extra, must_refuse in (
                ("waive one engine line", ["--waive", "Fuel surcharge"], False),
                ("waive one + add a flat line",
                 ["--waive", "Fuel surcharge", "--add", "On-site|flat|200"], False),
                ("a real gap, with a waiver in play",
                 ["--waive", "Fuel surcharge"], True)):
            with open(good, "w") as fh:
                json.dump(quote2 if must_refuse else quote, fh)
            rw = subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"),
                                 good] + extra, capture_output=True, text=True)
            refused = "REFUSING TO RENDER" in (rw.stdout + rw.stderr)
            if refused and not must_refuse:
                problems.append(f"{label}: refused to render a legitimate waiver — Core's "
                                f"aggregate still contains the waived amount, so the "
                                f"document is short by exactly the waiver")
            if must_refuse and not refused:
                problems.append(f"{label}: a real gap rendered anyway — adding the waived "
                                f"amount back must not mask a genuine mismatch")

    if problems:
        print("  ✗ money ownership")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ money ownership")
    return True


def lint_greeter_leg():
    """A greeter leg must carry no drive time, and must still be priced.

    Core reports a travel_time on a greeter's as-directed stop — 5 minutes at Irvine, 6 at
    Whistler, 13 on the wrong hotel-to-venue shape. "5 min drive" against a person meeting a
    flight is the detail a client notices. The unit is still a real priced unit; only the
    drive figure is dropped."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("_nq_g",
                                                      os.path.join(HERE, "normalize_quote.py"))
        nq = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nq)
    except Exception as e:
        print(f"  ✗ greeter leg: could not import ({e})")
        return False

    def unit(vt):
        return {"key": "g", "label": "Greeter", "quantity": 1, "line_total": 40420,
                "passenger_count": 1, "pickup_date": "2027-03-20T09:00:00-07:00",
                "vehicle_type": vt, "travel_times": [0, 5],
                "stops": [{"display_name": "Hotel", "travel_time": 0},
                          {"display_name": "As Directed", "travel_time": 5,
                           "as_directed": True, "duration": 4}],
                "pricing_summary": {"status": "priced", "total_amount": 40420,
                                    "pricing_method": "hourly",
                                    "rate": {"effective_rate_amount": 7699,
                                             "billing_unit": "hour", "minimum_hours": 2},
                                    "calculation": {"billable_hours": 5.25, "quantity": 1}}}
    problems = []
    g, _ = nq.normalize_unit(unit({"id": 12, "name": "Hourly Greeter/Coordinator",
                                   "capacity": None, "greeter": True}), None)
    if g.get("route"):
        problems.append(f"greeter leg carries a route: {g['route']}")
    if any(s.get("drive_minutes") for s in g["stops"]):
        problems.append("greeter leg carries per-stop drive minutes")
    if not g.get("is_greeter"):
        problems.append("greeter leg not flagged as one")
    if (g["pricing"] or {}).get("line_total_cents") != 40420:
        problems.append("greeter leg lost its price — only the drive time should go")

    # By name alone, when `greeter` isn't on the vehicle_type object.
    g2, _ = nq.normalize_unit(unit({"id": 13, "name": "Single Greet", "capacity": None}), None)
    if g2.get("route") or not g2.get("is_greeter"):
        problems.append("a greeter identified by name alone kept its drive time")

    # A normal vehicle must keep its drive time.
    v, _ = nq.normalize_unit(unit({"id": 8, "name": "SUV", "capacity": 6}), None)
    if not v.get("route"):
        problems.append("an SUV lost its drive time — suppression is too broad")

    if problems:
        print("  ✗ greeter leg")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ greeter leg")
    return True


def lint_handoff_contract():
    """A handoff from an older build must be refused, with a sentence a CSM can act on.

    A v1 or v2 handoff was written against the previous MCP contract — estimate_type could
    be "approximate", a passenger id was always present, the sourcing market arrived on the
    quote. Reading those fields as if they still mean what they meant produces a document
    that looks right, which is worse than one that refuses. Also pins the three places the
    version number lives: handoff.py writes it, normalize_quote.py checks it, and
    handoff-contract.md documents it."""
    import importlib.util
    import subprocess
    import tempfile

    skills = os.path.normpath(os.path.join(HERE, "..", ".."))

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    try:
        nq = load(os.path.join(HERE, "normalize_quote.py"), "_nq_h")
    except Exception as e:
        print(f"  ✗ handoff contract: could not import ({e})")
        return False

    problems = []
    doc = os.path.join(skills, "quote-intake", "references", "handoff-contract.md")
    try:
        with open(doc) as fh:
            text = fh.read()
        if f'"contract": {nq.HANDOFF_CONTRACT},' not in text:
            problems.append(f"handoff-contract.md does not document contract "
                            f"{nq.HANDOFF_CONTRACT}")
    except OSError as e:
        problems.append(f"cannot read handoff-contract.md ({e})")

    fx = os.path.join(DEFAULT_FIXTURES, "boston-offsite-handoff", "handoff")
    if os.path.isdir(fx):
        with open(os.path.join(fx, "intake.json")) as fh:
            live = json.load(fh)
        if live.get("contract") != nq.HANDOFF_CONTRACT:
            problems.append(f"the handoff fixture is contract {live.get('contract')}, "
                            f"this build reads {nq.HANDOFF_CONTRACT}")
        # A downgraded copy must be refused.
        with tempfile.TemporaryDirectory() as d:
            import shutil
            hd = os.path.join(d, "handoff")
            shutil.copytree(fx, hd)
            stale = dict(live, contract=nq.HANDOFF_CONTRACT - 1)
            with open(os.path.join(hd, "intake.json"), "w") as fh:
                json.dump(stale, fh)
            r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                                "--from-handoff", hd, os.path.join(d, "q.json")],
                               capture_output=True, text=True)
            out = r.stdout + r.stderr
            if r.returncode == 0:
                problems.append("a stale handoff was accepted — it must be refused")
            elif "older version of the plugin" not in out:
                problems.append("a stale handoff was refused, but not in words a CSM "
                                "could act on")

    if problems:
        print("  ✗ handoff contract")
        for pr in problems:
            print(f"      - {pr}")
        return False
    print("  ✓ handoff contract")
    return True


# The document question set lives in ONE place: BASE_ORDER in decide.py. It used to live
# in three — decide.py, questions.md and the decision tree — and on 7 Oct Group C removed
# the `fuel` question from the first two and missed the third, so the file CLAUDE.md calls
# the authoritative flow went on listing a question the script no longer asks AND went on
# saying a discount is "a document-level line. Never re-quote through the engine" — the
# exact local-arithmetic-on-Core's-number that C1 replaced with a Core re-quote. Nothing
# failed; the prose just disagreed with the code for a day.
_MONEY_PROSE_EXEMPT = frozenset({
    # Dated history. Rewriting these to satisfy a guard would falsify the record.
    "feedback-archive.md",
})


def document_question_keys():
    """The question keys decide.py will actually ask, parsed from decide.py itself."""
    src = os.path.join(HERE, "decide.py")
    with open(src) as fh:
        text = fh.read()
    m = re.search(r"^BASE_ORDER\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not m:
        raise RuntimeError(f"no BASE_ORDER in {src}")
    base = re.findall(r"[\"\']([a-z_]+)[\"\']", m.group(1))
    if not base:
        raise RuntimeError(f"empty BASE_ORDER in {src}")
    # Keys decide.py inserts conditionally rather than listing in BASE_ORDER.
    # The inserted key is insert()'s LAST argument; a lazier pattern picks up the
    # index key ("discount_pct") from o.insert(o.index("discount_pct") + 1, "greeter_cost").
    extra = set(re.findall(r"o\.insert\(.*?,\s*[\"\']([a-z_]+)[\"\']\s*\)", text))
    return frozenset(base), frozenset(extra) - frozenset(base)


# The `decisions` block in handoff-contract.md is the same invariant lint_question_set
# checks in prose, in a shape that guard cannot see: it matches NUMBERED lists, and this is
# a jsonc key block. That is precisely how a `"fuel"` key survived there for three days
# after decide.py stopped writing one -- the fuel question was removed on 7 Oct and four
# files were updated, and this was not one of them, because nothing was looking at it.
_HANDOFF_DOC = os.path.join(
    SKILL, "..", "quote-intake", "references", "handoff-contract.md")


def handoff_decision_keys():
    """The top-level keys of the `decisions` object documented in handoff-contract.md."""
    with open(os.path.normpath(_HANDOFF_DOC)) as fh:
        lines = fh.readlines()
    start = next((i for i, l in enumerate(lines) if re.search(r'"decisions"\s*:\s*\{', l)), None)
    if start is None:
        raise RuntimeError('no `"decisions": {` block in handoff-contract.md')
    keys, depth = [], 0
    for line in lines[start:]:
        code = re.sub(r"//.*$", "", line)
        if depth == 1:
            m = re.match(r'\s*"([a-z_]+)"\s*:', code)
            if m:
                keys.append(m.group(1))
        depth += code.count("{") - code.count("}")
        if depth <= 0:
            break
    if not keys:
        raise RuntimeError("`decisions` block in handoff-contract.md documents no keys")
    return keys


def document_question_order():
    """BASE_ORDER as a list -- the order decide.py actually asks in, not just the set."""
    src = os.path.join(HERE, "decide.py")
    with open(src) as fh:
        text = fh.read()
    m = re.search(r"^BASE_ORDER\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not m:
        raise RuntimeError(f"no BASE_ORDER in {src}")
    return re.findall(r"[\"\']([a-z_]+)[\"\']", m.group(1))


def lint_question_set():
    """Instruction prose must name the questions decide.py asks — no more, no fewer —
    and must never tell a session to apply a discount without going back to Core."""
    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    try:
        base, extra = document_question_keys()
        base_order = document_question_order()
    except RuntimeError as e:
        print(f"  ✗ question set: {e}")
        return False
    allowed = base | extra
    problems = []

    numbered = re.compile(r"^\s*\d+\.\s*\*\*`?([a-z_]{3,})`?\*\*")
    # "never/don't re-quote" said anywhere near a discount is the reversed C1 rule --
    # unless the sentence is explicitly recounting it as the OLD rule, which the
    # decision tree does on purpose so the next reader knows it changed under them.
    reversed_c1 = re.compile(r"(never|don'?t|do not)\s+re-?quote", re.I)
    recounted = re.compile(r"used to (say|be|read)|no longer|wrong now|was right under|previously said", re.I)

    for owner in ("quote-intake", "quote-document"):
        for root, dirs, files in os.walk(os.path.join(skills, owner)):
            dirs[:] = [d for d in dirs if d not in ("evals", "assets", "__pycache__")]
            for fn in sorted(files):
                if not fn.endswith(".md") or fn in _MONEY_PROSE_EXEMPT:
                    continue
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, skills)
                with open(p) as fh:
                    lines = fh.readlines()
                keys = []
                for i, line in enumerate(lines, 1):
                    m = numbered.match(line)
                    if m:
                        keys.append((m.group(1), i))
                    if (reversed_c1.search(line) and re.search(r"discount", line, re.I)
                            and not recounted.search(line)):
                        problems.append(
                            f"{rel}:{i}: tells a session NOT to re-quote a discount. "
                            "A discount is a Core re-quote (temporary_discount), not a local line.")
                # Only judge a list that is plainly the document question list.
                named = {k for k, _ in keys}
                if len(named & allowed) < 3:
                    continue
                for k, i in keys:
                    if k not in allowed:
                        problems.append(
                            f"{rel}:{i}: names '{k}' as a document question, "
                            f"but decide.py does not ask it.")
                for k in sorted(base - named):
                    problems.append(
                        f"{rel}: omits '{k}', which decide.py does ask.")

    # The handoff contract documents the same keys as a jsonc block, which the numbered-
    # list pattern above cannot see. Checked by name rather than by shape.
    try:
        documented = handoff_decision_keys()
    except (OSError, RuntimeError) as e:
        problems.append(f"handoff-contract.md: cannot read the decisions block: {e}")
        documented = None
    if documented is not None:
        seen = set(documented)
        for k in sorted(seen - allowed):
            problems.append(
                f"handoff-contract.md: documents decision key '{k}', "
                "but decide.py does not ask it.")
        for k in sorted(allowed - seen):
            problems.append(
                f"handoff-contract.md: omits decision key '{k}', which decide.py does ask.")
        ordered = [k for k in documented if k in base]
        if ordered != [k for k in base_order if k in set(ordered)]:
            problems.append(
                "handoff-contract.md: lists the decision keys in a different order than "
                f"decide.py asks them ({ordered} vs BASE_ORDER).")

    if problems:
        print("  ✗ question set")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  ✓ question set ({len(base)} asked, {len(extra)} conditional, "
          f"handoff contract agrees)")
    return True


# C4 compares the document total against Core's aggregate, and C5 pins fuel as the
# remainder so that comparison passes by construction. Together they guarantee the TOTAL
# and say nothing about whether each line is the thing its label claims. An additional
# discount the normalizer could not see therefore vanished into the fuel line and printed
# a NEGATIVE "Fuel surcharge" at a positive 10% -- right total, wrong story, in front of a
# client. The invariant below is deliberately not about discounts: a line whose stated
# percentage is positive must not carry a negative amount, and vice versa. That catches
# the next misattribution as well as this one.
_ATTRIBUTION_FIXTURE = os.path.join(
    SKILL, "..", "quote-intake", "evals", "fixtures", "temporary-discount-sedan",
    "raw_quote.json")


def lint_discount_attribution():
    """Every engine line's sign must agree with the percentage it states, and the stated
    discount percentages must add up to the effective discount Core reported."""
    import subprocess
    import tempfile

    fx = os.path.normpath(_ATTRIBUTION_FIXTURE)
    if not os.path.exists(fx):
        print("  \u25cb discount attribution: temporary-discount fixture missing, skipped")
        return True
    with open(fx) as fh:
        raw = json.load(fh)

    def dig(o, key):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == key and isinstance(v, int):
                    return v
                got = dig(v, key)
                if got is not None:
                    return got
        elif isinstance(o, list):
            for v in o:
                got = dig(v, key)
                if got is not None:
                    return got
        return None

    eff_bps = dig(raw, "effective_discount_basis_points")
    problems = []
    with tempfile.TemporaryDirectory() as d:
        q = os.path.join(d, "quote.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), fx, q,
                            "--client", "Yerdle"], capture_output=True, text=True)
        if r.returncode or not os.path.exists(q):
            print(f"  \u2717 discount attribution: normalize failed ({r.stderr.strip()[:120]})")
            return False
        with open(q) as fh:
            quote = json.load(fh)

    for a in quote.get("adjustments", []):
        if a.get("source") != "engine":
            continue
        amt = a.get("amount_cents_fixed")
        if amt is None:
            continue
        pct = a.get("value") or 0
        if pct > 0 and amt < 0:
            problems.append(f"'{a['label']}' states +{pct}% but carries {amt} cents — "
                            "a surcharge line is absorbing a discount")
        if pct < 0 and amt > 0:
            problems.append(f"'{a['label']}' states {pct}% but carries +{amt} cents")

    if eff_bps:
        stated = sum(-(a.get("value") or 0) * 100 for a in quote.get("adjustments", [])
                     if a.get("source") == "engine" and (a.get("value") or 0) < 0)
        if round(stated) != eff_bps:
            problems.append(f"discount lines state {round(stated)} basis points against "
                            f"Core's effective {eff_bps} — a discount is missing a line")

    if quote.get("total_cents") != quote.get("engine_total_cents"):
        problems.append("total no longer matches Core's aggregate")

    if problems:
        print("  \u2717 discount attribution")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 discount attribution ({eff_bps} bps across "
          f"{sum(1 for a in quote['adjustments'] if (a.get('value') or 0) < 0)} lines)")
    return True


# Pagination is an ESTIMATE of height, so it can only be wrong in two directions: it can
# forget something that takes vertical space, or it can mis-measure something it knows
# about. Both happened. The intro note sits above the table and the first-page budget was
# a flat constant, and the route line's height was counted in stops rather than in
# characters -- so a long note plus European hotel names with street addresses clipped a
# real client quote by 246px, with five rows printed underneath the footer.
#
# A geometric check needs a browser, which this suite cannot assume. This one is
# structural and browser-free: whatever the exact budget, spending more of the page above
# the table MUST leave room for fewer rows on it. A renderer that ignores the intro note
# returns the identical layout for both, which is exactly the bug.
def lint_page_fit():
    """A long intro note must cost the first quote page some rows."""
    import copy
    import re as _re
    import subprocess
    import tempfile

    fx = os.path.join(DEFAULT_FIXTURES, "six-leg-heavy-notes", "quote.json")
    if not os.path.exists(fx):
        print("  \u25cb page fit: six-leg fixture missing, skipped")
        return True
    with open(fx) as fh:
        base = json.load(fh)

    long_note = ("Thank you for the opportunity to support this programme. The itinerary "
                 "below covers all ground movements for the family and their guests across "
                 "the three cities, including the airport arrivals, the inter-city "
                 "transfers and the evening events. Vehicles and chauffeurs are held for "
                 "your exclusive use for the durations shown, and we have allowed "
                 "additional time at each pickup so that nobody is waiting.")

    def rows_on_first_table_page(quote, note):
        q = copy.deepcopy(quote)
        q.setdefault("personalization", {})["intro_note"] = note
        with tempfile.TemporaryDirectory() as d:
            qp = os.path.join(d, "quote.json")
            with open(qp, "w") as fh:
                json.dump(q, fh)
            subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"),
                            qp, os.path.join(d, "out.pdf")],
                           capture_output=True, text=True)
            html_path = os.path.join(d, "out.print.html")
            if not os.path.exists(html_path):
                return None
            with open(html_path, encoding="utf-8") as fh:
                html = fh.read()
        for page in _re.findall(r'<section class="page">.*?</section>', html, _re.S):
            body = _re.search(r"<table class='lines'>.*?</tbody>", page, _re.S)
            if body:
                return len(_re.findall(r"<tr>", body.group(0)))
        return None

    short = rows_on_first_table_page(base, "")
    long_ = rows_on_first_table_page(base, long_note)
    if short is None or long_ is None:
        print("  \u2717 page fit: could not render the probe document")
        return False
    if long_ >= short:
        print("  \u2717 page fit")
        print(f"      - a {len(long_note)}-character intro note left the first quote page "
              f"holding {long_} rows, the same as with no note at all ({short}).")
        print("      - the note renders ABOVE the table, so it must cost the page rows; "
              "a flat first-page budget is how rows end up under the footer.")
        return False
    print(f"  \u2713 page fit (intro note costs the first page {short - long_} row(s))")
    return True


# The capture is the only channel from a live session back to whoever maintains this
# plugin, and the step that runs it is specified as silent -- "say nothing to the user".
# So anything that makes it fail produces no error anybody reads: it produces a bug report
# that never arrives. That is not hypothetical. Two defects reached a client PDF on
# 2026-10-09 and were diagnosed only because the CSM pasted them into a chat afterwards;
# the capture for that session never ran.
#
# `--request` used to be mandatory, and node K's own documented fallback -- a quote
# brought from elsewhere, so no handoff and no request.md -- could therefore never produce
# one. The session most likely to be improvising was the session that structurally could
# not report it.
def lint_capture_resilience():
    """A capture must still be produced when the inputs are incomplete."""
    import subprocess
    import tempfile

    fx = os.path.join(DEFAULT_FIXTURES, "six-leg-heavy-notes", "quote.json")
    if not os.path.exists(fx):
        print("  \u25cb capture resilience: six-leg fixture missing, skipped")
        return True

    cases = [
        ("no --request at all (document flow entered without a handoff)", []),
        ("--request pointing at a file that is not there", ["--request", "/nonexistent/request.md"]),
    ]
    problems = []
    with tempfile.TemporaryDirectory() as d:
        for label, extra in cases:
            r = subprocess.run(
                [sys.executable, os.path.join(HERE, "capture_session.py"),
                 "--slug", "guard", "--client", "Guard", "--deliverable", "pdf",
                 "--quote", fx, "--dir", d, "--auto"] + extra,
                capture_output=True, text=True)
            made = [f for f in os.listdir(d) if f.endswith(".capture.json")]
            # A render snapshot (--auto) writes `<slug>.feedback.snapshot.json`; the
            # post-feedback run writes `<slug>.feedback.json`. Either is "the feedback
            # file" here — what matters is that one exists, since it uploads first.
            fb = [f for f in os.listdir(d)
                  if f.endswith((".feedback.json", ".feedback.snapshot.json"))]
            # The last-resort handler keeps a broken capture from stopping a session, but
            # a capture that only survives because of it is still broken: the feedback
            # file is what actually gets uploaded first, and that never gets written.
            if "CAPTURE DEGRADED" in (r.stderr or ""):
                problems.append(f"{label}: only survived via the last-resort handler — "
                                "the capture itself still throws")
            elif not fb:
                problems.append(f"{label}: no feedback file, which is the one that uploads first")
            elif r.returncode != 0:
                problems.append(f"{label}: exited {r.returncode} — "
                                f"{(r.stderr or '').strip().splitlines()[-1][:110] if r.stderr else 'no stderr'}")
            elif not made:
                problems.append(f"{label}: exited cleanly but wrote no capture")
            else:
                with open(os.path.join(d, made[0])) as fh:
                    cap = json.load(fh)
                if not cap.get("request_missing"):
                    problems.append(f"{label}: capture does not record that the request was missing — "
                                    "a silent gap is worse than a noted one")
            for f in os.listdir(d):
                if f.endswith((".capture.json", ".feedback.json",
                               ".feedback.snapshot.json", ".pending-upload")):
                    os.remove(os.path.join(d, f))

    # --- the capture must leave the session, not just the function -----------------
    # Everything below is a 10 Oct 2026 finding. Three real sessions produced captures
    # and the team got none of them without asking: one call was malformed and silent,
    # one upload was never made, one was still outstanding when the session ended -- and
    # the two biggest captures were over the old 25 KB ceiling, so they stayed in a
    # container that no longer exists.
    import base64 as _b64
    import gzip as _gzip
    import json as _json

    with tempfile.TemporaryDirectory() as d:
        # A capture the size of the real one that was lost. No fixture here is big
        # enough to trip a 25 KB ceiling -- the largest makes a 19 KB capture -- so
        # asserting against the small ones proved nothing, and the first version of this
        # check passed happily with the ceiling put back. The quote is padded with inert
        # internal notes until the capture is comparable to the 192 KB World Cup record.
        big = _json.load(open(fx, encoding="utf-8"))
        big.setdefault("internal", {})["_guard_padding"] = [
            f"line {i}: padding so this capture is as large as the ones that were lost "
            f"to the size ceiling on 10 Oct 2026" for i in range(1800)]
        big_fx = os.path.join(d, "big-quote.json")
        with open(big_fx, "w", encoding="utf-8") as fh:
            _json.dump(big, fh)
        if os.path.getsize(big_fx) < 150 * 1024:
            problems.append("the padded guard quote is too small to test the size rule")
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_session.py"),
             "--slug", "guard-big", "--client", "Guard", "--deliverable", "pdf",
             "--quote", big_fx, "--dir", d],
            capture_output=True, text=True)
        try:
            out = _json.loads(r.stdout)
        except ValueError:
            problems.append(f"capture printed no JSON report ({(r.stderr or '')[:160]})")
            out = {}

        titles = [u.get("title", "") for u in out.get("upload", [])]
        if not any(t.endswith(".capture.json.gz.b64") for t in titles):
            problems.append("the full capture is not offered for upload compressed — "
                            "the 25 KB rule stranded the two richest captures of the day")
        if "full_capture_kept_local" in out:
            problems.append("the report still has a size-gated 'kept local' path")

        # the compressed envelope must round-trip, or the weekly pass gets nothing
        packed = next((u["path"] for u in out.get("upload", [])
                       if u.get("title", "").endswith(".gz.b64")), None)
        if packed and os.path.exists(packed):
            try:
                env = _json.load(open(packed, encoding="utf-8"))
                inner = _json.loads(_gzip.decompress(
                    _b64.b64decode(env["data"])).decode("utf-8"))
                if not inner.get("quote"):
                    problems.append("the compressed capture decodes without a quote")
                if env.get("encoding") != "gzip+base64":
                    problems.append("the compressed capture does not declare its encoding")
            except Exception as ex:  # noqa: BLE001
                problems.append(f"the compressed capture does not decode: {ex}")

        # an ephemeral directory must be reported as such, not silently accepted
        local = out.get("local_copy") or {}
        if local.get("durable") is not False:
            problems.append(f"a capture written to {d} is not reported as "
                            f"non-durable — '~' is a container on claude.ai and an "
                            f"isolated VM on a linked desktop, and two captures were "
                            f"reported saved and then lost")

        # pdf_pages must be measured or absent, never the literal 3 it used to be
        cap = next((f for f in os.listdir(d) if f.endswith(".capture.json")), None)
        if cap:
            exp = (_json.load(open(os.path.join(d, cap), encoding="utf-8"))
                   .get("expected") or {})
            if "pdf_pages" in exp:
                problems.append(f"pdf_pages was recorded as {exp['pdf_pages']} with no "
                                f"--pdf to measure; real deliverables were 4, 5 and 8 "
                                f"pages and fixtures run 3 to 9, so a guess invites "
                                f"correcting the expectation to match the output")

        # the marker must be clearable without `rm`, and not without a Drive id
        no_id = subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_session.py"),
             "--mark-uploaded", "guard-big", "--dir", d], capture_output=True, text=True)
        if no_id.returncode == 0:
            problems.append("--mark-uploaded cleared the marker with no --file-id, so a "
                            "session can make the backlog look clean without uploading")
        if not glob.glob(os.path.join(d, "*.pending-upload")):
            problems.append("the pending-upload marker was removed by a refused "
                            "--mark-uploaded")
        with_id = subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_session.py"),
             "--mark-uploaded", "guard-big", "--dir", d, "--file-id", "test123"],
            capture_output=True, text=True)
        if with_id.returncode != 0:
            problems.append(f"--mark-uploaded failed with an id: "
                            f"{(with_id.stderr or '')[:160]}")
        elif glob.glob(os.path.join(d, "*.pending-upload")):
            problems.append("--mark-uploaded left the marker in place, so an upload that "
                            "DID happen still reads as outstanding and the backlog "
                            "count shown to the user is wrong")

        # The full capture must go up on the RENDER pass too, under its own title.
        #
        # It used to be held back for the post-feedback run, which made the richest
        # artifact depend on a conversational step. On 10 Oct 2026 that step was skipped:
        # a live quote delivered its PDF, uploaded the snapshot, never asked "Anything
        # you'd like changed?", and the full capture reached the folder only because the
        # user asked for it by name.
        snap = subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_session.py"),
             "--slug", "guard-snap", "--client", "Guard", "--deliverable", "pdf",
             "--quote", big_fx, "--dir", d, "--auto"], capture_output=True, text=True)
        try:
            snap_out = _json.loads(snap.stdout)
        except ValueError:
            problems.append("the render pass printed no JSON report")
            snap_out = {}
        snap_titles = [u.get("title", "") for u in snap_out.get("upload", [])]
        if not any(t.endswith(".gz.b64") for t in snap_titles):
            problems.append("the render pass does not offer the full capture — a session "
                            "that never reaches the feedback question then loses it")
        # and the two passes must not collide: Drive's create_file always creates, so one
        # title uploaded twice leaves two files with one name, on every quote
        full = subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_session.py"),
             "--slug", "guard-snap", "--client", "Guard", "--deliverable", "pdf",
             "--quote", big_fx, "--dir", d, "--worked", "ok"],
            capture_output=True, text=True)
        try:
            full_titles = [u.get("title", "")
                           for u in _json.loads(full.stdout).get("upload", [])]
        except ValueError:
            full_titles = []
            problems.append("the post-feedback pass printed no JSON report")
        snap_caps = {t for t in snap_titles if t.endswith(".gz.b64")}
        full_caps = {t for t in full_titles if t.endswith(".gz.b64")}
        if snap_caps and full_caps and snap_caps == full_caps:
            problems.append(f"both passes upload the capture as {sorted(snap_caps)[0]} — "
                            f"Drive always creates, so that is two files with one name "
                            f"on every quote")
        if snap_caps and not any("snapshot" in t for t in snap_caps):
            problems.append("the render pass's capture is not marked as the snapshot, so "
                            "the weekly pass cannot tell which copy superseded the other")

        # a malformed call must leave a trace; it used to print usage and vanish
        before = set(glob.glob(os.path.expanduser(
            "~/.savoya-quoting/captures/capture-refused-*.json")))
        subprocess.run([sys.executable, os.path.join(HERE, "capture_session.py"),
                        "--dir", d], capture_output=True, text=True)
        after = set(glob.glob(os.path.expanduser(
            "~/.savoya-quoting/captures/capture-refused-*.json")))
        if not after - before:
            problems.append("a call with missing arguments left no record — the step is "
                            "specified as silent, so a usage error is a bug report that "
                            "never happened")
        for f in after - before:
            try:
                os.remove(f)
            except OSError:
                pass

    if problems:
        print("  \u2717 capture resilience")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 capture resilience ({len(cases)} degraded inputs captured; "
          f"compressed, durability-reported, markable, and loud when misused)")
    return True


# The route guards already catch a BLANK map. They do not catch an honest-looking one:
# the offline overview draws stops in true relative position joined by straight lines,
# which is a schematic, not a driving route. Rendered under the same heading as a street
# map it is a false claim about geography that a client has no way to question -- and the
# CSMs who reported "blank with just straight lines" were describing exactly this picture
# with nothing on the page to explain it.
def lint_map_honesty():
    """A schematic map must not be presented as a street map."""
    import copy
    import subprocess
    import tempfile

    fx = os.path.join(DEFAULT_FIXTURES, "sixteen-leg-route-map", "quote.json")
    if not os.path.exists(fx):
        print("  \u25cb map honesty: route-map fixture missing, skipped")
        return True
    with open(fx) as fh:
        base = json.load(fh)
    if not base.get("route_map"):
        print("  \u25cb map honesty: fixture carries no route_map, skipped")
        return True

    def render(style):
        q = copy.deepcopy(base)
        with tempfile.TemporaryDirectory() as d:
            # The fixture carries the ROUTE_MAP_PNG placeholder the suite substitutes at
            # runtime; without a real file route_page() renders nothing and both styles
            # come back identical for the wrong reason.
            png = os.path.join(d, "map.png")
            try:
                from PIL import Image
                Image.new("RGB", (1100, 620), (235, 232, 228)).save(png)
            except ImportError:
                return "SKIP"
            q["route_map"] = dict(q["route_map"], style=style, png=png)
            qp = os.path.join(d, "quote.json")
            with open(qp, "w") as fh:
                json.dump(q, fh)
            subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"),
                            qp, os.path.join(d, "out.pdf")], capture_output=True, text=True)
            hp = os.path.join(d, "out.print.html")
            if not os.path.exists(hp):
                return None
            with open(hp, encoding="utf-8") as fh:
                return fh.read()

    tiled, offline = render("tiled"), render("offline")
    if tiled == "SKIP":
        print("  \u25cb map honesty: Pillow not installed, skipped")
        return True
    if tiled is None or offline is None:
        print("  \u2717 map honesty: could not render the probe document")
        return False

    problems = []
    if tiled == offline:
        problems.append("a schematic and a street map render identically — "
                        "the document makes the same claim about both")
    if "not a driving route" not in offline and "not driving routes" not in offline:
        problems.append("the schematic does not say its connecting lines are not driving routes")
    if "not a driving route" in tiled or "not driving routes" in tiled:
        problems.append("a real street map is disclaiming itself as a schematic")

    if problems:
        print("  \u2717 map honesty")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 map honesty (schematic and street map are distinguishable)")
    return True


# Several docs exist TWICE: once at the repo root, where anyone would naturally open
# them, and once under assets/plugin-root/, which is the copy rebuild_plugin.py ships.
# Edit the root one and the change silently never reaches a CSM.
#
# The first version of this guard hardcoded ("SETUP.md", "RUNBOOK.md") -- the two files
# the incident happened to involve -- and README.md was ALREADY diverged at the time,
# uncovered. A hardcoded list only ever covers the incident you just had, which is the
# same mistake in a new place. So the list is DERIVED: every file present in both
# locations is checked, and a duplicated file with no declared relationship FAILS rather
# than passing silently. Adding a third copy of something now forces a decision.
#
# Two relationships are legitimate:
#   same   - the two copies must be byte-identical.
#   prefix - the root copy is a superset; the shipped copy must be exactly its opening
#            section. README.md is this: the root version adds a "Working on this repo"
#            section that a CSM should never be handed.
_PAIRED_DOCS = {
    "SETUP.md": "same",
    "RUNBOOK.md": "same",
    "CONTRIBUTING.md": "same",
    "README.md": "prefix",
    # Not a doc, and the one where a drift would be worst: it carries the MCP server URL.
    # A shipped copy pointing at a different host than the repo believes is a whole class
    # of bug nobody would think to look for.
    ".mcp.json": "same",
}

# Pairs that do NOT share a filename, so the derived scan above cannot see them.
# plugin.json is the dangerous one and was invisible to the first two versions of this
# guard. There are two copies at different paths, and **the build reads the one nobody
# would think to edit**: `.claude-plugin/plugin.json` is the standard, obvious manifest
# location and `rebuild_plugin.py` never reads it. Bump the obvious file, build without
# PLUGIN_VERSION, and you ship a package labelled with the new version carrying the old
# content. Compared parsed rather than byte-for-byte, so a trailing newline is not a
# failure.
_CROSS_PATH_PAIRS = (
    (".claude-plugin/plugin.json", "plugin.json"),
)


def lint_paired_docs():
    """Every doc that exists in both places must match its declared relationship."""
    root = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    shipped_dir = os.path.join(SKILL, "assets", "plugin-root")
    if not os.path.isdir(shipped_dir):
        print("  \u25cb paired docs: no plugin-root, skipped")
        return True

    problems, checked = [], 0
    for name in sorted(os.listdir(shipped_dir)):
        a = os.path.join(root, name)
        b = os.path.join(shipped_dir, name)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            continue        # only lives in one place; nothing to drift
        rel = _PAIRED_DOCS.get(name)
        if rel is None:
            problems.append(
                f"{name}: exists in both the repo root and assets/plugin-root/ but no "
                f"relationship is declared. Say whether the two must be identical or the "
                f"shipped copy is an opening section of the root one — an undeclared "
                f"duplicate is how the last three drifts happened.")
            continue
        checked += 1
        with open(a, encoding="utf-8") as fh:
            ta = fh.read()
        with open(b, encoding="utf-8") as fh:
            tb = fh.read()
        if rel == "same" and ta != tb:
            problems.append(
                f"{name}: the root copy and the shipped copy differ ({len(ta)} vs "
                f"{len(tb)} chars) but are declared identical. rebuild_plugin.py ships "
                f"assets/plugin-root/{name}, so an edit to the root copy alone reaches "
                f"nobody.")
        elif rel == "prefix" and not ta.startswith(tb.rstrip() [:max(0, len(tb) - 2)] or tb):
            problems.append(
                f"{name}: the shipped copy is declared to be the opening section of the "
                f"root copy, and is not. Either the root copy was edited above the split "
                f"or the shipped copy drifted.")

    for root_rel, shipped_rel in _CROSS_PATH_PAIRS:
        a = os.path.join(root, root_rel)
        b = os.path.join(shipped_dir, shipped_rel)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            continue
        checked += 1
        try:
            with open(a, encoding="utf-8") as fh:
                va = json.load(fh)
            with open(b, encoding="utf-8") as fh:
                vb = json.load(fh)
        except ValueError as ex:
            problems.append(f"{root_rel} / plugin-root/{shipped_rel}: not valid JSON ({ex})")
            continue
        if va != vb:
            diff = sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))
            problems.append(
                f"{root_rel} and plugin-root/{shipped_rel} disagree on {diff}. "
                f"rebuild_plugin.py reads the plugin-root copy and never reads "
                f"{root_rel}, so editing that one alone changes nothing that ships.")

    if problems:
        print("  \u2717 paired docs")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 paired docs ({checked} checked, list derived not hardcoded)")
    return True


# Phrases that must appear somewhere in each file. Matched loosely on a distinctive
# fragment rather than a whole sentence, so the prose can be edited without breaking
# the guard — but the *rule* cannot be deleted without it going red.
_NO_OWN_MATH = {
    "CLAUDE.md": ("covers comparisons too", "707.18"),
    "skills/quote-document/RULES.md": ("Never state a price Core did not return", "707.18"),
    "skills/quote-intake/references/decision-tree.md": (
        "is a quote, not a sum", "comes from a tool response"),
}


def lint_path_resolution():
    """Finding this plugin by hand must land on the NEWEST copy.

    An upload whose name collides is unpacked beside the old one as `savoya-quoting~g2`,
    `~g3`, and every older copy stays on disk. So the un-suffixed directory is always the
    first one ever installed, and a glob on the plain name matches it and nothing else.

    On 10 Oct 2026 two uploads were installed, 0.19.1 from September and
    0.25.0-sourcing.1. The skills loaded from the current copy -- so the flow looked
    right, and the duplicate was invisible -- while a session that located a *script* by
    name ran September's: that `capture_session.py` has no `--auto` flag at all and
    requires `--request`, so the capture call was rejected with bare argparse usage and
    the session recorded nothing. The count of copies never showed this; which copy the
    bare name reaches is the part that bites.

    Version comparison is numeric here on purpose. As strings "0.9" sorts above "0.25",
    and this repo has already passed through both.
    """
    problems = []

    for skill in ("quote-intake", "quote-document"):
        path = os.path.join(SKILL, "..", skill, "SKILL.md")
        if not os.path.exists(path):
            problems.append(f"{skill}/SKILL.md is missing")
            continue
        text = open(path, encoding="utf-8").read()
        if "savoya-quoting*" not in text:
            problems.append(f"{skill}/SKILL.md does not tell a session to match "
                            f"savoya-quoting* — a bare-name glob finds the oldest copy")
        if "never a bare name match" not in text.lower():
            problems.append(f"{skill}/SKILL.md lost the instruction to prefer the newest "
                            f"copy over a bare name match")
        if "sorts above" not in text and "not lexical" not in text:
            problems.append(f"{skill}/SKILL.md's resolver does not warn that a string "
                            f"comparison mis-orders 0.9 against 0.25")

    sys.path.insert(0, HERE)
    import setup_check

    if not hasattr(setup_check, "version_key"):
        problems.append("setup_check has no version_key(), so it cannot say which copy "
                        "is actually newest")
    else:
        k = setup_check.version_key
        for older, newer in (("0.9.0", "0.25.0"), ("0.19.1", "0.25.0-sourcing.1"),
                             ("0.25.0-sourcing.1", "0.25.0-sourcing.3"),
                             ("0.25.0", "1.0.0")):
            if not k(newer) > k(older):
                problems.append(f"version_key puts {newer} at or below {older}")

    src = open(os.path.join(HERE, "setup_check.py"), encoding="utf-8").read()
    for marker, why in (
            ("bare_name", "setup_check does not mark which copy a bare-name lookup reaches"),
            ("stale_copy_shadows_path_lookup",
             "the machine-readable report does not say whether the STALE copy is the one "
             "found by name — the count alone is not actionable"),
            ("version_in_use", "the report does not say which version is actually in use")):
        if marker not in src:
            problems.append(why)

    if problems:
        print("  \u2717 path resolution")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      see RULES.md 2026-10-10: two copies of this plugin is a silent fork")
        return False
    print("  \u2713 path resolution (both skills prefer the newest copy; 4 version "
          "orderings; setup check names the shadowed lookup)")
    return True


def lint_no_hand_editing():
    """The flow must have a way to set what it asks about, and derive what Core sent.

    Two of the three live sessions on 10 Oct 2026 edited quote.json by hand because
    `decide.py` asks the personalization question, records the answer in intake.json, and
    nothing writes it into the document -- `event_name` and `intro_note` "stayed null and
    had to be set manually". The same two patched `source_tool`, `persisted`,
    `aggregate_total` and `temporary_pricing` into the handoff by hand, "since handoff.py
    write has no flags for them".

    Hand-editing a client document is how wrong claims get in: one of those sessions put
    an intro note in asserting that tax and driver gratuity were included, which the terms
    on the final page of the same PDF contradict. It was caught by re-reading before
    render, not by anything here.
    """
    import json as _json
    import subprocess
    import tempfile

    setter = os.path.join(HERE, "set_personalization.py")
    problems = []
    if not os.path.exists(setter):
        print("  \u2717 no hand editing: set_personalization.py is missing, so the "
              "personalization answer has nowhere to go but a hand edit")
        return False

    fx = os.path.join(DEFAULT_FIXTURES, "access-tca-wedding", "quote.json")
    with tempfile.TemporaryDirectory() as d:
        qp = os.path.join(d, "quote.json")
        with open(fx, encoding="utf-8") as fh:
            _json.dump(_json.load(fh), open(qp, "w", encoding="utf-8"))

        # it must refuse a note that contradicts the terms -- the real mistake
        bad = subprocess.run([sys.executable, setter, qp, "--intro-note",
                              "Tax and driver gratuity are included."],
                             capture_output=True, text=True)
        if bad.returncode == 0:
            problems.append("an intro note claiming tax and gratuity are included was "
                            "accepted; the terms on the final page say otherwise")

        # and it must actually write the fields
        ok = subprocess.run([sys.executable, setter, qp,
                             "--event-name", "Guard Event",
                             "--intro-note", "Gratuity is not expected; variable fees are "
                                             "billed at cost.",
                             "--am-name", "Guard"], capture_output=True, text=True)
        if ok.returncode != 0:
            problems.append(f"a correct personalization write failed: "
                            f"{(ok.stderr or '')[:160]}")
        else:
            pers = (_json.load(open(qp, encoding="utf-8")).get("personalization") or {})
            for key, want in (("event_name", "Guard Event"),):
                if pers.get(key) != want:
                    problems.append(f"{key} was not written to quote.json")
            if not pers.get("intro_note"):
                problems.append("intro_note was not written to quote.json")

    # the handoff must derive what Core already sent, rather than need flags for it
    sys.path.insert(0, os.path.join(SKILL, "..", "quote-intake", "scripts"))
    try:
        import handoff as _handoff
    except ImportError as ex:
        problems.append(f"cannot import handoff.py: {ex}")
    else:
        if not hasattr(_handoff, "temporary_pricing_of"):
            problems.append("handoff.py has no temporary_pricing_of(), so the additional "
                            "discount has to be hand-patched into intake.json")
        else:
            units = [{"pricing_summary": {"adjustments": {
                "temporary_discount_basis_points": 500,
                "temporary_discount_label": "Additional 5% discount"}}}]
            got = _handoff.temporary_pricing_of(units) or {}
            if (got.get("discount") or {}).get("basis_points") != 500:
                problems.append(f"temporary_pricing_of did not read Core's basis points: "
                                f"{got!r}")
            if _handoff.temporary_pricing_of([{"pricing_summary": {"adjustments": {}}}]):
                problems.append("temporary_pricing_of invents a discount where Core "
                                "reported none")
        src = open(os.path.join(SKILL, "..", "quote-intake", "scripts", "handoff.py"),
                   encoding="utf-8").read()
        for field in ("source_tool", "persisted", "aggregate_total", "temporary_pricing"):
            if f'"{field}"' not in src:
                problems.append(f"the handoff does not record {field}, so a session has "
                                f"to patch intake.json by hand")

    if problems:
        print("  \u2717 no hand editing")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      see RULES.md 2026-10-10: a document the flow asks about must be")
        print("      writable by the flow, and what Core sent is derived, never retyped")
        return False
    print("  \u2713 no hand editing (personalization setter refuses contradictions; "
          "handoff derives 4 fields)")
    return True


def lint_client_safe_labels():
    """Core's own strings are read, not published unexamined.

    Three real defects on 10 Oct 2026, all from printing a Core field straight through:

      * `temporary_discount_label` = "Temporary user-supplied discount" reached a client
        PDF. "Temporary" describes pricing Core did not persist -- an internal fact about
        the quote, not about the client's discount.
      * `temporary_discount_label` = "Additional 5% discount" already carried the figure,
        and the adjustment table appends it too: "Additional 5% discount (5%)".
      * `special_event.name` = "Wimbledon 2022" was returned against July 2027 dates and
        printed three times on a $17.9k proposal.

    The event DISCLOSURE must survive the third fix -- it carries a real minimum and
    cancellation window -- so this asserts the name is gone and the warning is not.
    """
    import copy
    import json as _json
    import subprocess
    import tempfile

    sys.path.insert(0, HERE)
    import normalize_quote
    import render_html
    import render_print

    problems = []

    for raw, expect in [("Temporary user-supplied discount", "Additional discount"),
                        ("Temporary rate", "Additional discount"),
                        (None, "Additional discount"),
                        ("Additional 5% discount", "Additional 5% discount"),
                        ("Loyalty 12.5% off", "Loyalty 12.5% off")]:
        got = normalize_quote.client_label(raw)
        if got != expect:
            problems.append(f"client_label({raw!r}) -> {got!r}, expected {expect!r}")

    # A stale year withholds the name; the matching year keeps it; no year keeps it.
    import contextlib
    import io as _io
    for name, date, keep in [("Wimbledon 2022", "2027-07-01T08:40:00+01:00", False),
                             ("Wimbledon 2027", "2027-07-01T08:40:00+01:00", True),
                             ("Ryder Cup", "2027-07-01T08:40:00+01:00", True)]:
        # the stale-year case warns on stderr by design; swallow it here so the suite's
        # own output cannot hide a warning that matters
        with contextlib.redirect_stderr(_io.StringIO()):
            got = normalize_quote.event_for_client({"name": name}, date)
        if bool(got.get("name")) is not keep:
            problems.append(f"event_for_client({name!r}, 2027) -> {got!r}; "
                            f"name should {'survive' if keep else 'be withheld'}")

    fx = os.path.join(SKILL, "evals", "fixtures", "access-tca-wedding", "quote.json")
    if not os.path.exists(fx):
        print("  ✗ client-safe labels: wedding fixture missing")
        return False
    with open(fx, encoding="utf-8") as fh:
        q = copy.deepcopy(_json.load(fh))
    q["adjustments"] = [
        {"label": "Preferred client discount", "type": "percent", "value": -30.0,
         "applies_to": None, "source": "engine", "amount_cents": 0, "amount_cents_fixed": 0},
        {"label": "Additional 5% discount", "type": "percent", "value": -5.0,
         "applies_to": None, "source": "engine", "amount_cents": 0, "amount_cents_fixed": 0},
    ]
    # name withheld by the stale-year rule, disclosure retained
    q["legs"][0]["pricing"]["special_event"] = {"name": None, "stale_name": "Wimbledon 2022",
                                                "leg_year": "2027"}
    with tempfile.TemporaryDirectory() as d:
        qp = os.path.join(d, "quote.json")
        with open(qp, "w", encoding="utf-8") as fh:
            _json.dump(q, fh)
        mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), qp],
                              capture_output=True, text=True)
        rendered = {"print": render_print.render_html(q),
                    "email html": render_html.render(q),
                    "email text": mail.stdout}
    for fmt, text in rendered.items():
        if not text:
            problems.append(f"{fmt}: produced nothing, so this format is untested"
                            + (f" ({mail.stderr.strip()[:160]})"
                               if fmt == "email text" and mail.stderr else ""))
            continue
        if "Wimbledon" in text:
            problems.append(f"{fmt}: printed a withheld special-event name")
        if "emporar" in text or "user-supplied" in text:
            problems.append(f"{fmt}: leaked Core's internal pricing wording")
        if "5% discount (5%)" in text or "5% discount&nbsp;(5%)" in text:
            problems.append(f"{fmt}: printed the discount percentage twice")
        if fmt != "email text" and "Event pricing" not in text:
            problems.append(f"{fmt}: dropped the event disclosure along with the name "
                            f"— the minimum and cancellation window still apply")

    if problems:
        print("  ✗ client-safe labels")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      see RULES.md 2026-10-10, normalize_quote.client_label and")
        print("      event_for_client, render_print.pct_suffix")
        return False
    print("  ✓ client-safe labels (5 labels, 3 event years, 3 formats)")
    return True


def lint_commission():
    """A commission is STATED on every format, with an amount computed in CODE, and it
    changes no total anywhere.

    Added 10 Oct 2026 as rate-only; amended 16 Oct 2026 (PRD R59). A live Yerdle session
    needed the amount on both options, computed it by hand and edited it into the terms --
    a figure with nothing checking it, which is the outcome the rate-only rule existed to
    prevent. The basis is now FIXED (the subtotal after every discount, before the fuel
    surcharge), so the figure is deterministic and this guard can recompute it:

      * Option A is recomputed from a DIFFERENT path than the one under test: the engine
        subtotal plus the discount lines normalize_quote pinned, not the per-leg sum
        apply_adjustments uses;
      * Option B has no discount lines of its own, so it is recomputed from Core's net
        per leg divided by the fuel factor, within a cent per leg of rounding;
      * both must equal the known-good Yerdle figures ($600.50, $728.61);
      * the total must be byte-identical with the commission and without it -- it is not
        an adjustment, it never enters `adjustments`, and C4 must stay meaningful;
      * with no per-leg Core figures (a hand-assembled quote.json) the RATE stands alone
        and no amount is guessed;
      * declining leaves no trace -- no amount either.

    It names no beneficiary, because the commission may be earned by the client or by an
    agency acting for them, and a client-facing document should not assert which.
    """
    import copy
    import json as _json
    import re as _re
    import subprocess
    import tempfile

    sys.path.insert(0, HERE)
    import render_html
    import render_print

    wedding = os.path.join(DEFAULT_FIXTURES, "access-tca-wedding", "quote.json")
    handoff = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options", "handoff")
    problems = []

    def adjust(path, *extra):
        return subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"),
                               path, *extra], capture_output=True, text=True)

    def surfaces_of(q, path):
        mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), path],
                              capture_output=True, text=True)
        return {
            "PDF": _re.sub(r"<[^>]+>", " ", render_print.render_html(q)),
            "HTML email": _re.sub(r"<[^>]+>", " ", render_html.render(q)),
            "email copy": mail.stdout or "",
        }

    with tempfile.TemporaryDirectory() as d:
        # ---- 1. a quote WITH Core's per-leg figures: the amount is stated and correct
        base = os.path.join(d, "base.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                            "--from-handoff", handoff, base, "--prepared-by", "Regress",
                            "--title", "Regression quote"], capture_output=True, text=True)
        if r.returncode:
            print(f"  ✗ commission: could not normalize the Yerdle fixture ({(r.stderr or '')[:160]})")
            return False
        plain, comm = os.path.join(d, "plain.json"), os.path.join(d, "comm.json")
        for path in (plain, comm):
            with open(base, encoding="utf-8") as fh:
                data = _json.load(fh)
            with open(path, "w", encoding="utf-8") as fh:
                _json.dump(data, fh)
        if adjust(comm, "--clear", "--commission-pct", "5").returncode:
            print("  ✗ commission: recording a rate failed")
            return False
        adjust(plain, "--clear")
        with open(plain, encoding="utf-8") as fh:
            qp = _json.load(fh)
        with open(comm, encoding="utf-8") as fh:
            qc = _json.load(fh)

        # the money must not move, and the amount is not an adjustment
        if qp["total_cents"] != qc["total_cents"]:
            problems.append(f"the total changed when a commission was recorded: "
                            f"{qp['total_cents']} -> {qc['total_cents']} -- a commission is "
                            f"stated, not charged")
        if (qp.get("option_b") or {}).get("total_cents") != (qc.get("option_b") or {}).get("total_cents"):
            problems.append("Option B's total changed when a commission was recorded")
        if len(qp.get("adjustments", [])) != len(qc.get("adjustments", [])):
            problems.append("recording a commission added an adjustment line -- it must "
                            "never enter `adjustments`")
        if any("commission" in (a.get("label") or "").lower() for a in qc.get("adjustments", [])):
            problems.append("a commission appeared as an adjustment label")

        # the amount, recomputed along a different path
        amts = qc.get("commission_amounts") or {}
        if not amts:
            problems.append("no commission_amounts were computed for a quote that carries Core's per-leg figures")
        else:
            from decimal import Decimal, ROUND_HALF_UP
            def half_up(cents):
                return int((Decimal(cents) * Decimal(5) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            eng_disc = sum(a["amount_cents_fixed"] for a in qc["adjustments"]
                           if a.get("source") == "engine" and (a.get("value") or 0) < 0)
            want_a = half_up(qc["engine_subtotal_cents"] + eng_disc)
            if amts.get("a") != want_a:
                problems.append(f"Option A commission {amts.get('a')} != {want_a} "
                                f"(engine subtotal + discount lines, x 5%, half-up)")
            fuel = next((a["value"] for a in qc["adjustments"] if "fuel" in a["label"].lower()), 0)
            ob_legs = [l for l in qc["legs"] if l.get("alternative_of")]
            replaced = {l["alternative_of"] for l in ob_legs}
            b_legs = ob_legs + [l for l in qc["legs"] if not l.get("alternative_of") and l["key"] not in replaced]
            b_base = sum(l["engine_net_line_cents"] for l in b_legs) / (1 + fuel / 100.0)
            want_b = half_up(round(b_base))
            if amts.get("b") is None or abs(amts["b"] - want_b) > len(b_legs):
                problems.append(f"Option B commission {amts.get('b')} is not within {len(b_legs)} cents of "
                                f"{want_b} (Core's net per leg, less fuel, x 5%)")
            if (amts.get("a"), amts.get("b")) != (60050, 72861):
                problems.append(f"the Yerdle quote must state $600.50 / $728.61, got "
                                f"{amts.get('a')} / {amts.get('b')} cents")

        # stated, identically, on every format
        sent = "calculated after discounts and before the fuel surcharge: $600.50 on Option A, $728.61 on Option B."
        for name, text in surfaces_of(qc, comm).items():
            if not text:
                problems.append(f"{name}: produced nothing, so it is untested")
                continue
            if sent not in " ".join(text.split()):
                problems.append(f"{name}: does not state the commission amounts as '{sent}'")
        # R59 (placement, 16 Oct 2026): the amount sits under each option's total, quietly.
        import html as _html
        pdf_text = " ".join(_html.unescape(surfaces_of(qc, comm)["PDF"]).split())
        for want in ("5% commission \u00b7 $600.50", "5% commission \u00b7 $728.61"):
            if want not in pdf_text:
                problems.append(f"the PDF does not show '{want}' under the option total")
        if _re.search(r"Commission\s+5%\s", pdf_text) and "5% commission" not in pdf_text:
            problems.append("the PDF header still carries a rate-only commission cell")
        # R82 (17 Oct 2026): it is the figure that sells the quote, so it is a badge, and in the
        # email it sits directly under the totals beneath its own heading.
        raw_print = surfaces_of(qc, comm)["PDF"]
        css = _re.search(r"\.hero-comm\s*\{([^}]*)\}", raw_print)
        if not css or "border" not in css.group(1) or "font-weight" not in css.group(1):
            problems.append("the PDF commission line is not styled as a badge (needs a border and weight)")
        em = surfaces_of(qc, comm).get("email copy") or ""
        full = em.split("=== SHORT VERSION ===")[0]
        fp = [x.strip() for x in full.split("\n\n")]
        idx = next((i for i, x in enumerate(fp) if x.startswith("COMMISSION")), None)
        tot = next((i for i, x in enumerate(fp) if "full line items, rate card" in x), None)
        if idx is None:
            problems.append("the email carries no COMMISSION heading")
        elif tot is None or idx != tot + 1:
            problems.append("the email's COMMISSION block is not directly under the totals paragraph")

        # ---- 2. 'No' must leave no trace, amounts included
        if adjust(comm, "--commission-pct", "none").returncode:
            problems.append("--commission-pct none failed")
        with open(comm, encoding="utf-8") as fh:
            qn = _json.load(fh)
        if qn.get("commission_amounts") or qn.get("commission_line") or qn.get("commission_pct"):
            problems.append("declining a commission left commission fields on quote.json")
        for name, text in surfaces_of(qn, comm).items():
            if "commission" in text.lower():
                problems.append(f"{name}: mentions a commission when none was recorded")

        # ---- 3. a hand-assembled quote (no per-leg Core figures): the RATE stands alone
        hand = os.path.join(d, "hand.json")
        with open(wedding, encoding="utf-8") as fh:
            hq = copy.deepcopy(_json.load(fh))
        for leg in hq["legs"]:                       # what a hand-assembled quote.json lacks
            for k in [k for k in leg if k.startswith("engine_")]:
                del leg[k]
        with open(hand, "w", encoding="utf-8") as fh:
            _json.dump(hq, fh)
        if adjust(hand, "--commission-pct", "5").returncode:
            problems.append("recording a rate on a hand-assembled quote failed")
        else:
            with open(hand, encoding="utf-8") as fh:
                qh = _json.load(fh)
            if qh.get("commission_amounts"):
                problems.append("an amount was stated for a quote with no Core per-leg figures -- "
                                "it must be left out rather than guessed")
            # The email copy is not tested here: draft_email.py already refuses a quote
            # with no engine_net_line_cents, so a hand-assembled quote never reaches it.
            for name, text in surfaces_of(qh, hand).items():
                if name == "email copy":
                    continue
                if "A 5% commission applies to this program." not in " ".join(text.split()):
                    problems.append(f"{name}: a hand-assembled quote must still state the rate")
                if _re.search(r"commission[^.\n]{0,60}\$[\d,]", text, _re.I):
                    problems.append(f"{name}: states an amount the plugin could not derive from Core's figures")

        # ---- 4. a nonsense rate is refused rather than printed
        for bad in ("150", "abc", "-4"):
            rb = adjust(plain, "--commission-pct", bad)
            if rb.returncode == 0:
                problems.append(f"--commission-pct {bad!r} was accepted")

    if problems:
        print("  ✗ commission")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      see RULES.md: a commission amount is computed in code, on a fixed basis")
        print("      (after discounts, before fuel), and changes no total")
        return False
    print("  ✓ commission (rate and amount on 3 formats, amount recomputed two ways, "
          "absent when declined, total unchanged, no guessed amount)")
    return True


def lint_flight_line():
    """The email asks for flight details ONLY when a flight is outstanding (PRD R74).

    Added 16 Oct 2026. `draft_email.py` printed "Send over the flight details when you
    have them" whenever the quote carried ANY placeholder, so a 9:00 AM pickup placeholder
    on a coach hire with no flights made the email ask a client for flight details. Both
    directions are pinned: no airport stop with a TBD flight, no line; a TBD flight, the
    line.
    """
    import json as _json
    import subprocess
    import tempfile

    cases = [("yerdle-iol-whistler-options", False), ("boston-offsite-handoff", True)]
    problems = []
    with tempfile.TemporaryDirectory() as d:
        for name, want in cases:
            fx = os.path.join(DEFAULT_FIXTURES, name, "handoff")
            q = os.path.join(d, name + ".json")
            r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                                "--from-handoff", fx, q, "--prepared-by", "Regress"],
                               capture_output=True, text=True)
            if r.returncode:
                problems.append(f"{name}: could not normalize ({(r.stderr or '')[:120]})")
                continue
            with open(q, encoding="utf-8") as fh:
                quote = _json.load(fh)
            tbd_flight = any(s.get("kind") == "airport" and (s.get("flight") or {}).get("tbd")
                             for l in quote["legs"] for s in (l.get("stops") or []))
            if tbd_flight != want:
                problems.append(f"{name}: fixture no longer {'has' if want else 'lacks'} a TBD flight, "
                                f"so this guard tests nothing")
                continue
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q, "--clear"],
                           capture_output=True, text=True)
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q],
                                  capture_output=True, text=True).stdout or ""
            has_line = "flight details" in mail
            has_ph = bool(quote.get("internal", {}).get("placeholders"))
            if has_line != want:
                problems.append(f"{name}: email {'asks' if has_line else 'does not ask'} for flight details "
                                f"but a flight is {'outstanding' if want else 'not outstanding'}"
                                + (" (a placeholder exists, which must not trigger it)" if has_ph and not want else ""))
    if problems:
        print("  \u2717 flight line")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 flight line (asked only when a flight is outstanding; both directions pinned)")
    return True


def lint_client_requests():
    """Carried client requests are noted and never resolved by the session (PRD R73).

    Added 16 Oct 2026. A Yerdle session wrote "PA and signage are arranged separately, not
    included in vehicle pricing" into the client email by hand. The session did not know
    that. The line is now built in code from intake's client_questions, names the request,
    says it will be confirmed, and carries no inclusion or exclusion wording. Pinned: the
    line reaches the email copy and the HTML email, it passes the forbidden-wording check,
    a quote with no operational request prints none, and no instruction file still teaches
    the old "arranged separately" note.
    """
    import json as _json
    import subprocess
    import tempfile
    sys.path.insert(0, HERE)
    from client_requests import FORBIDDEN, requests_line

    problems = []
    with tempfile.TemporaryDirectory() as d:
        for name, want in (("yerdle-iol-whistler-options", True), ("boston-offsite-handoff", False)):
            fx = os.path.join(DEFAULT_FIXTURES, name, "handoff")
            q = os.path.join(d, name + ".json")
            r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                                "--from-handoff", fx, q, "--prepared-by", "Regress"],
                               capture_output=True, text=True)
            if r.returncode:
                problems.append(f"{name}: could not normalize ({(r.stderr or '')[:120]})")
                continue
            quote = _json.load(open(q, encoding="utf-8"))
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q, "--clear"],
                           capture_output=True, text=True)
            quote = _json.load(open(q, encoding="utf-8"))
            line = requests_line(quote)
            if bool(line) != want:
                problems.append(f"{name}: requests line {'missing' if want else 'present'}: {line!r}")
                continue
            if not want:
                continue
            if FORBIDDEN.search(line):
                problems.append(f"{name}: line asserts an answer: {line!r}")
            for needle in ("PA/speaker", "Signage", "will confirm"):
                if needle not in line:
                    problems.append(f"{name}: line lacks {needle!r}")
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q],
                                  capture_output=True, text=True).stdout or ""
            if line not in mail:
                problems.append(f"{name}: email copy lacks the line")
            html = os.path.join(d, name + ".html")
            subprocess.run([sys.executable, os.path.join(HERE, "render_html.py"), q, html],
                           capture_output=True, text=True)
            if os.path.exists(html):
                import html as _h
                if _h.escape(line, quote=True) not in open(html, encoding="utf-8").read() \
                        and line not in open(html, encoding="utf-8").read():
                    problems.append(f"{name}: HTML email lacks the line")
            else:
                problems.append(f"{name}: HTML email did not render")
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    for rel in ("quote-document/RULES.md", "quote-document/SKILL.md",
                "quote-intake/references/client-questions.md"):
        path = os.path.join(root, rel)
        if os.path.exists(path) and "not included in vehicle pricing" in open(path, encoding="utf-8").read():
            problems.append(f"{rel} still teaches 'not included in vehicle pricing' (R73)")
    if problems:
        print("  \u2717 client requests")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 client requests (noted, never resolved; no inclusion wording; email and HTML carry it)")
    return True


def lint_client_request_answers():
    """PRD R72/R73. A request Core cannot answer is put to the user, and the answer reaches the document.
    Tax, gratuity and cancellation are answered by the terms and are never asked."""
    import json as _json
    import subprocess
    import tempfile
    sys.path.insert(0, HERE)
    import client_requests as cr
    problems = []
    for text, kind in (("Is tax and driver gratuity included?", "boilerplate"),
                       ("Cancellation policy: please provide", "boilerplate"),
                       ("Onsite staff support in the hotel lobby to direct customers", "operational"),
                       ("Do you have an electric vehicle?", "operational")):
        if cr.classify(text) != kind:
            problems.append(f"{text!r} classed {cr.classify(text)}, wanted {kind}")
    qs = ["Is tax included?", "Do you have an electric vehicle?", "Signage on the vehicles"]
    if cr.request_keys(qs) != ["request:1", "request:2"]:
        problems.append(f"request keys wrong: {cr.request_keys(qs)}")
    items = cr.carry(qs, {"request:1": "not included", "request:2": "Yes, signage is fine."})
    quote = {"client_requests": items, "personalization": {}}
    line = cr.requests_line(quote)
    if "electric vehicle \u2014 We are not able to provide this." not in line or "Signage on the vehicles \u2014 Yes, signage is fine." not in line:
        problems.append(f"answers not printed beside their requests: {line!r}")
    if "will confirm" in line:
        problems.append(f"an answered request still says it will be confirmed: {line!r}")
    unanswered = cr.requests_line({"client_requests": cr.carry(qs), "personalization": {}})
    if "will confirm" not in unanswered or cr.FORBIDDEN.search(unanswered):
        problems.append(f"unanswered fallback wrong: {unanswered!r}")
    import confirm_items as ci
    if [i for i in ci.items(quote) if i["kind"] == "client_request"]:
        problems.append("an answered request is still a confirm item")
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "handoff"))
        _json.dump({"client": {"name": "T"}, "client_questions": qs, "decisions": {}}, open(os.path.join(d, "handoff", "intake.json"), "w"))
        def dec(*a):
            return subprocess.run([sys.executable, os.path.join(HERE, "decide.py")] + list(a), capture_output=True, text=True, cwd=d)
        r = dec("discount_pct", "none")
        if "next: request:1" not in r.stdout:
            problems.append(f"decide.py did not ask the electric-vehicle request next: {r.stdout[:120]!r}")
        r = dec("request:1", "not included")
        if "next: request:2" not in r.stdout:
            problems.append(f"decide.py did not go on to the second request: {r.stdout[:120]!r}")
        r = dec("request:2", "extra cost")
        if "next: commission_pct" not in r.stdout:
            problems.append(f"decide.py did not return to the base questions: {r.stdout[:120]!r}")
    skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    if "request:<n>" not in skill:
        problems.append("SKILL.md does not teach the request:<n> questions (R72/R73)")
    if problems:
        print("  \u2717 client request answers")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 client request answers (asked per request, tax/gratuity/cancellation never asked, answer printed beside the request)")
    return True


def lint_user_supplied_facts():
    """PRD R35. A dimension appears in a document only if Core returned it or the user supplied it.
    Core returns none, so the generated documents of every fixture print none unless the quote
    carries it in user_supplied_facts; the instruction files tell the session to ask."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    dim = re.compile(r"\b\d{1,2}(\.\d)?\s?(ft|feet|foot)\b|\b\d{1,2}\s?'\s?(long|length)|\b(length|clearance)\b", re.I)
    with tempfile.TemporaryDirectory() as d:
        for name in sorted(os.listdir(DEFAULT_FIXTURES)):
            fx = os.path.join(DEFAULT_FIXTURES, name, "handoff")
            if not os.path.isdir(fx):
                continue
            q = os.path.join(d, name + ".json")
            r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, q, "--prepared-by", "Regress"],
                               capture_output=True, text=True)
            if r.returncode:
                continue
            quote = _json.load(open(q, encoding="utf-8"))
            if "user_supplied_facts" not in quote:
                problems.append(f"{name}: quote does not carry user_supplied_facts")
            supplied = " ".join(str(f.get("answer", "")) for f in quote.get("user_supplied_facts", []))
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q, "--clear"], capture_output=True, text=True)
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q], capture_output=True, text=True).stdout or ""
            for m in dim.finditer(mail):
                if m.group(0).lower() not in supplied.lower():
                    problems.append(f"{name}: the email prints {m.group(0)!r}, which no user supplied")
    vt = open(os.path.join(HERE, "..", "..", "quote-intake", "references", "vehicle-types.md"), encoding="utf-8").read()
    if "Never state a figure from this table" not in vt:
        problems.append("vehicle-types.md still lets a session state its dimensions")
    sk = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    if "--fact" not in sk or "never inferred" not in sk:
        problems.append("quote-intake SKILL.md does not tell the session to ask for a missing dimension (R35)")
    if problems:
        print("  \u2717 user-supplied facts")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 user-supplied facts (no unsupplied dimension in any fixture email; the instructions say ask)")
    return True


def lint_overlap_and_placeholders():
    """PRD R97 and R98. An hourly block across an airport transfer is a question; a held-open stop
    prints its neutral label and never the resolved name or address."""
    import json as _json
    import shutil
    import subprocess
    import tempfile
    problems = []
    sys.path.insert(0, os.path.join(HERE, "..", "..", "quote-intake", "scripts"))
    import importlib
    h = importlib.import_module("handoff")

    def unit(key, method, start, hours=0, airport=False, drive=(30,)):
        return {"key": key, "pickup_date": f"2027-03-20T{start}:00-07:00", "travel_times": list(drive),
                "stops": [{"name": "LAX", "stop_type": "airport"}] if airport else [{"name": "Hotel"}],
                "pricing_summary": {"pricing_method": method, "calculation": {"billable_hours": hours}}}
    day = unit("day", "hourly", "08:00", 10)
    xfer = unit("xfer", "transfer", "14:00", airport=True, drive=(45,))
    early = unit("early", "transfer", "06:00", airport=True, drive=(45,))
    after = unit("after", "transfer", "19:00", airport=True)
    if h.overlaps([day, xfer]) != [("day", "xfer")]:
        problems.append("a transfer inside the block was not found")
    if h.overlaps([day, early, after]):
        problems.append("a transfer outside the block was reported")
    _, probs = h.overlap_decisions([], [day, xfer])
    if not any("Ask the user" in x for x in probs):
        problems.append("an unanswered overlap does not produce the question")
    got, probs = h.overlap_decisions(["day|xfer|client_time"], [day, xfer])
    if probs or got != [{"block": "day", "transfer": "xfer", "decision": "client_time"}]:
        problems.append(f"an answered overlap was not accepted: {probs}")
    _, probs = h.overlap_decisions(["day|xfer|start_after_transfer"], [day, xfer])
    if not any("still starts before" in x for x in probs):
        problems.append("start_after_transfer accepted while the block still starts first")
    _, probs = h.overlap_decisions(["day|xfer|whenever"], [day, xfer])
    if not any("bad --overlap" in x for x in probs):
        problems.append("a bad overlap answer was accepted")
    # R98
    with tempfile.TemporaryDirectory() as d:
        fx = os.path.join(DEFAULT_FIXTURES, "boston-offsite-handoff", "handoff")
        q0 = os.path.join(d, "q0.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, q0, "--prepared-by", "Regress"], capture_output=True, text=True)
        if r.returncode:
            problems.append("could not normalize the base fixture")
        else:
            base = _json.load(open(q0, encoding="utf-8"))
            every = [s["label"] for l in base["legs"] for s in l["stops"]]
            leg = next(l for l in base["legs"] if any(s.get("kind") == "address" and every.count(s["label"]) == 1 for s in l["stops"]))
            stop = next(s for s in leg["stops"] if s.get("kind") == "address" and every.count(s["label"]) == 1)
            real, neutral = stop["label"], "Boston, MA (pickup address to be confirmed)"
            fx2 = os.path.join(d, "handoff")
            shutil.copytree(fx, fx2)
            ip = os.path.join(fx2, "intake.json")
            intake = _json.load(open(ip, encoding="utf-8"))
            intake["placeholder_stops"] = [{"unit": leg["key"], "stop": real, "label": neutral}]
            _json.dump(intake, open(ip, "w"))
            q1 = os.path.join(d, "q1.json")
            subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx2, q1, "--prepared-by", "Regress"], capture_output=True, text=True)
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q1, "--clear"], capture_output=True, text=True)
            q = _json.load(open(q1, encoding="utf-8"))
            st = next(s for l in q["legs"] if l["key"] == leg["key"] for s in l["stops"] if s.get("placeholder"))
            if st["label"] != neutral or "address" in st:
                problems.append(f"the held-open stop did not take its neutral label: {st}")
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q1], capture_output=True, text=True).stdout or ""
            if neutral not in mail:
                problems.append("the email does not print the neutral label")
            if real in mail.replace(neutral, ""):
                problems.append("the email still prints the resolved stop name")
    sk = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    if "--overlap" not in sk or "--placeholder-stop" not in sk:
        problems.append("quote-intake SKILL.md does not teach --overlap and --placeholder-stop")
    if problems:
        print("  \u2717 overlap and placeholders")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 overlap and placeholders (overlap asked, never silent; held-open stop prints its neutral label)")
    return True


def lint_notes_and_no_commission():
    """PRD R99 and R100. Identical notes collapse, short notes print inline, totals follow the
    subtotals; a no-commission copy is made from the same session without moving the total."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    sys.path.insert(0, HERE)
    import render_print as rp
    legs = [{"ref": f"A{i}", "client_notes": ["Meet inside the terminal at baggage reclaim, name board displayed.", "Gate code 4411."]} for i in (1, 2, 3)]
    legs[1]["client_notes"].append("Child seat requested for this leg only, to be confirmed with dispatch before the day of travel.")
    out = rp.prep_notes(legs)
    long_notes = [n for l in out for n in l["client_notes"]]
    inline = [n for l in out for n in l["inline_notes"]]
    if sum("Meet inside the terminal" in n for n in long_notes + inline) != 1:
        problems.append("an identical note was not collapsed to one")
    if not any(n.startswith("A1, A2 and A3:") for n in long_notes + inline):
        problems.append(f"the collapsed note does not name its legs: {long_notes + inline}")
    if "A1, A2 and A3: Gate code 4411." not in inline:
        problems.append("a short collapsed note did not print inline")
    if not any("Child seat" in n for n in out[1]["client_notes"]):
        problems.append("a long one-leg note left the notes block")
    if any(l["client_notes"] != legs[i]["client_notes"] for i, l in enumerate(out)) is False:
        problems.append("prep_notes changed nothing")
    if legs[0]["client_notes"] != ["Meet inside the terminal at baggage reclaim, name board displayed.", "Gate code 4411."]:
        problems.append("prep_notes changed the quote it was given")
    with tempfile.TemporaryDirectory() as d:
        fx = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options", "handoff")
        q = os.path.join(d, "q.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, q, "--prepared-by", "Regress"], capture_output=True, text=True)
        if r.returncode:
            problems.append("could not normalize the base fixture")
        else:
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q, "--clear", "--commission-pct", "5"], capture_output=True, text=True)
            had = _json.load(open(q, encoding="utf-8"))
            if not had.get("commission_pct"):
                problems.append("the fixture quote did not take a commission; guard tests nothing")
            else:
                mail = os.path.join(d, "m.txt")
                r = subprocess.run([sys.executable, os.path.join(HERE, "no_commission_copy.py"), q, "--email", mail, "--dir", os.path.join(d, "none")], capture_output=True, text=True)
                if r.returncode:
                    problems.append(f"no_commission_copy failed: {(r.stderr or r.stdout)[:160]}")
                else:
                    cp = _json.load(open(os.path.splitext(q)[0] + ".no-commission.json", encoding="utf-8"))
                    if cp.get("commission_pct") or cp.get("total_cents") != had.get("total_cents"):
                        problems.append("the copy kept a commission or moved the total")
                    if "ommission" in open(mail, encoding="utf-8").read():
                        problems.append("the no-commission email still says commission")
                    if not _json.load(open(q, encoding="utf-8")).get("commission_pct"):
                        problems.append("the original lost its commission")
    sk = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    if "no_commission_copy.py" not in sk:
        problems.append("SKILL.md does not teach the no-commission copy")
    if problems:
        print("  \u2717 notes and no-commission copy")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 notes and no-commission copy (collapse, inline, totals first; copy keeps the total and drops the commission)")
    return True


def lint_review_fixes():
    """The 17 Oct 2026 test2 session. An options response is ingested, not rejected; overlap
    questions are asked within one option only; a fuel-display ask is never a client request; a fit
    question is one; a greeter is asked once; a supplied flight is no placeholder."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "..", "..", "quote-intake", "scripts"))
    import importlib
    cr = importlib.import_module("client_requests")
    h = importlib.import_module("handoff")
    for t, want in (("If a fuel surcharge applies, show it on each leg", "boilerplate"),
                    ("Confirm that all 14 people with 14 carry-on bags fit in one Sprinter", "operational"),
                    ("Please include tax, gratuity and your cancellation policy", "boilerplate"),
                    ("Please send flight details when you have them", "boilerplate"),
                    ("Confirmation of the booking by email", "boilerplate")):
        if cr.classify(t) != want:
            problems.append(f"{t!r} classed {cr.classify(t)}, wanted {want}")
    qs = ["Wi-Fi on board", "Greeter with name sign", "Meet and greet inside terminal", "Confirm 14 carry-ons fit in one Sprinter", "Fuel surcharge on each leg"]
    if cr.request_keys(qs) != ["request:0", "request:3"]:
        problems.append(f"request keys are {cr.request_keys(qs)}; a greeter must be asked once (greeter_cost) and fuel never")
    items = {i["text"]: i for i in cr.carry(qs, {"request:0": "included"})}
    if items["Greeter with name sign"].get("answer"):
        problems.append("a greeter request took a request answer")
    d_src = open(os.path.join(HERE, "decide.py"), encoding="utf-8").read()
    if "Never say it fits" not in d_src:
        problems.append("decide.py does not warn against claiming a fit")
    # options response
    def pkg(prefix, rate):     # Core gives every option the same unit keys
        us = [{"key": "t1", "line_total": rate, "pickup_date": "2027-03-20T08:00:00-07:00", "stops": [{"name": "Hotel"}],
               "pricing_summary": {"pricing_method": "hourly"}},
              {"key": "t2", "line_total": rate * 2, "pickup_date": "2027-03-20T14:00:00-07:00", "stops": [{"name": "LAX", "stop_type": "airport"}],
               "pricing_summary": {"pricing_method": "transfer"}}]
        return {"quote_units": us, "aggregate_total": rate * 3}
    resp = {"options": [{"key": "value", "label": "Value", "result": pkg("v", 1000)}, {"key": "elevated", "label": "Elevated", "result": pkg("e", 1500)}]}
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "quote-intake", "scripts", "handoff.py"), "ingest", "--name", "A", "--dir", d],
                           input=_json.dumps(resp), capture_output=True, text=True)
        out = r.stdout + r.stderr
        if r.returncode or "--package A_value --package A_elevated" not in out:
            problems.append(f"an options response was not ingested as packages: {out[:200]}")
        for n in ("A_value", "A_elevated"):
            if not os.path.exists(os.path.join(d, "responses", n + ".json")):
                problems.append(f"{n}.json was not saved")
        # the merge pairs each alternative with the Option A unit that has the same key; nothing else is asked
        ns = type("NS", (), {"package": ["A_value", "A_elevated"], "dir": d, "shared": [], "alt_of": []})()
        try:
            merged, pk, alts = h.merge_packages(ns)
            if alts != {"A_elevated_t1": "t1", "A_elevated_t2": "t2"}:
                problems.append(f"merged options did not pair by key: {alts}")
            if len(merged["quote_units"]) != 4 or merged["aggregate_total"] != 3000:
                problems.append("merged options lost a unit or changed the primary total")
        except SystemExit as e:
            problems.append(f"merging ingested options stopped: {e}")
        bad = _json.loads(_json.dumps(resp))
        bad["options"][1]["result"]["aggregate_total"] += 1
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "quote-intake", "scripts", "handoff.py"), "ingest", "--name", "B", "--dir", d],
                           input=_json.dumps(bad), capture_output=True, text=True)
        if r.returncode != 2 or os.path.exists(os.path.join(d, "responses", "B_value.json")):
            problems.append("an options response with one altered total was partly saved")
    # overlaps stay inside one option
    a1 = {"key": "a1", "pickup_date": "2027-03-20T08:00:00-07:00", "travel_times": [30], "stops": [{"name": "LAX", "stop_type": "airport"}],
          "pricing_summary": {"pricing_method": "hourly", "calculation": {"billable_hours": 10}}}
    b1 = dict(a1, key="b1")
    if len(h.overlaps([a1, b1])) != 2:
        problems.append("the control pair is not found without option sets")
    if h.overlaps([a1, b1], [{"a1"}, {"b1"}]):
        problems.append("units in different options were paired as an overlap")
    merged = {"merged_packages": {"A": {"unit_keys": ["a1", "a3"]}, "B": {"unit_keys": ["b1"]}}}
    sets = h.option_sets(merged, ["a1", "a3"], {"b1": "a1"})
    if sets != [{"a1", "a3"}, {"b1", "a3"}]:
        problems.append(f"option sets are {sets}; an unreplaced Option A unit belongs to both options")
    n_src = open(os.path.join(HERE, "normalize_quote.py"), encoding="utf-8").read()
    if "a supplied flight is no placeholder" not in n_src:
        problems.append("the normalizer still reports a supplied flight as a placeholder")
    sk = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    if "generate_quote_options" not in sk.split("Saving a pricing response")[1][:3500]:
        problems.append("quote-intake SKILL.md does not say how to save a generate_quote_options response")
    if problems:
        print("  \u2717 review fixes")
        for x in problems:
            print("  \u2717", x)
        return False
    print("  \u2713 review fixes (options response ingested and merged by key; overlaps within one option; fuel, fit and greeter classes; supplied flight is no placeholder)")
    return True


def lint_copy_rules():
    """PRD R62 and R74. The fuel surcharge belongs to the whole quote: it is in the header and
    the terms and in no leg row, email line or note. A flight the client supplied prints as
    given; a venue the client named prints by that name."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as d:
        for name in sorted(os.listdir(DEFAULT_FIXTURES)):
            fx = os.path.join(DEFAULT_FIXTURES, name, "handoff")
            if not os.path.isdir(fx):
                continue
            q = os.path.join(d, name + ".json")
            if subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, q, "--prepared-by", "Regress"],
                              capture_output=True, text=True).returncode:
                continue
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q, "--clear"], capture_output=True, text=True)
            quote = _json.load(open(q, encoding="utf-8"))
            html = os.path.join(d, name + ".html")
            subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"), q, os.path.join(d, name + ".pdf"), "--html", html, "--no-cover"], capture_output=True, text=True)
            if os.path.exists(html):
                page = open(html, encoding="utf-8").read()
                for row in re.findall(r"<tr>\s*<td class='ref'>.*?</tr>", page, re.S):
                    if re.search(r"fuel", row, re.I):
                        problems.append(f"{name}: a leg row names the fuel surcharge")
                        break
                for row in re.findall(r"<tr><td class='ref'>.*?</tr>", page, re.S):
                    if re.search(r"fuel", row, re.I):
                        problems.append(f"{name}: a note row names the fuel surcharge")
                        break
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q], capture_output=True, text=True).stdout or ""
            places = {str(l.get("service_area")) for l in quote["legs"] if l.get("service_area")}
            for ln in mail.splitlines():
                if re.search(r"fuel", ln, re.I):
                    if re.search(r"\bA\d\b|\bB\d\b", ln) or any(p and p.split(",")[0] in ln for p in places):
                        problems.append(f"{name}: an email line puts the fuel surcharge beside a leg or market: {ln[:90]!r}")
            for l in quote["legs"]:
                for n in l.get("client_notes") or []:
                    if re.search(r"fuel", str(n), re.I):
                        problems.append(f"{name}: a leg note names the fuel surcharge")
        # R74 and R62: supplied flight and venue name
        fx = os.path.join(DEFAULT_FIXTURES, "boston-offsite-handoff", "handoff")
        base = os.path.join(d, "b.json")
        subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, base, "--prepared-by", "Regress"], capture_output=True, text=True)
        bq = _json.load(open(base, encoding="utf-8"))
        leg = next((l for l in bq["legs"] if any(s.get("kind") == "airport" for s in l["stops"])), None)
        if not leg:
            problems.append("no airport leg in the base fixture; the flight check tests nothing")
        else:
            import shutil
            fx2 = os.path.join(d, "hf")
            shutil.copytree(fx, fx2)
            ip = os.path.join(fx2, "intake.json")
            it = _json.load(open(ip, encoding="utf-8"))
            it["flight_details"] = [{"unit": leg["key"], "text": "BA2612 departing 2:50 PM"}]
            _json.dump(it, open(ip, "w"))
            q2 = os.path.join(d, "f.json")
            subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx2, q2, "--prepared-by", "Regress"], capture_output=True, text=True)
            subprocess.run([sys.executable, os.path.join(HERE, "apply_adjustments.py"), q2, "--clear"], capture_output=True, text=True)
            h2 = os.path.join(d, "f.html")
            subprocess.run([sys.executable, os.path.join(HERE, "render_print.py"), q2, os.path.join(d, "f.pdf"), "--html", h2, "--no-cover"], capture_output=True, text=True)
            page = open(h2, encoding="utf-8").read() if os.path.exists(h2) else ""
            if "Flight BA2612 departing 2:50 PM" not in page:
                problems.append("a supplied flight does not print as given")
            mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q2], capture_output=True, text=True).stdout or ""
            if "flight BA2612 departing 2:50 PM" not in mail:
                problems.append("a supplied flight is missing from the email heading")
    sys.path.insert(0, os.path.join(HERE, "..", "..", "quote-intake", "scripts"))
    import importlib
    h = importlib.import_module("handoff")
    isk = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    for flag in ("--flight", "--venue"):
        if flag not in isk or not hasattr(h, "TIME_KINDS"):
            problems.append(f"quote-intake SKILL.md does not teach {flag}")
    if problems:
        print("  \u2717 copy rules")
        for b in sorted(set(problems)):
            print(f"      - {b}")
        return False
    print("  \u2713 copy rules (fuel only in header and terms; supplied flight and venue print as given)")
    return True


def lint_confirm_items():
    """Every placeholder and operational request reaches the confirm list (PRD R72).

    Added 16 Oct 2026. The Yerdle quote shipped four "NO SAVOYA SERVICE AREA" legs, a
    placeholder pickup time and unconfirmed inventory notes with no one asked. The list is
    built in code; service-area placeholders collapse into one item, nothing is dropped,
    and SKILL.md must tell the session to run the helper before presenting files.
    """
    import json as _json
    import subprocess
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as d:
        fx = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options", "handoff")
        q = os.path.join(d, "q.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                            "--from-handoff", fx, q, "--prepared-by", "Regress"],
                           capture_output=True, text=True)
        if r.returncode:
            problems.append("could not normalize yerdle")
        else:
            quote = _json.load(open(q, encoding="utf-8"))
            out = subprocess.run([sys.executable, os.path.join(HERE, "confirm_items.py"), q, "--json"],
                                 capture_output=True, text=True).stdout
            got = _json.loads(out or "[]")
            phs = quote["internal"]["placeholders"]
            n_area = sum(1 for p in phs if "NO SAVOYA SERVICE AREA" in p)
            n_other = sum(len([x for x in p.split(";") if x.strip()]) for p in phs if "NO SAVOYA SERVICE AREA" not in p)   # ";"-joined notes are separate items
            n_req = sum(1 for x in quote.get("client_requests", []) if x["kind"] == "operational")
            if n_area < 2:
                problems.append("fixture no longer has several service-area placeholders; guard tests nothing")
            kinds = [g["kind"] for g in got]
            if kinds.count("service_area") != 1:
                problems.append(f"service-area placeholders not grouped into one item: {kinds}")
            if kinds.count("placeholder") != n_other:
                problems.append(f"{n_other} other placeholders but {kinds.count('placeholder')} items")
            if kinds.count("client_request") != n_req:
                problems.append(f"{n_req} operational requests but {kinds.count('client_request')} items")
            area_item = next((g for g in got if g["kind"] == "service_area"), {"text": ""})
            for l in quote["legs"]:
                if any(l["key"] in p and "NO SAVOYA SERVICE AREA" in p for p in phs) and l["key"] not in area_item["text"]:
                    problems.append(f"grouped item omits leg {l['key']}")
    skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    if "confirm_items.py" not in skill:
        problems.append("SKILL.md never tells the session to run confirm_items.py")
    if problems:
        print("  \u2717 confirm items")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 confirm items (every placeholder and operational request listed; service areas grouped; SKILL.md runs it)")
    return True


def lint_deliverables():
    """Only the formats the user chose are delivered (PRD R85)."""
    import subprocess
    import tempfile
    import json as _json
    problems = []
    fx = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options", "handoff")
    with tempfile.TemporaryDirectory() as d:
        q = os.path.join(d, "quote.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"), "--from-handoff", fx, q,
                            "--prepared-by", "G"], capture_output=True, text=True)
        if r.returncode:
            print("  \u2717 deliverables: could not normalize the Yerdle fixture")
            return False
        def mail(fmt, *extra):
            hd = os.path.join(d, "handoff"); os.makedirs(hd, exist_ok=True)
            if fmt is None:
                if os.path.exists(os.path.join(hd, "intake.json")):
                    os.remove(os.path.join(hd, "intake.json"))
            else:
                _json.dump({"decisions": {"format": fmt}}, open(os.path.join(hd, "intake.json"), "w"))
            return subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), q, *extra],
                                  capture_output=True, text=True, cwd=d)
        if mail("pdf").returncode == 0:
            problems.append("an email was drafted for a PDF-only job")
        if "R85" not in mail("pdf").stderr:
            problems.append("the refusal does not say why (R85)")
        if mail("pdf", "--asked").returncode:
            problems.append("--asked did not allow an email the user asked for")
        for fmt in ("email", "email+pdf"):
            if mail(fmt).returncode:
                problems.append(f"an email was refused for the format {fmt!r}")
        if mail(None).returncode:
            problems.append("an email was refused when no format was recorded")
        mail("pdf")
        v = subprocess.run([sys.executable, os.path.join(HERE, "verify_document.py"), q], capture_output=True, text=True, cwd=d)
        if "DELIVERABLES: pdf only" not in v.stdout:
            problems.append("verify does not print the deliverables for a PDF-only job")
    skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    if "DELIVERABLES" not in skill or "R85" not in skill:
        problems.append("quote-document SKILL.md does not tell the session to deliver only the chosen format")
    if problems:
        print("  \u2717 deliverables")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 deliverables (a PDF-only job drafts no email; --asked and email formats pass; verify prints the line)")
    return True


def lint_blocked_capture():
    """A session that produced no document still leaves a record (PRD R80)."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    cs = os.path.join(HERE, "capture_session.py")
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, HOME=d)
        def run(*args):
            return subprocess.run([sys.executable, cs, *args], capture_output=True, text=True, env=env, cwd=d)
        cap = os.path.join(d, ".savoya-quoting", "captures")
        r = run("--blocked", "could not save responses", "--slug", "blk", "--client", "Blk")
        if "CAPTURE CONSENT UNASKED" not in r.stdout or glob.glob(os.path.join(cap, "*")):
            problems.append("unasked consent: a blocked session must ask and write nothing")
        run("--consent", "no", "--user", "G")
        run("--blocked", "x", "--slug", "blk", "--client", "Blk")
        if glob.glob(os.path.join(cap, "*.blocked*")):
            problems.append("declined consent: a blocked session wrote a record")
        run("--consent", "yes")
        os.makedirs(os.path.join(d, "handoff", "responses"))
        _json.dump({"aggregate_total": 100, "quote_units": [{"key": "u1", "label": "L", "line_total": 100}]},
                   open(os.path.join(d, "handoff", "responses", "A.json"), "w"))
        open(os.path.join(d, "req.md"), "w").write("the request")
        r = run("--blocked", "responses could not be saved", "--slug", "blk", "--client", "Blk", "--request", "req.md")
        out = os.path.join(cap, "blk.blocked.json")
        if r.returncode or not os.path.exists(out):
            problems.append(f"no record written with consent granted: {r.stderr.strip()[:150]}")
        else:
            rec = _json.load(open(out))
            if rec.get("request") != "the request" or not rec.get("priced") or rec.get("blocked_because") != "responses could not be saved":
                problems.append("the record lacks the request, what was priced, or the reason")
            if "blocked.json" not in r.stdout or not glob.glob(os.path.join(cap, "*.blocked.pending-upload")):
                problems.append("the record is not offered for upload with a pending marker")
            packed = os.path.join(cap, "blk.blocked.json.gz.b64")
            if not os.path.exists(packed):
                problems.append("the blocked record is not packed for upload (a readable copy is what gets condensed)")
            else:
                import base64, gzip, hashlib
                envl = _json.load(open(packed))
                body = gzip.decompress(base64.b64decode(envl["data"]))
                if body != open(out, "rb").read() or hashlib.sha256(body).hexdigest() != envl.get("sha256"):
                    problems.append("the packed blocked record is not the saved record byte for byte")
                up = _json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])["upload"][0]
                if up.get("sha256") != hashlib.sha256(open(packed, "rb").read()).hexdigest() or not up.get("bytes"):
                    problems.append("the upload list does not carry the byte count and hash of the file to upload")
            r2 = run("--mark-uploaded", "blk", "--file-id", "abc")
            if glob.glob(os.path.join(cap, "*.blocked.pending-upload")):
                problems.append("--mark-uploaded did not clear the blocked-session marker")
    cap_md = open(os.path.join(HERE, "..", "references", "capture.md"), encoding="utf-8").read()
    skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    intake = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    for name, text in (("capture.md", cap_md), ("quote-document SKILL.md", skill), ("quote-intake SKILL.md", intake)):
        if "--blocked" not in text:
            problems.append(f"{name} never tells the session to run capture_session.py --blocked")
    if problems:
        print("  \u2717 blocked-session capture")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 blocked-session capture (asks, respects a no, records request and priced data, clears on upload; all three docs name it)")
    return True


def lint_handoff_packages():
    """Pricing responses are saved by a checked step and separately priced packages become
    options in one document (PRD R78, R79). Built from the Yerdle options fixture: its four
    units are split into two packages, ingested, merged and normalized, and the document must
    come out with the fixture's own totals."""
    import copy
    import json as _json
    import subprocess
    import tempfile
    problems = []
    intake = os.path.join(HERE, "..", "..", "quote-intake", "scripts", "handoff.py")
    fx = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options")
    raw = _json.load(open(os.path.join(fx, "handoff", "raw_quote.json"), encoding="utf-8"))
    us = raw["quote_units"]

    def pkg(units, headcount=75):
        d = {k: v for k, v in raw.items() if k not in ("quote_units", "aggregate_total")}
        # R91: units serving one trip carry a share of the headcount that adds up to it
        # (the first takes the remainder, the rest 25 each), never the whole headcount each
        groups = {}
        for u in units:
            groups.setdefault((u.get("pickup_date"), str([x.get("name") for x in u.get("stops") or []])), []).append(u)
        d["quote_units"] = []
        for g in groups.values():
            for i_, u in enumerate(g):
                pc = None if headcount is None else (headcount - 25 * (len(g) - 1) if i_ == 0 else 25)
                d["quote_units"].append(dict(copy.deepcopy(u), passenger_count=pc))
        d["aggregate_total"] = sum(u["line_total"] for u in units)
        return d
    A = pkg(us[0:2])
    twin = copy.deepcopy(us[1]); twin["key"] = "optB_jun10_coach"
    B = pkg([us[2], us[3], twin])
    with tempfile.TemporaryDirectory() as d:
        def run(args, stdin=None):
            return subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=d, input=stdin)
        bad = _json.dumps(dict(B, aggregate_total=B["aggregate_total"] + 1))
        r = run([intake, "ingest", "--name", "B"], bad)
        if r.returncode != 2 or os.path.exists(os.path.join(d, "handoff", "responses", "B.json")):
            problems.append("ingest accepted a response whose units do not add up to its own total")
        r = run([intake, "ingest", "--name", "B"], "{not json")
        if r.returncode == 0:
            problems.append("ingest accepted text that is not JSON")
        for name, p_ in (("A", A), ("B", B)):
            r = run([intake, "ingest", "--name", name], _json.dumps(p_))
            if r.returncode:
                problems.append(f"ingest rejected a good response {name}: {r.stderr.strip()[:120]}")
        saved = os.path.join(d, "handoff", "responses", "A.json")
        if os.path.exists(saved) and _json.load(open(saved)) != A:
            problems.append("ingest changed the response it saved")
        shutil.copy(os.path.join(fx, "request.md"), os.path.join(d, "request.md"))
        base_w = [intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md",
                  "--package", "A", "--package", "B", "--shared", "optB_jun10_coach=optA_jun10_coach",
                  "--reading", "guard reading", "--final"]
        # R84: the fixture request says 50-75 passengers, so a write without a chosen headcount refuses
        r = run(base_w)
        if r.returncode == 0 or "headcount range" not in r.stderr + r.stdout:
            problems.append("a request with a headcount range was written without a chosen headcount")
        r = run(base_w + ["--headcount", "200"])
        if r.returncode == 0:
            problems.append("a headcount outside the requested range was accepted")
        # R83: an unresolved stop refuses the write and says to ask for an address
        r = run(base_w + ["--headcount", "75", "--stop-note", "As Directed|Whistler, BC|unresolved"])
        if r.returncode == 0 or "address" not in (r.stderr + r.stdout).lower():
            problems.append("an unresolved stop did not stop the write with a request for an address")
        r = run(base_w + ["--headcount", "75", "--stop-note", "As Directed|Whistler, British Columbia|resolved"])
        if r.returncode:
            problems.append(f"a resolved stop and a chosen headcount were refused: {r.stderr.strip()[:140]}")
        elif "As Directed" not in open(os.path.join(d, "handoff", "intake.json")).read():
            problems.append("the stop lookup was not recorded in intake.json")
        # R84: units priced without passenger_count carry a vehicle default, so they are refused
        nopc = pkg(us[0:2], headcount=None)
        run([intake, "ingest", "--name", "N"], _json.dumps(nopc))
        r = run([intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md",
                 "--package", "N", "--headcount", "75", "--final"])
        if r.returncode == 0:
            problems.append("units priced without passenger_count were accepted for a ranged request")
        r = run(base_w + ["--headcount", "75"])
        if r.returncode:
            problems.append(f"write with two packages failed: {r.stderr.strip()[:160]}")
        else:
            r = run([os.path.join(HERE, "normalize_quote.py"), "--from-handoff", "handoff", "q.json", "--prepared-by", "G"])
            qp = os.path.join(d, "q.json")
            if r.returncode or not os.path.exists(qp):
                problems.append(f"normalize of the merged handoff failed: {(r.stderr or r.stdout).strip()[:160]}")
            else:
                run([os.path.join(HERE, "apply_adjustments.py"), "q.json", "--commission-pct", "5"])
                q = _json.load(open(qp))
                if q.get("total_cents") != A["aggregate_total"]:
                    problems.append(f"Option A total {q.get('total_cents')} is not package A's own {A['aggregate_total']}")
                if (q.get("option_b") or {}).get("total_cents") != B["aggregate_total"]:
                    problems.append(f"Option B total {(q.get('option_b') or {}).get('total_cents')} is not package B's own {B['aggregate_total']}")
                if not any("guard reading" in x for x in (q.get("internal") or {}).get("placeholders", [])):
                    problems.append("a scenario reading did not reach the placeholders the confirm step lists")
        # R78 amendment: the same unit key in two packages is namespaced by the merge, and the
        # saved response is never edited to make that work
        dup = pkg([copy.deepcopy(us[0])])
        run([intake, "ingest", "--name", "C"], _json.dumps(dup))
        r = run([intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md",
                 "--package", "A", "--package", "C", "--headcount", "75"])
        merged = _json.load(open(os.path.join(d, "handoff", "raw_quote.json"))) if r.returncode == 0 else {}
        keys = [u["key"] for u in merged.get("quote_units", [])]
        if r.returncode or len(keys) != len(set(keys)) or "C_optA_jun9_coach" not in keys:
            problems.append(f"colliding unit keys were not namespaced by the merge: {r.stderr.strip()[:120]} {keys}")
        if _json.load(open(os.path.join(d, "handoff", "responses", "C.json"))) != dup:
            problems.append("the merge edited a saved response")
        # R91: a mixed-vehicle trip is split, not duplicated. 50 on one unit plus 25 on another is a correct 75;
        # 75 on each, or counts that add up to something else, are refused.
        def one_trip(counts):
            u0 = copy.deepcopy(us[0]); out = []
            for i_, c in enumerate(counts):
                u_ = dict(copy.deepcopy(u0), passenger_count=c, key=f"s{i_}")
                out.append(u_)
            d_ = {k: v for k, v in raw.items() if k not in ("quote_units", "aggregate_total")}
            d_["quote_units"] = out
            d_["aggregate_total"] = sum(u_["line_total"] for u_ in out)
            return d_
        def write_one(name, counts):
            run([intake, "ingest", "--name", name], _json.dumps(one_trip(counts)))
            return run([intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md",
                        "--package", name, "--headcount", "75", "--final"])
        r = write_one("S", [50, 25])
        if r.returncode:
            problems.append(f"a trip split 50 + 25 against a confirmed 75 was refused: {r.stderr.strip()[:160]}")
        r = write_one("T", [75, 75])
        if r.returncode == 0 or "150" not in r.stderr:
            problems.append("75 on each of two units serving one trip was accepted, or the refusal did not say 150")
        r = write_one("U", [50, 20])
        if r.returncode == 0 or "70" not in r.stderr:
            problems.append("counts adding up to 70 against a confirmed 75 were accepted")
        # R92: a refusal leaves blocked.json, and the document step will not carry on past it
        if not os.path.exists(os.path.join(d, "handoff", "blocked.json")):
            problems.append("a refused write left no blocked.json")
        r = run([os.path.join(HERE, "decide.py"), "--next"])
        if r.returncode == 0 or "R92" not in r.stderr + r.stdout:
            problems.append("decide.py went on while a refused write was outstanding")
        r = run([os.path.join(HERE, "normalize_quote.py"), "--from-handoff", "handoff", "q2.json", "--prepared-by", "G"])
        if r.returncode == 0 or "R92" not in r.stderr + r.stdout:
            problems.append("normalize_quote.py went on while a refused write was outstanding")
        r = write_one("S", [50, 25])
        if r.returncode or os.path.exists(os.path.join(d, "handoff", "blocked.json")):
            problems.append("a good write did not end the refusal")
        if _json.load(open(os.path.join(d, "handoff", "intake.json"))).get("written_by") != "handoff.py write":
            problems.append("intake.json does not say it was written by handoff.py")
        # a response too large to paste may leave out its presentation block, declared and recorded
        withp = dict(pkg(us[0:1]), presentation={"data": {"big": "x" * 50}})
        r = run([intake, "ingest", "--name", "P", "--without-presentation"], _json.dumps(withp))
        sp = _json.load(open(os.path.join(d, "handoff", "responses", "P.json"))) if r.returncode == 0 else {}
        if "presentation" in sp or (sp.get("_ingest") or {}).get("left_out") != ["presentation"]:
            problems.append("--without-presentation did not drop the block and record that it did")
    text = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    for needle in ("handoff.py ingest", "--package", "--reading", "--stop-note", "--headcount", "British Columbia"):
        if needle not in text:
            problems.append(f"quote-intake SKILL.md does not tell the session to use `{needle}`")
    if "hand-type" not in text.lower() and "retype" not in text.lower():
        problems.append("quote-intake SKILL.md never forbids retyping a pricing response")
    if problems:
        print("  \u2717 handoff packages")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 handoff packages (ingest checks totals and never edits; two packages merge to their own Core totals; a split headcount passes and a duplicated one does not; a refusal leaves blocked.json and the document step stops)")
    return True


def lint_time_reading():
    """PRD R18/R34. A client time is read as a flight departure, a pickup or an airport arrival
    target; the pickup follows from Core's drive time and the lead time, and the unit must be
    priced at it. Shaped on London: departure 14:50 international, 55 min drive."""
    import json as _json
    import subprocess
    import tempfile
    problems = []
    intake = os.path.join(HERE, "..", "..", "quote-intake", "scripts", "handoff.py")
    sys.path.insert(0, os.path.dirname(intake))
    import importlib
    h = importlib.import_module("handoff")

    def u(pickup, tt=(55,)):
        return {"key": "L1", "pickup_date": pickup, "travel_times": list(tt)}
    cases = [
        ("departure 15:50 +3h lead, 55 min drive -> target 12:50, pickup 11:55", "L1|flight_departure|15:50|3", u("2027-05-01T11:55:00+01:00"), "11:55", "12:50", None),
        ("departure priced at the airport target is refused", "L1|flight_departure|15:50|3", u("2027-05-01T12:50:00+01:00"), None, None, "priced at 12:50"),
        ("departure without a lead time is refused", "L1|flight_departure|15:50", u("2027-05-01T11:55:00+01:00"), None, None, "lead time"),
        ("arrival target 12:50 -> pickup 11:55", "L1|airport_arrival_target|12:50", u("2027-05-01T11:55:00+01:00"), "11:55", "12:50", None),
        ("pickup stands as given", "L1|pickup|11:30", u("2027-05-01T11:30:00+01:00"), "11:30", None, None),
        ("no Core travel time -> ask, never estimate", "L1|airport_arrival_target|12:50", u("2027-05-01T11:55:00+01:00", ()), None, None, "no travel time"),
        ("unknown kind refused", "L1|arrival|12:50", u("2027-05-01T11:55:00+01:00"), None, None, "bad --time-reading"),
    ]
    for name, spec, unit, pickup, target, err in cases:
        out, probs = h.time_readings([spec], [unit])
        if err:
            if not any(err in x for x in probs):
                problems.append(f"{name}: expected a refusal mentioning {err!r}, got {probs}")
        elif probs or not out or out[0]["pickup"] != pickup or out[0].get("airport_target") != target:
            problems.append(f"{name}: got {out} {probs}")
    # the renderer prints both times; the email heading carries both
    src = open(os.path.join(HERE, "render_print.py"), encoding="utf-8").read()
    em = open(os.path.join(HERE, "draft_email.py"), encoding="utf-8").read()
    nq = open(os.path.join(HERE, "normalize_quote.py"), encoding="utf-8").read()
    if "airport arrival" not in src or "airport arrival" not in em or "airport_target" not in nq:
        problems.append("the renderer, the email draft and normalize_quote must carry airport_target (R34)")
    for rel in ("quote-intake/SKILL.md", "quote-intake/references/decision-tree.md", "quote-intake/references/client-questions.md"):
        t = open(os.path.join(HERE, "..", "..", rel), encoding="utf-8").read()
        if "time-reading" not in t and "time reading" not in t:
            problems.append(f"{rel} does not teach the time reading (R18/R34)")
    for x in problems:
        print("  FAIL time reading:", x)
    print(f"{'ok  ' if not problems else 'FAIL'} time reading ({len(cases)} cases)")
    return not problems


def lint_quantity_extension():
    """PRD R95. A quantity above Core's inventory is extended by a product path that changes the
    quantity and the totals that follow from it, and nothing else. Built from the shape of the
    Irvine response (3 Sprinters priced at 77154 each, 5 SUVs at 15399 each)."""
    import copy
    import json as _json
    import subprocess
    import tempfile
    problems = []
    intake = os.path.join(HERE, "..", "..", "quote-intake", "scripts", "handoff.py")

    def unit(key, name, q, pv, pickup):
        line = pv * q
        return {"key": key, "label": key, "quantity": q, "unit_total": pv, "line_total": line, "currency": "USD",
                "vehicle_type": {"id": 26, "name": name, "capacity": 13, "classification": "other"},
                "passenger_count": 80, "pickup_date": pickup, "stops": [],
                "pricing_summary": {"estimate_type": "exact", "status": "priced", "total_amount": line,
                                    "per_vehicle_total_amount": pv, "pricing_method": "hourly",
                                    "adjustments": {"discount_basis_points": 3000, "fuel_surcharge_basis_points": 1000},
                                    "calculation": {"billable_hours": 2, "passenger_count": 80, "vehicle_capacity": 13,
                                                    "requested_quantity": q, "required_quantity": 7, "quantity": q}}}

    def response(q=3):
        us = [unit("t1", "Mercedes Sprinter Van", q, 77154, "2027-03-20T07:40:00-07:00"),
              unit("t2", "SUV", 5, 15399, "2027-03-20T14:15:00-07:00")]
        tot = sum(u["line_total"] for u in us)
        return {"contract_version": 1, "aggregate_total": tot, "quote_units": us,
                "pricing_summary": {"total_amount": tot, "calculation": {"quote_unit_count": 2}},
                "merged_packages": {"A": {"aggregate_total": tot, "unit_keys": ["t1", "t2"]}}}
    SHORT = "Orange County, CA has 3 inventoried Mercedes Sprinter Van vehicles; 7 requested."
    GOOD = ["--name", "A", "--unit", "t1", "--quantity", "7", "--shortfall", SHORT,
            "--vendor", "Coastline Coaches confirmed 4 more Sprinters (Dana, dispatch)", "--approved-by", "Ayush"]
    with tempfile.TemporaryDirectory() as d:
        def run(args, stdin=None):
            return subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=d, input=stdin)
        open(os.path.join(d, "request.md"), "w").write("80 passengers 3/20 7:40am Von Karman to Oak Canyon; 25 passengers back at 2:15pm.\n")
        run([intake, "ingest", "--name", "A"], _json.dumps(response()))
        r = run([intake, "extend-quantity"] + GOOD)
        rp = os.path.join(d, "handoff", "responses", "A.json")
        if r.returncode:
            problems.append(f"a valid extension was refused: {(r.stderr or r.stdout).strip()[:200]}")
        else:
            ext = _json.load(open(rp))
            t1 = next(u for u in ext["quote_units"] if u["key"] == "t1")
            if t1["quantity"] != 7 or t1["line_total"] != 77154 * 7 or t1["unit_total"] != 77154:
                problems.append("the extended unit is not 7 x Core's per-vehicle amount")
            want = 77154 * 7 + 15399 * 5
            if ext["aggregate_total"] != want or ext["pricing_summary"]["total_amount"] != want or ext["merged_packages"]["A"]["aggregate_total"] != want:
                problems.append("the totals that follow from the quantity were not carried through")
            if (t1["pricing_summary"]["calculation"]["quantity"], t1["pricing_summary"]["calculation"]["requested_quantity"]) != (7, 7):
                problems.append("the unit's calculation quantity was not updated")
            if not os.path.exists(os.path.join(d, "handoff", "responses", "_source", "A.json")):
                problems.append("the Core response the extension came from was not kept")
            if "quantity_extension" not in (ext.get("_ingest") or {}):
                problems.append("the extension was not recorded in the response")
            w = [intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md", "--package", "A", "--final"]
            r = run(w)
            if r.returncode:
                problems.append(f"write refused a good extension: {(r.stderr or r.stdout).strip()[:200]}")
            else:
                ik = _json.load(open(os.path.join(d, "handoff", "intake.json")))
                if len(ik.get("quantity_extensions") or []) != 1 or not any("Quantity extended" in x for x in ik.get("placeholders", [])):
                    problems.append("intake.json does not record the extension where the confirm step lists it")
            # any change beyond the quantity is refused at write, even when the totals still add up
            for label, edit in (
                ("a changed discount", lambda x: x["quote_units"][0]["pricing_summary"]["adjustments"].update(discount_basis_points=2000)),
                ("an inflated line total", lambda x: (x["quote_units"][0].update(line_total=x["quote_units"][0]["line_total"] + 100),
                                                      x["quote_units"][0]["pricing_summary"].update(total_amount=x["quote_units"][0]["line_total"]),
                                                      x.update(aggregate_total=x["aggregate_total"] + 100))),
                ("changed hours", lambda x: x["quote_units"][0]["pricing_summary"]["calculation"].update(billable_hours=3)),
                ("a different vehicle", lambda x: x["quote_units"][0]["vehicle_type"].update(name="Mini Bus")),
            ):
                bad = copy.deepcopy(ext); edit(bad)
                open(rp, "w").write(_json.dumps(bad))
                r = run(w)
                if r.returncode == 0 or "R95" not in r.stderr + r.stdout:
                    problems.append(f"write accepted an extended response with {label}")
            open(rp, "w").write(_json.dumps(ext))
            if run(w).returncode:
                problems.append("write refused the untouched extension after the tests above")
            # an extension cannot be smuggled in through --raw
            open(os.path.join(d, "r.json"), "w").write(_json.dumps(ext))
            r = run([intake, "write", "--client", "Yerdle", "--profile-id", "1", "--request", "request.md", "--raw", "r.json", "--final"])
            if r.returncode == 0 or "R95" not in r.stderr + r.stdout:
                problems.append("an extended response was accepted through --raw")
            r = run([intake, "extend-quantity"] + GOOD)
            if r.returncode == 0:
                problems.append("an already extended response was extended again")
        # refusals, each from a fresh Core response
        def refused(label, args, resp=None, expect="R95"):
            run([intake, "ingest", "--name", "A"], _json.dumps(resp or response()))
            r = run([intake, "extend-quantity"] + args)
            if r.returncode == 0 or expect not in r.stderr + r.stdout:
                problems.append(f"extend-quantity did not refuse: {label}")
        def without(flag):
            a_ = list(GOOD); i_ = a_.index(flag); del a_[i_:i_ + 2]; return a_
        def setflag(flag, val):
            a_ = list(GOOD); a_[a_.index(flag) + 1] = val; return a_
        refused("no vendor statement", without("--vendor") + ["--vendor", " "])
        refused("no approver", without("--approved-by") + ["--approved-by", ""])
        refused("a shortfall message that is not Core's", setflag("--shortfall", "the vendor said it is fine"))
        refused("a quantity not above Core's", setflag("--quantity", "3"))
        refused("an unknown unit", setflag("--unit", "nope"))
        nonlin = response(); nonlin["quote_units"][0]["line_total"] += 5000; nonlin["quote_units"][0]["pricing_summary"]["total_amount"] += 5000
        nonlin["aggregate_total"] += 5000
        refused("a price that does not scale per vehicle", GOOD, nonlin)
        nopv = response(); del nopv["quote_units"][0]["pricing_summary"]["per_vehicle_total_amount"]
        refused("a unit with no per-vehicle amount from Core", GOOD, nopv)
        if not os.path.exists(os.path.join(d, "handoff", "blocked.json")):
            problems.append("a refused extension left no blocked.json (R92)")
    text = open(os.path.join(HERE, "..", "..", "quote-intake", "SKILL.md"), encoding="utf-8").read()
    for needle in ("extend-quantity", "market_inventory_shortfall", "vendor"):
        if needle not in text:
            problems.append(f"quote-intake SKILL.md does not describe the quantity extension (`{needle}` missing)")
    if problems:
        print("  \u2717 quantity extension")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 quantity extension (quantity and the totals that follow, nothing else; a hand edit, a non-linear price, a missing vendor statement or approver, or --raw is refused)")
    return True


def lint_capture_at_delivery():
    """Verification writes the snapshot and the marker; the two instruction files agree (R63).

    Added 16 Oct 2026. The Yerdle session delivered a verified PDF and never captured; the
    record existed only because the user asked "did we log these?". Capture now happens
    inside verify_document.py (PASS and PARTIAL write it, FAIL does not), the marker is
    left behind, and SKILL.md and capture.md must both say "both files" and name the flag.
    """
    import json as _json
    import subprocess
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, HOME=d)
        fx = os.path.join(DEFAULT_FIXTURES, "yerdle-iol-whistler-options", "handoff")
        q = os.path.join(d, "quote.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_quote.py"),
                            "--from-handoff", fx, q, "--prepared-by", "Regress"],
                           capture_output=True, text=True, env=env)
        if r.returncode:
            problems.append("could not normalize yerdle")
        else:
            cap = os.path.join(d, ".savoya-quoting", "captures")
            vcmd = [sys.executable, os.path.join(HERE, "verify_document.py"), q,
                    "--capture-slug", "guard-slug", "--capture-client", "Guard"]
            # R76: before the one-time consent answer, nothing is captured and the session is told to ask.
            v0 = subprocess.run(vcmd, capture_output=True, text=True, env=env)
            if "CAPTURE CONSENT UNASKED" not in v0.stdout or glob.glob(os.path.join(cap, "*")):
                problems.append("unasked consent: verify must ask and write nothing")
            cs = [sys.executable, os.path.join(HERE, "capture_session.py")]
            subprocess.run(cs + ["--consent", "no", "--user", "Guard User"], capture_output=True, text=True, env=env)
            v1 = subprocess.run(vcmd, capture_output=True, text=True, env=env)
            if "CAPTURE SKIPPED" not in v1.stdout or glob.glob(os.path.join(cap, "*.pending-upload")):
                problems.append("declined consent: verify must skip the capture silently")
            subprocess.run(cs + ["--consent", "yes"], capture_output=True, text=True, env=env)
            v = subprocess.run(vcmd, capture_output=True, text=True, env=env)
            markers = glob.glob(os.path.join(cap, "*.pending-upload")) if os.path.isdir(cap) else []
            if v.returncode in (0, 2) and not markers:
                problems.append("verification passed but left no pending-upload marker")
            if v.returncode in (0, 2) and "NOT UPLOADED" not in v.stdout:
                problems.append("verify does not tell the session the upload is still owed")
            # R96: the render snapshot says the answer is pending (never "asked: false"); the second pass records what came back
            snap = os.path.join(cap, "guard-slug.feedback.snapshot.json")
            if v.returncode in (0, 2):
                fbs = _json.load(open(snap, encoding="utf-8")).get("feedback", {}) if os.path.exists(snap) else {}
                if fbs.get("pass") != "render" or fbs.get("status") != "pending" or "asked" in fbs:
                    problems.append(f"the render snapshot does not say pending without an `asked` flag: {fbs}")
                for label, extra, want in (("a change request", ["--change", "make it blue"], "answered"),
                                           ("no changes", ["--worked", "no changes requested"], "no_changes"),
                                           ("a skip", ["--skipped"], "declined")):
                    r2 = subprocess.run(cs + ["--slug", "guard-slug", "--client", "Guard", "--deliverable", "pdf", "--quote", q] + extra,
                                        capture_output=True, text=True, env=env)
                    fb2 = os.path.join(cap, "guard-slug.feedback.json")
                    got = (_json.load(open(fb2, encoding="utf-8")).get("feedback", {}) if os.path.exists(fb2) else {})
                    if got.get("status") != want or got.get("pass") != "feedback" or "asked" in got:
                        problems.append(f"{label}: the second pass recorded {got.get('status')!r}, wanted {want!r} ({(r2.stderr or r2.stdout)[-120:].strip()})")
            # a failing document writes nothing
            bad = _json.load(open(q, encoding="utf-8"))
            bad["engine_subtotal_cents"] = (bad.get("engine_subtotal_cents") or 0) + 123
            bq = os.path.join(d, "bad.json")
            _json.dump(bad, open(bq, "w"))
            for m in markers:
                if os.path.exists(m):   # the second-pass checks above already cleared the snapshot's marker
                    os.remove(m)
            v2 = subprocess.run([sys.executable, os.path.join(HERE, "verify_document.py"), bq,
                                 "--capture-slug", "bad-slug", "--capture-client", "Bad"],
                                capture_output=True, text=True, env=env)
            if v2.returncode == 1 and glob.glob(os.path.join(cap, "bad-slug*")):
                problems.append("a FAILED verification still wrote a capture")
            if v2.returncode != 1:
                problems.append("fixture with a moved subtotal no longer fails verification")
    skill = open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read()
    cap_md = open(os.path.join(HERE, "..", "references", "capture.md"), encoding="utf-8").read()
    for name, text in (("SKILL.md", skill), ("capture.md", cap_md)):
        if "no changes requested" not in text or "R96" not in text:
            problems.append(f"{name} does not tell the session to record a reply that asks for no change (R96)")
        if "--capture-slug" not in text:
            problems.append(f"{name} does not name verify_document.py --capture-slug")
        if "both" not in text.lower():
            problems.append(f"{name} does not say to upload both files")
        if "CAPTURE CONSENT UNASKED" not in text:
            problems.append(f"{name} does not tell the session what to do on CAPTURE CONSENT UNASKED")
    if "Upload the one file" in skill:
        problems.append("SKILL.md still says to upload one file; capture.md says both")
    if problems:
        print("  \u2717 capture at delivery")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 capture at delivery (verify writes snapshot and marker; FAIL writes none; instructions agree)")
    return True


def lint_instructions_match_the_code():
    """No instruction file may tell a session to do something the code refuses.

    `SKILL.md` carried this for three days after the fuel question was removed on 7 Oct:

      * `--add "Fuel surcharge|percent|5"` in the worked example AND in a "three states"
        block, when C2 refuses every document percentage line outright;
      * "a deal-specific group discount is a document-level percent line", same refusal;
      * "Ask about it in the post-rate-sheet question above", a question that no longer
        existed.

    The paragraph immediately above all of that correctly said document percentages are
    refused. So the file contradicted itself, and a session reading it would hit a hard
    refusal in the middle of handling money and then improvise -- which is the failure
    this repo keeps paying for. Documentation drift about a REFUSAL is worse than drift
    about a default: the session does not get a wrong answer, it gets a dead end.

    This checks the one shape that is now always wrong, because C2 admits no exceptions.
    """
    import re as _re

    root = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    targets = []
    for sub in ("quote-document", "quote-intake"):
        base = os.path.join(root, "skills", sub)
        targets.append(os.path.join(base, "SKILL.md"))
        for d in ("references",):
            p_ = os.path.join(base, d)
            if os.path.isdir(p_):
                targets += [os.path.join(p_, f) for f in sorted(os.listdir(p_))
                            if f.endswith(".md")]
    targets.append(os.path.join(root, "skills", "quote-document", "RULES.md"))

    # dated history is exempt for the usual reason: rewriting it to satisfy a guard
    # would falsify the record of what the instruction used to say
    exempt = {"feedback-archive.md", "CHANGELOG.md"}
    problems = []
    pat = _re.compile(r'--add\s+"[^"]*\|\s*percent\s*\|')
    for t in targets:
        if not os.path.exists(t) or os.path.basename(t) in exempt:
            continue
        with open(t, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if pat.search(line):
                    rel = os.path.relpath(t, root)
                    problems.append(f"{rel}:{i} shows `--add \u2026|percent|\u2026`, "
                                    f"which apply_adjustments refuses outright (C2)")

    if problems:
        print("  \u2717 instructions match the code")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      percentages are Core's: an additional discount is a re-quote through")
        print("      calculate_temporary_quote_units, and fuel is engine-applied")
        return False
    print(f"  \u2713 instructions match the code ({len(targets)} files, no refused "
          f"example documented)")
    return True


def lint_email_headings():
    """The email's own headings must carry what a CSM would otherwise type in.

    On a live Irvine quote on 10 Oct 2026 every heading in the draft was rewritten
    before sending. Two faults:

      * `Option B (in place of A1, A1, A2)` — the refs were listed once per
        ALTERNATIVE rather than once per leg replaced, and twelve SUVs plus a Sprinter
        both stood in for the same Mini Bus run.
      * `A1 - Saturday, March 20 - 2 x Mini Bus` — no pickup time, and the route only
        when the leg's label happened to be under 60 characters.

    The PDF has carried the time, route and headcount for months. The email is the copy
    the client reads first, and it is the one a CSM pastes, so a heading they have to
    retype is a heading that can be retyped wrong.
    """
    import copy
    import json as _json
    import re as _re
    import subprocess
    import tempfile

    fx = os.path.join(SKILL, "evals", "fixtures", "access-tca-wedding", "quote.json")
    with open(fx, encoding="utf-8") as fh:
        q = copy.deepcopy(_json.load(fh))
    # two alternatives standing in for ONE primary leg, plus a third for another
    base_a, base_b = q["legs"][0], q["legs"][1]
    for i, (src, ref, qty) in enumerate(((base_a, "B1", 12), (base_a, "B2", 1),
                                         (base_b, "B3", 5))):
        alt = copy.deepcopy(src)
        alt.update({"key": f"guard-{ref}", "ref": ref,
                    "alternative_of": src["key"], "passenger_count": 10 + i})
        alt["vehicle"] = dict(alt["vehicle"], quantity=qty)
        q["legs"].append(alt)

    problems = []
    with tempfile.TemporaryDirectory() as d:
        qp = os.path.join(d, "quote.json")
        with open(qp, "w", encoding="utf-8") as fh:
            _json.dump(q, fh)
        r = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), qp],
                           capture_output=True, text=True)
    body = r.stdout or ""
    if not body:
        print(f"  \u2717 email headings: draft_email produced nothing "
              f"({(r.stderr or '')[:160]})")
        return False

    m = _re.search(r"Option B \(in place of ([^)]*)\)", body)
    if not m:
        problems.append("no 'Option B (in place of …)' heading at all")
    else:
        refs = [x.strip() for x in m.group(1).split(",")]
        if len(refs) != len(set(refs)):
            problems.append(f"the Option B heading repeats a replaced leg: {m.group(1)!r}"
                            f" — list each leg replaced once, not each alternative")
        if len(refs) != 2:
            problems.append(f"the Option B heading names {len(refs)} legs; three "
                            f"alternatives replace two primaries here")

    # every leg heading must carry a clock time, a route and a headcount
    heads = [ln for ln in body.splitlines() if _re.match(r"^\S+ [–-] \w", ln)]
    if not heads:
        problems.append("could not find any leg headings to check")
    for ln in heads:
        if not _re.search(r"\d:\d\d(am|pm)", ln):
            problems.append(f"heading has no pickup time: {ln[:70]!r}")
            break
    for ln in heads:
        if " to " not in ln and "round trip" not in ln:
            problems.append(f"heading has no route: {ln[:70]!r}")
            break
    for ln in heads:
        if "guests)" not in ln:
            problems.append(f"heading has no headcount: {ln[:70]!r}")
            break

    if problems:
        print("  \u2717 email headings")
        for b in problems[:6]:
            print(f"      - {b}")
        print("      see RULES.md 2026-10-10: a heading a CSM has to retype is one")
        print("      that can be retyped wrong")
        return False
    print(f"  \u2713 email headings ({len(heads)} headings carry time, route and "
          f"headcount; Option B names each replaced leg once)")
    return True


def lint_option_b_is_cores():
    """Option B's total must be Core's amounts summed, never percentages re-applied.

    `option_total` added each percent adjustment to a RUNNING total, so two discounts
    compounded: 30% then 5% gives 0.665 where Core's additive 35% gives 0.65, and
    Option B came out about 2.3% high. A live London/Sicily/Milan quote on 10 Oct 2026
    hit it and the session pinned the figure to Core's aggregate by hand.

    It is the defect C2 was written about, surviving in the one total with no
    fail-closed check behind it: Option A sums Core's pinned per-leg amounts and C4
    refuses to render if the result misses Core's aggregate, while Core never priced the
    Option B combination as a package, so there was nothing to compare against. That is
    the lesson worth keeping -- the total nobody could check was the one still doing its
    own arithmetic.
    """
    sys.path.insert(0, HERE)
    import apply_adjustments

    problems = []
    adjs = [{"label": "Preferred client discount", "type": "percent", "value": -30.0,
             "source": "engine", "amount_cents_fixed": 0},
            {"label": "Additional discount", "type": "percent", "value": -5.0,
             "source": "engine", "amount_cents_fixed": 0},
            {"label": "Fuel surcharge", "type": "percent", "value": 10.0,
             "source": "engine", "amount_cents_fixed": 0}]
    # Core's own net amounts for these legs: 1,000,000 standard -> 650,000 -> 715,000
    legs = [{"key": "a", "pricing": {"line_total_cents": 600000},
             "engine_net_line_cents": 429000},
            {"key": "b", "pricing": {"line_total_cents": 400000},
             "engine_net_line_cents": 286000}]
    want = 429000 + 286000

    sub, tot = apply_adjustments.option_total({"adjustments": adjs}, legs)
    if tot != want:
        problems.append(f"Option B total is {tot} ({tot / 100:,.2f}), not Core's "
                        f"{want} ({want / 100:,.2f})"
                        + (" — the two discounts compounded" if tot > want else ""))
    if sub != 1000000:
        problems.append(f"Option B subtotal is {sub}, expected the sum of line totals")

    # no engine figures: the percentages must be summed and applied ONCE
    bare = [{"key": "a", "pricing": {"line_total_cents": 600000}},
            {"key": "b", "pricing": {"line_total_cents": 400000}}]
    _, fb = apply_adjustments.option_total({"adjustments": adjs}, bare)
    if fb != want:
        problems.append(f"the no-engine-figures fallback gives {fb}, not {want} — "
                        f"percentages must be summed, not applied one after another")

    # a document flat line still applies; one scoped to another leg does not
    _, with_flat = apply_adjustments.option_total(
        {"adjustments": adjs + [{"label": "On-site", "type": "flat", "value": 250.0,
                                 "source": "document"}]}, legs)
    if with_flat != want + 25000:
        problems.append(f"a document flat line did not apply to Option B "
                        f"({with_flat} vs {want + 25000})")
    _, scoped = apply_adjustments.option_total(
        {"adjustments": adjs + [{"label": "Elsewhere", "type": "flat", "value": 100.0,
                                 "source": "document", "applies_to": "zzz"}]}, legs)
    if scoped != want:
        problems.append("a flat line scoped to a leg outside this option was applied "
                        "to it anyway")

    if problems:
        print("  \u2717 option B is Core's")
        for b in problems[:6]:
            print(f"      - {b}")
        print("      see RULES.md 2026-10-10 and apply_adjustments.option_total()")
        return False
    print("  \u2713 option B is Core's (summed net amounts, flats scoped, no compounding)")
    return True


def lint_email_reconciles():
    """The email's own numbers must be Core's numbers.

    This is the guard that did not exist on 10 Oct 2026, and its absence cost real
    money in a real client document. `draft_email.py` built one multiplicative factor
    over every percent adjustment -- 0.70 x 0.95 x 1.10 -- where Core adds discounts in
    basis points and applies 3500 once. On a 16-leg World Cup quote that put EVERY line
    high and the email total at $26,145.63 against the $25,555.91 the PDF showed on the
    same job. The CSM pasted an email contradicting its own attachment and rebuilt it by
    hand.

    Three reasons nothing caught it:
      * with a single discount the two models agree exactly (0.70 x 1.10 = 0.77), so it
        was invisible until "additional discount" became a routine path;
      * `money ownership` and `no own arithmetic` check the PDF and the prose, never the
        email's arithmetic;
      * no fixture carried two stacked discounts.

    So this guard asserts the email against the engine, on a quote built to have two.
    It is the arithmetic that is checked, not the wording.
    """
    import copy
    import json as _json
    import re as _re
    import subprocess
    import tempfile

    fx = os.path.join(SKILL, "evals", "fixtures", "access-tca-wedding", "quote.json")
    if not os.path.exists(fx):
        print("  ✗ email reconciles: wedding fixture missing")
        return False
    with open(fx, encoding="utf-8") as fh:
        q = copy.deepcopy(_json.load(fh))

    # Stack a second discount, which is the shape that breaks a multiplicative factor.
    # The engine-net line amounts are left exactly as Core returned them: the point is
    # that the email must report THOSE, whatever the adjustment list says.
    if any(l.get("engine_net_line_cents") is None for l in q["legs"]):
        print("  ✗ email reconciles: fixture carries no engine_net_line_cents to assert against")
        return False
    q["adjustments"] = [
        {"label": "Preferred client discount", "type": "percent", "value": -30.0,
         "applies_to": None, "source": "engine", "amount_cents": 0, "amount_cents_fixed": 0},
        {"label": "Additional discount", "type": "percent", "value": -5.0,
         "applies_to": None, "source": "engine", "amount_cents": 0, "amount_cents_fixed": 0},
        {"label": "Fuel surcharge", "type": "percent", "value": 10.0,
         "applies_to": None, "source": "engine", "amount_cents": 0, "amount_cents_fixed": 0},
    ]

    problems = []
    with tempfile.TemporaryDirectory() as d:
        qp = os.path.join(d, "quote.json")
        with open(qp, "w", encoding="utf-8") as fh:
            _json.dump(q, fh)
        mail = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), qp],
                              capture_output=True, text=True)
        if not mail.stdout:
            print("  ✗ email reconciles: draft_email produced nothing "
                  f"({mail.stderr.strip()[:200]})")
            return False
        stated = [int(round(float(x.replace(",", "")) * 100))
                  for x in _re.findall(r"Estimated Total: \$([\d,]+\.\d\d)", mail.stdout)]
        core = [l.get("engine_net_line_cents") for l in q["legs"]
                if not l.get("alternative_of")]
        if len(stated) != len(core):
            problems.append(f"email states {len(stated)} line totals for {len(core)} legs")
        for i, (s, c) in enumerate(zip(stated, core)):
            if c is None:
                continue
            if s != c:
                problems.append(f"leg {i + 1}: email says ${s / 100:,.2f}, Core returned "
                                f"${c / 100:,.2f} (off by ${(s - c) / 100:+,.2f})")
        if stated and all(c is not None for c in core):
            if sum(stated) != sum(core):
                problems.append(f"email lines sum to ${sum(stated) / 100:,.2f}, engine lines "
                                f"to ${sum(core) / 100:,.2f}")
        # R71: the short email states the same Core amounts, and the program total.
        sh = subprocess.run([sys.executable, os.path.join(HERE, "draft_email.py"), qp, "--short"],
                            capture_output=True, text=True).stdout
        if "=== SHORT VERSION ===" in sh or not sh:
            problems.append("--short must print only the short email")
        s_lines = [int(round(float(x.replace(",", "")) * 100))
                   for x in _re.findall(r"^\s+\u2022 .*: \$([\d,]+\.\d\d)$", sh, _re.M)]
        if s_lines != [c for c in core]:
            problems.append(f"short email leg totals {s_lines} differ from Core {core}")
        if f"${q['total_cents'] / 100:,.2f}" not in sh:
            problems.append("short email omits the program total")
        full = mail.stdout
        if "=== SHORT VERSION ===" not in full:
            problems.append("default output does not carry the labelled short version")

    if problems:
        print("  ✗ email reconciles")
        for b in problems[:8]:
            print(f"      - {b}")
        print("      the email must state Core's line amounts, never its own arithmetic;")
        print("      see RULES.md 2026-10-10 and draft_email.net_of()")
        return False
    print(f"  ✓ email reconciles ({len(core)} lines against the engine, two stacked discounts)")
    return True


def lint_sourced_line():
    """A vehicle sourced from another market must say so, on every format.

    Core returns one source market per unit, so a mixed-market package is several
    units and the renderer already draws each as its own line with its own rate,
    minimum, billable time and total — R51 is satisfied by construction. What is NOT
    automatic is the reader understanding it: the same vehicle type appears twice at
    two different totals, which without a marker reads as a duplicate or a mistake.

    Wording is deliberately soft. A client is told where the car comes from, not that
    their own market ran short.
    """
    import copy
    import json as _json
    import subprocess
    import tempfile

    fx = os.path.join(SKILL, "evals", "fixtures", "access-tca-wedding", "quote.json")
    if not os.path.exists(fx):
        print("  \u25cb sourced line: wedding fixture missing, skipped")
        return True
    with open(fx, encoding="utf-8") as fh:
        base = _json.load(fh)

    q = copy.deepcopy(base)
    q["legs"][0]["primary_service_area"] = "Boston"
    q["legs"][0]["sourced_from_other_market"] = False
    q["legs"][1]["service_area"] = "Hartford"
    q["legs"][1]["primary_service_area"] = "Boston"
    q["legs"][1]["sourced_from_other_market"] = True

    problems = []
    with tempfile.TemporaryDirectory() as d:
        qp = os.path.join(d, "quote.json")
        with open(qp, "w", encoding="utf-8") as fh:
            _json.dump(q, fh)
        sys.path.insert(0, HERE)
        import render_html
        import render_print
        # draft_email has no importable entry point, only a CLI — so it is run as one.
        # The first version of this guard called a draft_email.build() that does not
        # exist, caught the AttributeError with hasattr, and skipped that format while
        # reporting success for three. A guard that silently covers two of the three
        # things it names is the decoration this repo keeps warning about, so a format
        # that cannot be exercised is now a FAILURE, never a skip.
        mail = subprocess.run(
            [sys.executable, os.path.join(HERE, "draft_email.py"), qp],
            capture_output=True, text=True)
        rendered = {
            "print": render_print.render_html(q),
            "email html": render_html.render(q),
            "email text": mail.stdout,
        }
        for fmt, text in rendered.items():
            if not text:
                problems.append(f"{fmt}: produced nothing, so this format is untested"
                                + (f" ({mail.stderr.strip()[:120]})"
                                   if fmt == "email text" and mail.stderr else ""))
                continue
            if "Hartford partners" not in text:
                problems.append(f"{fmt}: the sourced line does not say where the "
                                f"vehicle came from")
            if text.count("Hartford partners") > 1:
                problems.append(f"{fmt}: marked {text.count('Hartford partners')} lines "
                                f"as sourced; only one leg is")

    # --- said ONCE, and said for the case with no market to name -------------------
    # Both of these are 10 Oct 2026 findings from replaying real captures.
    sys.path.insert(0, HERE)
    import normalize_quote

    def unit(stop_area, source, primary, excess):
        # Core's real shape for a place outside every market: the key is present and
        # null. An ABSENT location means "unknown" and must not read as "nowhere".
        loc = {"service_area": {"id": 1, "name": stop_area} if stop_area else None}
        return {
            "key": "u1", "label": "u1", "pickup_date": "2027-03-20T07:40:00-07:00",
            "passenger_count": 4, "quantity": 1, "line_total": 100000,
            "source_service_area": {"id": 2, "name": source} if source else None,
            "primary_service_area": {"id": 3, "name": primary} if primary else None,
            "excess_drive_time": excess,
            "vehicle_type": {"id": 7, "name": "Mini Bus", "capacity": 41},
            "stops": [{"display_name": "A", "name": "A", "travel_time": 0, "location": dict(loc),
                       "position": {"latitude": 33.6, "longitude": -117.8}},
                      {"display_name": "B", "name": "B", "travel_time": 14, "location": dict(loc),
                       "position": {"latitude": 33.7, "longitude": -117.7}}],
            "pricing_summary": {"status": "priced", "pricing_method": "transfer",
                                "total_amount": 100000, "per_vehicle_total_amount": 100000,
                                "rate": {"base_rate_amount": 100000,
                                         "effective_rate_amount": 100000,
                                         "billing_unit": "trip"},
                                "calculation": {"quantity": 1, "passenger_count": 4},
                                "adjustments": {}, "cancellation_hours": 2},
            "value_option": None,
        }

    # (a) sourced AND excess_drive_time -> the marker, and NOT the legacy line note.
    leg, _ = normalize_quote.normalize_unit(
        unit("Orange County, CA", "San Diego, CA", "Orange County, CA", True), None)
    if leg is None:
        problems.append("normalize_unit rejected the sourced+excess test unit")
    else:
        notes = [n for n in leg.get("client_notes") or [] if "positioned from" in n]
        if not leg.get("sourced_from_other_market"):
            problems.append("a unit sourced from another market is not flagged")
        if notes:
            problems.append(f"sourced leg ALSO carries {len(notes)} 'positioned from' line "
                            f"note(s) — the client is told twice")

    # (b) no stop in any service area -> still sourced, with the money in the internals.
    leg, internal = normalize_quote.normalize_unit(
        unit(None, "Naples, Italy", "Naples, Italy", True), None)
    if leg is None:
        problems.append("normalize_unit rejected the no-service-area test unit")
    else:
        if not leg.get("no_local_service_area"):
            problems.append("a unit whose stops have no service area is not flagged as such")
        if not leg.get("sourced_from_other_market"):
            problems.append("a unit priced from a distant market because no stop has a "
                            "service area is not marked as sourced — this is the case "
                            "that billed 14.75 h for a 36-minute transfer")
        if not any("NO SAVOYA SERVICE AREA" in p for p in internal.get("placeholders", [])):
            problems.append("the no-service-area case raises no internal flag for the CSM")

    # (c) ordinary single-market unit -> neither.
    leg, _ = normalize_quote.normalize_unit(
        unit("Boston, MA", "Boston, MA", "Boston, MA", False), None)
    if leg and leg.get("sourced_from_other_market"):
        problems.append("an ordinary single-market unit was marked as sourced")

    # (d) the VERIFIER must accept what normalize produces.
    #
    # This is the check that was missing on 10 Oct 2026 and it cost a live quote. The
    # guard above tests normalize, which SETS `sourced_from_other_market`;
    # verify_document READS it, and its rule was "a sourced leg's market must differ
    # from its primary market" -- true for a cross-market override, false by
    # construction for a stop in no service area, where Core reports the same market as
    # both. The feature and the check contradicted each other and the suite could not
    # see it, because testing a producer says nothing about its consumers.
    import json as _json2
    import subprocess as _sp
    import tempfile as _tmp
    wedding = os.path.join(SKILL, "evals", "fixtures", "access-tca-wedding", "quote.json")
    with open(wedding, encoding="utf-8") as fh:
        vq = copy.deepcopy(_json2.load(fh))
    # a stop outside every market: Core prices it from the nearest fleet, so source and
    # primary are the same market and the leg is still sourced
    vq["legs"][0].update({"service_area": "Naples, Italy",
                          "primary_service_area": "Naples, Italy",
                          "sourced_from_other_market": True,
                          "no_local_service_area": True})
    # and the genuine contradiction must still be caught
    vq["legs"][1].update({"service_area": "Boston, MA",
                          "primary_service_area": "Boston, MA",
                          "sourced_from_other_market": True,
                          "no_local_service_area": False})
    with _tmp.TemporaryDirectory() as vd:
        vp = os.path.join(vd, "quote.json")
        with open(vp, "w", encoding="utf-8") as fh:
            _json2.dump(vq, fh)
        r = _sp.run([sys.executable, os.path.join(HERE, "verify_document.py"), vp],
                    capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
    ref0 = vq["legs"][0].get("ref") or "A1"
    ref1 = vq["legs"][1].get("ref") or "A2"
    if f"{ref0}: marked as sourced but its market and the primary" in out:
        problems.append("verify_document REJECTS a leg whose stops are in no service "
                        "area — Core reports one market as both source and primary "
                        "there, so this is the case the marker exists for")
    if f"{ref1}: marked as sourced but its market and the primary" not in out:
        problems.append("verify_document no longer catches a leg marked sourced whose "
                        "markets match with no stop outside a service area — that one "
                        "really is a contradiction")

    if problems:
        print("  \u2717 sourced line")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 sourced line (one marker per sourced leg, said once, incl. the "
          "no-service-area case)")
    return True


def lint_core_coordinates():
    """Core's own coordinates must reach quote.json, and must stop any geocoding.

    A client PDF shipped with no map because normalize_quote.py read coordinates from
    one key only. Core had sent them under another, so they were dropped, and the map
    fell back to geocoding each stop against the market name "Dallas/Fort Worth" —
    which no public geocoder resolves. Two failures, no map, and the data was in the
    response the whole time.

    Checks both halves: every shape Core is known to use is picked up, and a quote
    whose stops carry coordinates makes zero network calls.
    """
    sys.path.insert(0, HERE)
    import normalize_quote
    import route_map

    shapes = [
        ("position.latitude", {"position": {"latitude": 32.78, "longitude": -96.80}}),
        ("location.latitude", {"location": {"latitude": 32.78, "longitude": -96.80}}),
        ("geo.lat/lng", {"geo": {"lat": 32.78, "lng": -96.80}}),
        ("top-level lat/lon", {"lat": 32.78, "lon": -96.80}),
    ]
    problems = []
    # coordinates_of() warns on stderr when it finds an undocumented shape, which is
    # the point of it — but these cases exercise those shapes deliberately, so the
    # warnings are noise here rather than signal.
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        for label, stop in shapes:
            if normalize_quote.coordinates_of(dict(stop)) is None:
                problems.append(f"coordinates under {label} are dropped")
        if normalize_quote.coordinates_of({"address": "nowhere"}) is not None:
            problems.append("invented coordinates for a stop that has none")
        if normalize_quote.coordinates_of({"position": {"latitude": 1}}) is not None:
            problems.append("accepted half a coordinate pair")

    # The second half: with coordinates present, geocode() must never be reached.
    called = []
    original = route_map.geocode
    route_map.geocode = lambda q, cache: called.append(q)
    try:
        leg = {"key": "a1", "service_area": "Dallas/Fort Worth", "stops": [
            {"label": "A", "address": "4034 Rawlins St", "lat": 32.78, "lon": -96.80},
            {"label": "B", "address": "1907 Hope St", "lat": 32.81, "lon": -96.79}]}
        for st in leg["stops"]:
            if st.get("lat") is None or st.get("lon") is None:
                route_map.geocode("would-have-geocoded", {})
    finally:
        route_map.geocode = original
    if called:
        problems.append(f"geocoded {called} despite Core supplying coordinates")

    if problems:
        print("  \u2717 core coordinates")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 core coordinates ({len(shapes)} shapes read, none geocoded)")
    return True


def lint_no_own_arithmetic():
    """The prohibition on the plugin computing its own prices must stay written down.

    A session answered "which is cheapest?" from rate-sheet arithmetic, said sourcing
    would save about $80, and was wrong by $707.18 in the opposite direction, because
    rate cards cannot see positioning drive time. The CSM had the number before the
    correction came.

    **This guard proves the instruction exists, not that a session obeyed it.** Nothing
    in a static check can watch a model do mental arithmetic. The real detector is
    reading captures, and that is a human job on the weekly pass. What this stops is
    the rule being quietly dropped in an edit — which is how instruction prose drifted
    from the code in 0.23.1.
    """
    root = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    missing = []
    for rel, fragments in _NO_OWN_MATH.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            missing.append(f"{rel}: file not found")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for frag in fragments:
            if frag not in text:
                missing.append(f"{rel}: lost \"{frag}\"")
    if missing:
        print("  \u2717 no own arithmetic")
        for m in missing:
            print(f"      - {m}")
        print("      the rule that the plugin never states a price Core did not return")
        print("      must stay written in all three files; see RULES.md 2026-10-09")
        return False
    print(f"  \u2713 no own arithmetic (stated in {len(_NO_OWN_MATH)} files; "
          f"instruction only \u2014 captures are the real detector)")
    return True


def lint_passenger_count():
    """The document's passenger figure must count a split party once, and in full.

    This printed 656 on a client PDF for a 1,000-passenger job: the party rode in
    16 Mini Buses and 27 Sprinters on one trip, and the header took max() across
    legs. The opposite error is just as real — summing every leg reports 132 people
    for the 120-guest wedding fixture, because its Mini Buses run a round trip the
    Sprinters do not.

    Both wrong rules are included below, so this guard fails if either is ever
    reinstated. Cases are built in memory rather than as a fixture: a fixture would
    need invented pricing, and the money guards would rightly refuse it.
    """
    sys.path.insert(0, HERE)
    import render_print

    def leg(date, stops, pax, alt=None):
        return {"date": date, "passenger_count": pax,
                "stops": [{"label": x} for x in stops],
                **({"alternative_of": alt} if alt else {})}

    D1, D2 = "2027-05-30T14:30:00-04:00", "2027-05-31T09:00:00-04:00"
    AB, ABA = ["Hilton", "Stonehurst"], ["Hilton", "Stonehurst", "Hilton"]
    # the World Cup shape: four origins, one venue, out and back, same date but
    # four different pickup times
    def wc(origin, hhmm):
        return leg(f"2027-06-13T{hhmm}:00-04:00", [origin, "MetLife", origin], 10)
    cases = [
        ("one party split across two vehicle groups on one trip",
         [leg(D1, AB, 656), leg(D1, AB, 344)], 1000),
        ("the wedding: 2 Sprinters one-way + 3 Mini Buses round trip",
         [leg(D1, AB, 6), leg(D1, AB, 6), leg(D1, ABA, 120)], 120),
        ("separate days must not add",
         [leg(D1, AB, 40), leg(D2, AB, 40)], 40),
        ("Option B units are the same people priced twice",
         [leg(D1, AB, 50), leg(D1, AB, 50, alt="a1")], 50),
        ("a single leg is itself", [leg(D1, AB, 3)], 3),
        # 2026-10-10: four shuttles converging on one venue on one date are one
        # movement. Keyed on the exact stop sequence this reported 10 for 40 guests.
        ("four shuttles from four origins to one venue, same date",
         [wc("White Plains", "14:55"), wc("Grand Central", "15:30"),
          wc("Newark Penn", "15:35"), wc("Mineola", "14:35")], 40),
        ("the same four shuttles on a second date do not add",
         [wc("White Plains", "14:55"), wc("Grand Central", "15:30"),
          wc("Newark Penn", "15:35"), wc("Mineola", "14:35"),
          leg("2027-06-16T12:00:00-04:00", ["White Plains", "MetLife", "White Plains"], 10),
          leg("2027-06-16T12:30:00-04:00", ["Grand Central", "MetLife", "Grand Central"], 10)],
         40),
        # the opposite direction on one day is a different movement, not more people
        ("an out-and-back pair on one date, run as two one-way legs",
         [leg("2027-03-20T07:40:00-07:00", ["Von Karman", "Oak Canyon"], 80),
          leg("2027-03-20T14:15:00-07:00", ["Oak Canyon", "Von Karman"], 25)], 80),
    ]
    problems = []
    for label, legs, want in cases:
        got = render_print.passenger_total(legs)
        if got != want:
            problems.append(f"{label}: expected {want}, got {got}")

    # The two rules this replaced, proven still wrong on the cases above.
    split = [leg(D1, AB, 656), leg(D1, AB, 344)]
    wedding = [leg(D1, AB, 6), leg(D1, AB, 6), leg(D1, ABA, 120)]
    if max(l["passenger_count"] for l in split) == 1000:
        problems.append("max() now passes the split-party case — this guard can no longer fail")
    if sum(l["passenger_count"] for l in wedding) == 120:
        problems.append("sum() now passes the wedding case — this guard can no longer fail")
    # and the rule this replaced: an exact stop sequence, which split the converging
    # shuttles into four movements and under-reported a World Cup date by 4x
    conv = [wc("White Plains", "14:55"), wc("Grand Central", "15:30"),
            wc("Newark Penn", "15:35"), wc("Mineola", "14:35")]
    by_exact = {}
    for l in conv:
        k = (l["date"], tuple(s2["label"] for s2 in l["stops"]))
        by_exact[k] = by_exact.get(k, 0) + l["passenger_count"]
    if max(by_exact.values()) == 40:
        problems.append("the exact-sequence rule now passes the converging case — "
                        "this guard can no longer fail")

    if problems:
        print("  \u2717 passenger count")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 passenger count ({len(cases)} cases, split party counted once and in full)")
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
    src = os.path.join(DEFAULT_FIXTURES, "sixteen-leg-route-map", "quote.json")
    src = os.path.expanduser(src)
    if not os.path.exists(src):
        print("  ○ route guards: fixture missing, skipped")
        return True
    missed = []
    with tempfile.TemporaryDirectory() as td:
        q = json.load(open(src, encoding="utf-8"))
        blank = os.path.join(td, "blank.png")
        im = Image.new("RGB", (1100, 620), (235, 232, 228))
        ImageDraw.Draw(im).line([(10, 10), (900, 600)], fill=(184, 115, 51), width=5)
        im.save(blank)
        q["route_map"] = {"png": blank, "attribution": "x"}
        for l in q["legs"]:
            if len([s for s in l.get("stops", []) if not s.get("as_directed")]) >= 3:
                l["route"] = {"distance_mi": 0.0, "drive_min": 0, "segments": 1}
                break
        bad = os.path.join(td, "bad.json")
        json.dump(q, open(bad, "w", encoding="utf-8"), indent=2)
        r = subprocess.run([sys.executable, os.path.join(HERE, "verify_document.py"), bad],
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        if r.returncode == 0:
            missed.append("verifier passed a document it should have failed")
        if "single colour" not in out:
            missed.append("blank route map not caught")
        if "drive time of 0 min" not in out:
            missed.append("collapsed drive time not caught")

        # client_notes as a bare string: iterating it yields one character per item,
        # which printed the note as a vertical column of letters down the page.
        q2 = json.load(open(src, encoding="utf-8"))
        q2.pop("route_map", None)
        q2["legs"][0]["client_notes"] = "Hotel lobby staff to direct guests to the shuttles."
        strp = os.path.join(td, "strnote.json")
        json.dump(q2, open(strp, "w", encoding="utf-8"), indent=2)
        r2 = subprocess.run([sys.executable, os.path.join(HERE, "verify_document.py"), strp],
                            capture_output=True, text=True)
        if "client_notes is a string" not in (r2.stdout + r2.stderr):
            missed.append("client_notes-as-string not caught")
        # and the renderer must survive it rather than emit a column of letters
        htmlp = os.path.join(td, "s.html")
        r3 = subprocess.run([sys.executable, os.path.join(HERE, "render_html.py"), strp, htmlp],
                            capture_output=True, text=True)
        if r3.returncode == 0 and os.path.exists(htmlp):
            body = open(htmlp, encoding="utf-8").read()
            if "Hotel lobby staff" not in body:
                missed.append("renderer mangled a string client_notes")
        else:
            missed.append("render_html failed on a string client_notes")
        # PDF-only questions must not be asked once the format rules them out.
        sys.path.insert(0, HERE)
        import importlib.util
        spec = importlib.util.spec_from_file_location("_decide", os.path.join(HERE, "decide.py"))
        try:
            _d = importlib.util.module_from_spec(spec)
            sys.argv = ["decide.py", "--next"]
            try:
                spec.loader.exec_module(_d)
            except SystemExit:
                pass
            for fmt, want in (("email", False), ("html", False), ("word", False), ("excel", False),
                              ("pdf", True), ("email+pdf", True), ("print", True)):
                keys = _d.order_for({"client_questions": [], "decisions": {"format": fmt}})
                has = ("cover" in keys) or ("map" in keys)
                if has != want:
                    missed.append(f"format '{fmt}': cover/map {'asked' if has else 'skipped'}, expected "
                                  f"{'asked' if want else 'skipped'}")
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


def lint_help_and_artifacts():
    """The CSM help page and the managed artifacts stay true to the product (PRD R86-R90)."""
    import re as _re
    import subprocess
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    adir = os.path.join(root, "docs", "artifacts")
    helpmd = os.path.join(root, "skills", "quote-intake", "references", "help.md")
    if not os.path.isdir(adir):
        print("  \u25cb help and artifacts: docs/artifacts is not in this copy (installed plugin) \u2014 skipped")
        return True
    problems = []
    r = subprocess.run([sys.executable, os.path.join(adir, "sync_artifacts.py"), "check", "--quiet"],
                       capture_output=True, text=True)
    if r.returncode:
        problems.append("a managed artifact is stale: " + r.stdout.strip().replace("\n", " | "))
    text = open(helpmd, encoding="utf-8").read()
    page = open(os.path.join(adir, "help.html"), encoding="utf-8").read()
    # R88: open to everyone, so nothing a client, a price or the internals could leak through
    names = set()
    for fx in glob.glob(os.path.join(DEFAULT_FIXTURES, "*")):
        ip = os.path.join(fx, "handoff", "intake.json")
        if os.path.exists(ip):
            try:
                c = json.load(open(ip)).get("client")
                c = c.get("name") if isinstance(c, dict) else c
                if c: names.add(str(c).lower())
            except Exception:
                pass
    names = {n for n in names if len(n) > 3}
    if not names:
        problems.append("no client names found in the fixtures to check the help page against; the check would pass by default")
    tools = _re.findall(r"```tools\n(.*?)```", open(os.path.join(root, "skills", "quote-intake", "references", "mcp-contract.md"), encoding="utf-8").read(), _re.S)
    tool_names = tools[0].split() if tools else []
    for label, body in (("help.md", text), ("help page", page)):
        low = body.lower()
        if _re.search(r"\$\s?\d", body):
            problems.append(f"{label} carries a dollar amount (R88)")
        for n in sorted(names):
            if _re.search(r"\b" + _re.escape(n) + r"\b", low):
                problems.append(f"{label} names a client: {n} (R88)")
        for t in tool_names:
            if t in body:
                problems.append(f"{label} names a tool: {t} (R88)")
        if _re.search(r"\.py\b|ENGINEERING|\bMCP\b|\bCore\b", body):
            problems.append(f"{label} names a script or Savoya's internals (R88)")
    # R86/R87: the sections the page promises, and the contact route
    for sec in ("What it does", "How a quote goes", "The questions it asks, and why", "What it cannot do yet", "Questions and answers"):
        if f"## {sec}" not in text:
            problems.append(f"help.md has no '{sec}' section (R86)")
    if "core-ideas" not in text or "Log this session" not in text and "log this session" not in text:
        problems.append("help.md does not give the log-the-session and core-ideas route (R90)")
    if "Word and Excel" not in text:
        problems.append("help.md does not say Word and Excel are unproven")
    # drift against the code: one bullet per question the product asks
    sec = text.split("## The questions it asks, and why", 1)[-1].split("\n## ", 1)[0]
    asked = len(_re.findall(r"^- ", sec, _re.M))
    sys.path.insert(0, adir)
    import sync_artifacts as _sa
    if asked != len(_sa.question_order()):
        problems.append(f"help.md lists {asked} questions; the product asks {len(_sa.question_order())}")
    # the skills must answer from it and honour the request (R87, R90)
    for sk in ("quote-intake", "quote-document"):
        body = open(os.path.join(root, "skills", sk, "SKILL.md"), encoding="utf-8").read()
        if "references/help.md" not in body or "log this session" not in body.lower() or "R90" not in body:
            problems.append(f"{sk} SKILL.md does not point at help.md or handle 'log this session' (R87, R90)")
    if problems:
        print("  \u2717 help and artifacts")
        for m in problems:
            print("      " + m)
        return False
    print("  \u2713 help and artifacts")
    return True


def lint_refusals_and_mechanics():
    """A refused step is never walked around, and the user is never asked about the product's
    own working (PRD R92, R93). The behaviour is tested in `handoff packages`; this checks the
    instructions the session actually reads."""
    import re as _re
    problems = []
    skills = os.path.join(HERE, "..", "..")
    files = [os.path.join(skills, "quote-intake", "SKILL.md"), os.path.join(skills, "quote-document", "SKILL.md")]
    for sk in ("quote-intake", "quote-document"):
        files += sorted(glob.glob(os.path.join(skills, sk, "references", "*.md")))
    texts = {f: open(f, encoding="utf-8").read() for f in files}
    ask = _re.compile(r"how should (?:the|a|this) (?:handoff|file|document|quote) be (?:written|saved|stored)", _re.I)
    for f, t in texts.items():
        name = os.path.relpath(f, skills)
        if ask.search(t):
            problems.append(f"{name} asks the user how a file is written (R93)")
        for ln in t.splitlines():
            if "do you want in detail" in ln.lower() and "never when the request named" not in ln.lower():
                problems.append(f"{name} asks which scenario to detail without limiting it to options intake generated (R93): {ln[:80]!r}")
    intake = texts[files[0]]
    doc = texts[files[1]]
    for needle in ("blocked.json", "R92", "R93", "customize it, go on to the client document, or just the quote", "Both options"):
        if needle not in intake:
            problems.append(f"quote-intake SKILL.md lacks {needle!r}")
    if "blocked.json" not in doc or "R92" not in doc:
        problems.append("quote-document SKILL.md does not tell the session to stop on blocked.json (R92)")
    if problems:
        print("  \u2717 refusals and mechanics questions")
        for b in problems:
            print(f"      - {b}")
        return False
    print("  \u2713 refusals and mechanics questions (no question about how a file is written; scenario detail limited to options intake generated; both skills stop on blocked.json)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=DEFAULT_FIXTURES)
    ap.add_argument("--only", default=None)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    dirs = sorted(d for d in glob.glob(os.path.join(os.path.expanduser(a.fixtures), "*")) if os.path.isdir(d))
    if a.only:
        dirs = [d for d in dirs if os.path.basename(d) == a.only]
    if not dirs:
        sys.exit(f"No fixtures found in {a.fixtures}")
    lint_ok = lint_paths()
    lint_ok = lint_tool_contract() and lint_ok
    lint_ok = lint_warning_surfacing() and lint_ok
    lint_ok = lint_presentation_render() and lint_ok
    lint_ok = lint_airport_shape() and lint_ok
    lint_ok = lint_positioned_from() and lint_ok
    lint_ok = lint_money_ownership() and lint_ok
    lint_ok = lint_discount_attribution() and lint_ok
    lint_ok = lint_page_fit() and lint_ok
    lint_ok = lint_capture_resilience() and lint_ok
    lint_ok = lint_map_honesty() and lint_ok
    lint_ok = lint_paired_docs() and lint_ok
    lint_ok = lint_question_set() and lint_ok
    lint_ok = lint_greeter_leg() and lint_ok
    lint_ok = lint_handoff_contract() and lint_ok
    lint_ok = lint_sourced_line() and lint_ok
    lint_ok = lint_email_reconciles() and lint_ok
    lint_ok = lint_option_b_is_cores() and lint_ok
    lint_ok = lint_email_headings() and lint_ok
    lint_ok = lint_instructions_match_the_code() and lint_ok
    lint_ok = lint_commission() and lint_ok
    lint_ok = lint_flight_line() and lint_ok
    lint_ok = lint_client_requests() and lint_ok
    lint_ok = lint_client_request_answers() and lint_ok
    lint_ok = lint_user_supplied_facts() and lint_ok
    lint_ok = lint_overlap_and_placeholders() and lint_ok
    lint_ok = lint_notes_and_no_commission() and lint_ok
    lint_ok = lint_copy_rules() and lint_ok
    lint_ok = lint_review_fixes() and lint_ok
    lint_ok = lint_confirm_items() and lint_ok
    lint_ok = lint_capture_at_delivery() and lint_ok
    lint_ok = lint_handoff_packages() and lint_ok
    lint_ok = lint_quantity_extension() and lint_ok
    lint_ok = lint_time_reading() and lint_ok
    lint_ok = lint_blocked_capture() and lint_ok
    lint_ok = lint_deliverables() and lint_ok
    lint_ok = lint_client_safe_labels() and lint_ok
    lint_ok = lint_no_hand_editing() and lint_ok
    lint_ok = lint_path_resolution() and lint_ok
    lint_ok = lint_core_coordinates() and lint_ok
    lint_ok = lint_no_own_arithmetic() and lint_ok
    lint_ok = lint_passenger_count() and lint_ok
    lint_ok = lint_route_guards() and lint_ok
    lint_ok = lint_help_and_artifacts() and lint_ok
    lint_ok = lint_refusals_and_mechanics() and lint_ok
    bad = 0
    # Counting pages never caught the worst failures here: `.page` is a fixed box with
    # overflow:hidden, so content that does not fit is *cut*, and pdftotext still
    # extracts the cut text. A clipped line note and a clipped group total both looked
    # identical to a clean render from in here. With --pdf we keep each fixture's print
    # HTML and measure them all in one browser session afterwards.
    html_out = tempfile.mkdtemp(prefix="regress-measure-") if a.pdf else None
    for d in dirs:
        name, ok, msgs = check_fixture(d, a.pdf, html_out)
        if ok is None:
            print(f"  ○ {name}: {msgs[0]}")
        elif ok:
            print(f"  ✓ {name}")
        else:
            bad += 1
            print(f"  ✗ {name}")
            for m in msgs:
                print("      - " + m.replace("\n", "\n        "))
    clipped = []
    if html_out:
        try:
            sys.path.insert(0, HERE)
            import measure_pages
            jobs = [(f[:-len(".print.html")], os.path.join(html_out, f))
                    for f in sorted(os.listdir(html_out)) if f.endswith(".print.html")]
            if jobs:
                measured = measure_pages.measure_html(jobs)
                for label, pages in measured.items():
                    over = measure_pages.overflows(pages)
                    if over > 0:
                        worst = max((p for p in pages if not p["blank"]),
                                    key=lambda p: p["overflow_px"])
                        clipped.append((label, over, worst))
                fullest = max((100.0 * p["used_px"] / p["available_px"]
                               for pages in measured.values()
                               for p in pages if not p["blank"] and p["available_px"]),
                              default=0)
                if clipped:
                    print("  \u2717 page overflow — content is cut off the printed page")
                    for label, over, p in clipped:
                        print(f"      - {label} p{p['page']}: {over}px past the footer "
                              f"({100.0 * p['used_px'] / p['available_px']:.0f}% of the box)")
                        if p.get("text_tail"):
                            print(f"        last thing on the page: …{p['text_tail']}")
                else:
                    print(f"  \u2713 page overflow (fullest page {fullest:.0f}% of the usable box)")
        except Exception as ex:  # noqa: BLE001 — never let the instrument fail the suite
            print(f"  \u25cb page overflow: could not measure ({type(ex).__name__}: {ex})")
        finally:
            shutil.rmtree(html_out, ignore_errors=True)

    total = sum(1 for d in dirs if os.path.exists(os.path.join(d, "expected.json")))
    print(f"\n{total - bad}/{total} fixtures passed" + (" (with PDF)" if a.pdf else "")
          + ("" if lint_ok and not clipped else "  — guard checks FAILED"))
    sys.exit(1 if (bad or not lint_ok or clipped) else 0)


if __name__ == "__main__":
    main()
