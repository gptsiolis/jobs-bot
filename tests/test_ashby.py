import os
import unittest
from unittest.mock import Mock, patch

import requests

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

from scrapers import ashby


class AshbyTests(unittest.TestCase):
    def setUp(self):
        ashby._FAILED_SLUGS.clear()

    @patch("scrapers.ashby.time.sleep")
    @patch("scrapers.ashby.requests.get")
    def test_fetch_retries_timeout_then_succeeds(self, mock_get, mock_sleep):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = {"jobs": [{"id": "job_1"}]}
        mock_get.side_effect = [
            requests.Timeout("slow"),
            response,
        ]

        jobs = ashby._fetch("example")

        self.assertEqual(jobs, [{"id": "job_1"}])
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(ashby._FAILED_SLUGS, [])
        mock_sleep.assert_called_once()

    @patch("scrapers.ashby.time.sleep")
    @patch("scrapers.ashby.requests.get")
    def test_fetch_records_failure_after_all_retries(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.Timeout("slow")

        jobs = ashby._fetch("example")

        self.assertIsNone(jobs)
        self.assertEqual(mock_get.call_count, len(ashby.TIMEOUTS))
        self.assertEqual(ashby._FAILED_SLUGS[0][0], "example")
        self.assertEqual(mock_sleep.call_count, len(ashby.TIMEOUTS) - 1)

    @patch("scrapers.ashby.time.sleep")
    @patch("scrapers.ashby.requests.get")
    def test_fetch_does_not_retry_404(self, mock_get, mock_sleep):
        response = Mock()
        response.status_code = 404
        response.ok = False
        mock_get.return_value = response

        jobs = ashby._fetch("missing")

        self.assertIsNone(jobs)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(ashby._FAILED_SLUGS, [])
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
