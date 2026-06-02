import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

from scrapers import dayforce


class DayforceTests(unittest.TestCase):
    @patch("scrapers.dayforce.requests.get")
    def test_fetch_returns_json_list(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = [{"Title": "Business Development Associate"}]
        mock_get.return_value = response

        jobs = dayforce._fetch("example")

        self.assertEqual(jobs, [{"Title": "Business Development Associate"}])
        mock_get.assert_called_once()
        self.assertEqual(
            mock_get.call_args.kwargs["params"],
            {"includeActivePostingOnly": "true"},
        )

    @patch("scrapers.dayforce._fetch")
    def test_scrape_company_normalizes_filters_and_dedupes(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "Title": "Acquisitions - Analyst/Associate",
                "Description": "0-2 years of experience. Salary range is $90,000 - $110,000.",
                "ReferenceNumber": 650,
                "ApplyUrl": "https://jobs.dayforcehcm.com/en-US/example/jobs/650/apply",
                "City": "Chicago",
                "State": "IL",
                "Country": "USA",
                "IsVirtualLocation": False,
            },
            {
                "Title": "Acquisitions - Analyst/Associate",
                "Description": "0-2 years of experience.",
                "ReferenceNumber": 650,
                "ApplyUrl": "https://jobs.dayforcehcm.com/en-US/example/jobs/650/apply",
                "City": "Chicago",
                "State": "IL",
                "Country": "USA",
            },
            {
                "Title": "Warehouse Operations Associate",
                "Description": "Support inventory and warehouse workflows.",
                "ReferenceNumber": 651,
                "City": "Chicago",
                "State": "IL",
                "Country": "USA",
            },
        ]

        jobs = dayforce.scrape_company("Example Capital", "example")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "dayforce-example-650")
        self.assertEqual(jobs[0]["job_title"], "Acquisitions - Analyst/Associate")
        self.assertEqual(jobs[0]["locations"], ["Chicago, IL, USA"])
        self.assertEqual(jobs[0]["source"], "dayforce:Example Capital")
        self.assertEqual(jobs[0]["fit_bucket"], "possible")

    def test_virtual_location_sets_remote_work_mode(self):
        job = dayforce._normalize_job(
            {
                "Title": "Investment Analyst",
                "ReferenceNumber": 42,
                "ApplyUrl": "https://example.com/apply",
                "IsVirtualLocation": True,
            },
            "Example Capital",
            "example",
        )

        self.assertTrue(job["job_is_remote"])
        self.assertEqual(job["work_mode"], "remote")


if __name__ == "__main__":
    unittest.main()

