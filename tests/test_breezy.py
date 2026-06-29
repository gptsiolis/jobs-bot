import os
import unittest
from unittest.mock import Mock, patch

import requests

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

from scrapers import breezy


class BreezyTests(unittest.TestCase):
    def setUp(self):
        breezy._FAILED_SLUGS.clear()

    def test_location_string_handles_dict_string_and_missing(self):
        self.assertEqual(
            breezy._location_string({"name": "Seattle, WA, United States"}),
            "Seattle, WA, United States",
        )
        self.assertEqual(
            breezy._location_string(
                {"city": "Austin", "state": "TX", "country": {"name": "United States"}}
            ),
            "Austin, TX, United States",
        )
        self.assertEqual(breezy._location_string("Remote - US"), "Remote - US")
        self.assertEqual(breezy._location_string(None), "")

    def test_is_remote_from_flag_and_text(self):
        self.assertTrue(breezy._is_remote({"name": "Anywhere", "is_remote": True}))
        self.assertTrue(breezy._is_remote({"name": "Remote, United States"}))
        self.assertFalse(breezy._is_remote({"name": "New York, NY"}))

    def test_normalize_builds_apply_url_when_missing(self):
        normalized = breezy._normalize_job(
            {"_id": "abc123", "name": "Operations Associate", "location": {"name": "New York, NY"}},
            "Arrived",
            "arrived",
        )
        self.assertEqual(normalized["job_id"], "breezy-abc123")
        self.assertEqual(normalized["employer_name"], "Arrived")
        self.assertEqual(normalized["source"], "breezy:Arrived")
        self.assertEqual(normalized["job_apply_link"], "https://arrived.breezy.hr/p/abc123")
        self.assertEqual(normalized["locations"], ["New York, NY"])

    @patch("scrapers.breezy.requests.get")
    def test_scrape_company_filters_and_attaches_fit(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = [
            {
                "_id": "1",
                "name": "Business Operations Associate",
                "location": {"name": "New York, NY"},
                "url": "https://arrived.breezy.hr/p/1",
                "description": "Entry level, 0-1 years.",
            },
            {
                "_id": "2",
                "name": "Senior Director of Engineering",
                "location": {"name": "New York, NY"},
                "url": "https://arrived.breezy.hr/p/2",
                "description": "10+ years required.",
            },
        ]
        mock_get.return_value = response

        jobs = breezy.scrape_company("Arrived", "arrived")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_title"], "Business Operations Associate")
        self.assertIn("fit_bucket", jobs[0])

    @patch("scrapers.breezy.requests.get")
    def test_fetch_records_failure_on_404(self, mock_get):
        response = Mock()
        response.status_code = 404
        response.ok = False
        mock_get.return_value = response

        self.assertIsNone(breezy._fetch("missing"))
        self.assertEqual(breezy._FAILED_SLUGS[0][0], "missing")
        self.assertEqual(breezy.get_failures()[0]["ats"], "breezy")

    @patch("scrapers.breezy.requests.get")
    def test_fetch_handles_request_exception(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("boom")
        self.assertIsNone(breezy._fetch("arrived"))
        self.assertEqual(breezy._FAILED_SLUGS[0][0], "arrived")


if __name__ == "__main__":
    unittest.main()
