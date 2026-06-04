import os
import unittest

from scrapers import job_search
from storage import normalize_job_record


class FakeResponse:
    ok = True

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payload)


class JobSearchTests(unittest.TestCase):
    def test_normalizes_serpapi_job(self):
        raw = {
            "job_id": "abc123",
            "title": "Business Development Analyst",
            "company_name": "ExampleCo",
            "location": "New York, NY",
            "description": "Entry level role with salary $75,000 - $85,000 per year.",
            "apply_options": [{"link": "https://example.com/job"}],
        }

        job = job_search.normalize_job(raw, "business development analyst", "New York, NY")
        record = normalize_job_record(job)

        self.assertEqual(job["job_id"], "serpapi-6367c48dd193d56e")
        self.assertEqual(record["company"], "ExampleCo")
        self.assertEqual(record["visibility"], "default")
        self.assertEqual(record["compensation_min"], 75000)
        self.assertEqual(record["compensation_max"], 85000)

    def test_low_salary_is_stored_hidden_not_dropped(self):
        raw = {
            "job_id": "low-pay",
            "title": "Business Development Analyst",
            "company_name": "ExampleCo",
            "location": "Remote",
            "description": "This role pays $25/hour.",
        }

        job = job_search.normalize_job(raw, "business development analyst", "Remote")
        record = normalize_job_record(job)

        self.assertEqual(job["fit_bucket"], "reject")
        self.assertEqual(record["visibility"], "hidden")
        self.assertIn("compensation below floor", record["fit_reasons"])

    def test_scrape_uses_serpapi_pagination_token(self):
        os.environ["JOB_SEARCH_DAILY_REQUEST_LIMIT"] = "1"
        payload = {
            "jobs_results": [
                {
                    "job_id": "abc123",
                    "title": "Partnerships Associate",
                    "company_name": "ExampleCo",
                    "location": "Remote",
                    "description": "Entry level partnerships role.",
                }
            ],
            "serpapi_pagination": {"next_page_token": "next"},
        }
        session = FakeSession(payload)

        jobs = job_search.scrape(api_key="test", session=session)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][1]["engine"], "google_jobs")
        self.assertNotIn("location", session.calls[0][1])
        self.assertIn("remote", session.calls[0][1]["q"])

    def test_real_estate_investment_role_is_hidden(self):
        raw = {
            "job_id": "re-investment",
            "title": "Investment Analyst",
            "company_name": "RealEstateCo",
            "location": "New York, NY",
            "description": "Analyze real estate acquisitions and investment opportunities.",
        }

        job = job_search.normalize_job(raw, "investment analyst", "New York, NY")
        record = normalize_job_record(job)

        self.assertEqual(job["fit_bucket"], "reject")
        self.assertEqual(record["visibility"], "hidden")
        self.assertIn("investment role outside art/collectibles/crypto", record["fit_reasons"])


if __name__ == "__main__":
    unittest.main()
