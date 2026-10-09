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


def check_fixture(fx, want_pdf):
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
        rc, out = run(cmd, work)
        if rc:
            return name, False, [f"apply_adjustments failed:\n{out}"]

        q = json.load(open(qpath, encoding="utf-8"))
        for k in ("engine_subtotal_cents", "total_cents"):
            if k in exp and q.get(k) != exp[k]:
                fails.append(f"{k}: expected {exp[k]} got {q.get(k)}")
        if "option_b_total_cents" in exp and (q.get("option_b") or {}).get("total_cents") != exp["option_b_total_cents"]:
            fails.append(f"option_b_total_cents: expected {exp['option_b_total_cents']} got {(q.get('option_b') or {}).get('total_cents')}")
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

        corpus = ""
        for p in (html_path, print_html):
            if os.path.exists(p):
                corpus += open(p, encoding="utf-8").read()
        if want_pdf and os.path.exists(pdf_path) and shutil.which("pdftotext"):
            corpus += subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
            if "pdf_pages" in exp and shutil.which("pdfinfo"):
                info = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
                pages = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), None)
                if pages != exp["pdf_pages"]:
                    fails.append(f"pdf_pages: expected {exp['pdf_pages']} got {pages}")
        if want_pdf and os.path.exists(pdf_path):
            rc, out = run([sys.executable, os.path.join(HERE, "verify_document.py"), qpath, "--pdf", pdf_path], work)
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


def lint_question_set():
    """Instruction prose must name the questions decide.py asks — no more, no fewer —
    and must never tell a session to apply a discount without going back to Core."""
    skills = os.path.normpath(os.path.join(HERE, "..", ".."))
    try:
        base, extra = document_question_keys()
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

    if problems:
        print("  ✗ question set")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  ✓ question set ({len(base)} asked, {len(extra)} conditional)")
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
            fb = [f for f in os.listdir(d) if f.endswith(".feedback.json")]
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
                if f.endswith((".capture.json", ".feedback.json")):
                    os.remove(os.path.join(d, f))

    if problems:
        print("  \u2717 capture resilience")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 capture resilience ({len(cases)} degraded inputs still captured)")
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

    if problems:
        print("  \u2717 paired docs")
        for b in problems:
            print(f"      - {b}")
        return False
    print(f"  \u2713 paired docs ({checked} checked, list derived not hardcoded)")
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
    print(f"\n{total - bad}/{total} fixtures passed" + (" (with PDF)" if a.pdf else "")
          + ("" if lint_ok else "  — guard checks FAILED"))
    sys.exit(1 if (bad or not lint_ok) else 0)


if __name__ == "__main__":
    main()
