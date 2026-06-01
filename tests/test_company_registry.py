import csv
import os
import tempfile
import unittest

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

import config
from company_registry import (
    company_boards,
    metadata_for_company,
    validate_registry,
)
from scripts.build_sponsor_scores import build_scores


class CompanyRegistryTests(unittest.TestCase):
    def test_config_uses_registry_boards_with_metadata(self):
        self.assertIn("Stripe", config.COMPANY_BOARDS)
        self.assertEqual(config.COMPANY_BOARDS["Stripe"]["ats"], "greenhouse")
        self.assertEqual(config.COMPANY_BOARDS["Stripe"]["sponsor_tier"], "strong_history")
        self.assertEqual(config.COMPANY_BOARDS["Stripe"]["quality_tier"], "excellent")

    def test_registry_validation_catches_bad_entries(self):
        errors = validate_registry([
            {
                "name": "Example",
                "sector": "saas",
                "quality_tier": "excellent",
                "sponsor_tier": "explicit_no",
                "ats": {"type": "greenhouse", "slug": "example"},
            },
            {
                "name": "Example",
                "sector": "saas",
                "quality_tier": "bad",
                "sponsor_tier": "unknown_no_ban",
                "enabled": True,
            },
        ])
        self.assertTrue(any("explicit_no" in error for error in errors))
        self.assertTrue(any("duplicate company" in error for error in errors))
        self.assertTrue(any("invalid quality_tier" in error for error in errors))
        self.assertTrue(any("missing ats config" in error for error in errors))

    def test_metadata_defaults_for_unknown_company(self):
        metadata = metadata_for_company("Unknown Startup")
        self.assertEqual(metadata["sponsor_tier"], "unknown_no_ban")
        self.assertEqual(metadata["quality_tier"], "acceptable")

    def test_company_boards_skips_disabled_candidates(self):
        boards = company_boards()
        self.assertIn("Stripe", boards)
        self.assertIn("Airbnb", boards)
        self.assertNotIn("Adobe", boards)

    def test_build_sponsor_scores_from_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "oflc.csv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["EMPLOYER_NAME", "CASE_STATUS", "VISA_CLASS"],
                )
                writer.writeheader()
                writer.writerow({
                    "EMPLOYER_NAME": "Stripe, Inc.",
                    "CASE_STATUS": "Certified",
                    "VISA_CLASS": "H-1B",
                })
                writer.writerow({
                    "EMPLOYER_NAME": "Stripe Inc",
                    "CASE_STATUS": "Denied",
                    "VISA_CLASS": "H-1B",
                })
            scores = build_scores([path])
        self.assertEqual(scores["stripe"]["recent_lca_count"], 1)
        self.assertEqual(scores["stripe"]["statuses"]["Denied"], 1)


if __name__ == "__main__":
    unittest.main()
