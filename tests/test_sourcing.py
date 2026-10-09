import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "normalize_quote", ROOT / "skills/quote-document/scripts/normalize_quote.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourcingDocumentTest(unittest.TestCase):
    def test_uses_explicit_source_market_and_preserves_time_disclosure(self):
        unit = {
            "key": "suv_orange_county",
            "vehicle_type": {"id": 7, "name": "SUV", "capacity": 6},
            "quantity": 2,
            "unit_total": 25000,
            "line_total": 50000,
            "primary_service_area": {"id": 1, "name": "Los Angeles"},
            "source_service_area": {"id": 2, "name": "Orange County"},
            "stops": [
                {"name": "Pickup", "service_area": {"name": "Los Angeles"}},
                {"name": "Dropoff", "service_area": {"name": "Los Angeles"}},
            ],
            "pricing_summary": {
                "pricing_method": "hourly",
                "rate": {"effective_rate_amount": 10000, "minimum_hours": 2},
                "calculation": {"billable_hours": 2.5},
                "cancellation_hours": 24,
            },
            "sourcing_drive_time": {
                "additional_quoted_time_hours": 1.5,
                "incremental_client_amount": 30000,
            },
        }

        leg = MODULE.normalize_unit(unit, {})

        self.assertEqual(leg["service_area"], "Orange County")
        self.assertEqual(leg["primary_service_area"], "Los Angeles")
        self.assertEqual(leg["pricing"]["drive_time_price_change_cents"], 30000)
        self.assertIn("Orange County", leg["client_notes"][0])


if __name__ == "__main__":
    unittest.main()
