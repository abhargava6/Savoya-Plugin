import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "skills/quote-intake/scripts/handoff.py"
NORMALIZE = ROOT / "skills/quote-document/scripts/normalize_quote.py"
ADJUST = ROOT / "skills/quote-document/scripts/apply_adjustments.py"
BUILD = ROOT / "skills/quote-document/scripts/rebuild_plugin.py"
CASES = json.loads((ROOT / "tests/fixtures/exact-response-cases.json").read_text())


def run(*args, env=None):
    return subprocess.run(
        [sys.executable, *map(str, args)], text=True, capture_output=True, env=env
    )


class MigrationTests(unittest.TestCase):
    def test_active_instructions_do_not_route_removed_tools(self):
        excluded = {"feedback-archive.md"}
        active = []
        for path in (ROOT / "skills").rglob("*"):
            if (
                path.is_file()
                and path.name not in excluded
                and "evals/fixtures/" not in str(path)
            ):
                if path.suffix in {".md", ".json", ".py"}:
                    active.append(path.read_text(errors="ignore"))
        text = "\n".join(active)
        self.assertNotIn("plan_approximate_quote_units", text)
        self.assertNotIn("calculate_quote_options", text)

    def test_exact_cases_and_blocked_case(self):
        spec = importlib.util.spec_from_file_location("handoff", HANDOFF)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ("ordinary", "temporary_rate", "temporary_discount", "combined"):
            self.assertEqual([], module.validate_exact(CASES[name]), name)
        self.assertTrue(module.validate_exact(CASES["blocked"]))
        with self.assertRaises(ValueError):
            module.result_for(CASES["complete_comparison"])
        selected, option = module.result_for(CASES["complete_comparison"], "value")
        self.assertEqual("value", option["key"])
        self.assertEqual(2, selected["quote_units"][0]["quantity"])

    def test_normalization_preserves_zero_and_core_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, out = pathlib.Path(tmp) / "raw.json", pathlib.Path(tmp) / "quote.json"
            raw.write_text(json.dumps(CASES["ordinary"]))
            result = run(NORMALIZE, raw, out, "--client", "Test")
            self.assertEqual(0, result.returncode, result.stderr)
            quote = json.loads(out.read_text())
            self.assertEqual(0, quote["total_cents"])
            self.assertEqual(0, quote["legs"][0]["pricing"]["base_rate_cents"])
            self.assertEqual(0, quote["legs"][0]["pricing"]["line_total_cents"])

    def test_verification_does_not_rebuild_aggregate_from_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            raw, quote = p / "raw.json", p / "quote.json"
            response = json.loads(json.dumps(CASES["ordinary"]))
            response["aggregate_total"] = 777
            raw.write_text(json.dumps(response))
            normalized = run(NORMALIZE, raw, quote, "--client", "Test")
            self.assertEqual(0, normalized.returncode, normalized.stderr)
            verified = run(
                ROOT / "skills/quote-document/scripts/verify_document.py",
                quote,
                "--raw",
                raw,
            )
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)

    def test_sixteen_leg_pagination_keeps_every_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            raw, quote = p / "raw.json", p / "quote.json"
            response = json.loads(json.dumps(CASES["ordinary"]))
            template = response["quote_units"][0]
            response["quote_units"] = []
            for index in range(16):
                unit = json.loads(json.dumps(template))
                unit["key"] = f"leg_{index + 1}"
                unit["label"] = f"Service {index + 1}"
                unit["pickup_date"] = f"2027-01-{index + 1:02d}T09:00:00-05:00"
                unit["stops"] = [{"name": "Pickup"}, {"name": "Drop-off"}]
                response["quote_units"].append(unit)
            response["aggregate_total"] = 0
            raw.write_text(json.dumps(response))
            normalized = run(NORMALIZE, raw, quote, "--client", "Pagination Test")
            self.assertEqual(0, normalized.returncode, normalized.stderr)
            spec = importlib.util.spec_from_file_location(
                "render_print", ROOT / "skills/quote-document/scripts/render_print.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            html = module.render_html(json.loads(quote.read_text()))
            for index in range(1, 17):
                self.assertIn(f"A{index}", html)
            self.assertGreaterEqual(html.count('<section class="page'), 4)

    def test_handoff_omits_passenger_and_preserves_source_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            handoff = p / "handoff"
            raw, source, request = p / "raw.json", p / "source.json", p / "request.md"
            raw.write_text(json.dumps(CASES["temporary_discount"]))
            source.write_text(
                json.dumps(
                    {
                        "quote_units": [
                            {
                                "key": "u1",
                                "passenger_count": 4,
                                "stops": [{"stop_ref": "signed_ref"}],
                                "vehicle_type_ids": [8],
                            }
                        ]
                    }
                )
            )
            request.write_text("quote")
            result = run(
                HANDOFF,
                "write",
                "--dir",
                handoff,
                "--client",
                "Test",
                "--profile-id",
                "1",
                "--request",
                request,
                "--raw",
                raw,
                "--source-request",
                source,
                "--tool",
                "calculate_temporary_quote_units",
                "--final",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            saved = json.loads((handoff / "source_request.json").read_text())
            self.assertNotIn("passenger_id", saved["quote_units"][0])
            self.assertEqual(
                "signed_ref", saved["quote_units"][0]["stops"][0]["stop_ref"]
            )
            self.assertEqual(8, saved["quote_units"][0]["vehicle_type_id"])
            intake = json.loads((handoff / "intake.json").read_text())
            self.assertEqual(3, intake["contract"])
            self.assertFalse(intake["persisted"])

    def test_comparison_source_request_selects_one_complete_option(self):
        spec = importlib.util.spec_from_file_location("handoff", HANDOFF)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        package, _ = module.result_for(CASES["complete_comparison"], "value")
        source = {
            "options": [
                {
                    "key": "value",
                    "quote_units": [
                        {"key": "u1", "passenger_count": 8, "vehicle_type_ids": [1, 8]}
                    ],
                },
                {
                    "key": "elevated",
                    "quote_units": [
                        {"key": "u1", "passenger_count": 8, "vehicle_type_id": 26}
                    ],
                },
            ]
        }
        selected = module.selected_request(source, package, "value")
        self.assertNotIn("options", selected)
        self.assertEqual(8, selected["quote_units"][0]["vehicle_type_id"])
        self.assertNotIn("vehicle_type_ids", selected["quote_units"][0])

    def test_discount_requote_and_mixed_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            source = {
                "quote_units": [
                    {"key": "a", "vehicle_type_id": 8},
                    {"key": "b", "vehicle_type_id": 8},
                ]
            }
            (p / "source_request.json").write_text(json.dumps(source))
            out = p / "request.json"
            result = run(
                HANDOFF, "prepare-discount", "--dir", p, "--percent", "10", "--out", out
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("calculate_temporary_quote_units", result.stdout)
            built = json.loads(out.read_text())
            self.assertTrue(
                all(
                    u["temporary_discount"]["basis_points"] == 1000
                    for u in built["quote_units"]
                )
            )
            source["quote_units"][0]["temporary_rate"] = {
                "amount": 50000,
                "rate_type": "transfer",
            }
            (p / "source_request.json").write_text(json.dumps(source))
            result = run(
                HANDOFF, "prepare-discount", "--dir", p, "--percent", "0", "--out", out
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Mixed temporary pricing", result.stderr)

    def test_cache_clear_preserves_unrelated_configuration(self):
        with tempfile.TemporaryDirectory() as home:
            config = pathlib.Path(home) / ".savoya-quoting/config.json"
            config.parent.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "known_clients": {"A": 1},
                        "known_passengers": {"1": {"id": 2}},
                        "user": "Ethan",
                        "theme": "dark",
                    }
                )
            )
            env = dict(os.environ, HOME=home)
            result = run(HANDOFF, "clear-cache", env=env)
            self.assertEqual(0, result.returncode, result.stderr)
            saved = json.loads(config.read_text())
            self.assertEqual({"user": "Ethan", "theme": "dark"}, saved)

    def test_capture_workflow_remains_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            handoff = p / "handoff"
            handoff.mkdir()
            (handoff / "request.md").write_text("quote")
            (handoff / "raw_quote.json").write_text(json.dumps(CASES["ordinary"]))
            (handoff / "intake.json").write_text(
                json.dumps({"contract": 3, "client": {"name": "Test"}, "log": []})
            )
            result = run(HANDOFF, "capture", "--dir", handoff)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(pathlib.Path(payload["path"]).exists())
            self.assertEqual(
                3,
                json.loads(pathlib.Path(payload["path"]).read_text())[
                    "capture_version"
                ],
            )

    def test_local_money_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            quote = pathlib.Path(tmp) / "quote.json"
            quote.write_text(json.dumps({"total_cents": 100}))
            result = run(ADJUST, quote, "--add", "Discount|percent|-10")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Local price changes are disabled", result.stderr)

    def test_mcp_override_changes_only_packaged_copy(self):
        source_config = (ROOT / ".mcp.json").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "build"
            result = run(
                BUILD,
                ROOT / "skills/quote-document",
                out,
                "--mcp-url",
                "https://public.example/mcp",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            packaged = json.loads((out / ".mcp.json").read_text())
            self.assertEqual(
                "https://public.example/mcp", packaged["mcpServers"]["savoya"]["url"]
            )
            self.assertEqual(
                "https://public.example/oauth/clients/claude.json",
                packaged["mcpServers"]["savoya"]["oauth"]["clientId"],
            )
            self.assertEqual(source_config, (ROOT / ".mcp.json").read_text())

    def test_acceptance_package_includes_matching_oauth_client_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "build"
            result = run(BUILD, ROOT / "skills/quote-document", out)
            self.assertEqual(0, result.returncode, result.stderr)
            packaged = json.loads((out / ".mcp.json").read_text())
            config = packaged["mcpServers"]["savoya"]
            self.assertEqual("https://mcp-acceptance.savoya.net/mcp", config["url"])
            self.assertEqual(
                "https://mcp-acceptance.savoya.net/oauth/clients/claude.json",
                config["oauth"]["clientId"],
            )


if __name__ == "__main__":
    unittest.main()
