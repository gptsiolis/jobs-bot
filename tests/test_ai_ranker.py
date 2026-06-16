import json
import os
import unittest

import ai_ranker


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "output": [
                {"content": [{"type": "output_text", "text": json.dumps(self._payload)}]}
            ]
        }


class FakeSession:
    def __init__(self, payload):
        self._payload = payload

    def post(self, *args, **kwargs):
        return FakeResponse(self._payload)


class AiRankerTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: os.environ.get(k)
            for k in ("AI_RANKING_ENABLED", "OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
        }
        os.environ["AI_RANKING_ENABLED"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-key"
        # Disable the feedback-history fetch so the test makes no network call.
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_rank_jobs_applies_ai_metadata_without_clobbering_role_family(self):
        payload = {
            "jobs": [
                {
                    "job_id": "job-1",
                    "attainable": True,
                    "fit_score": 88,
                    "company_score": 80,
                    "seniority_level": "entry",
                    "summary": "Strong early-career ops fit.",
                    "reject_reasons": [],
                    "labels": ["ops"],
                },
                {
                    "job_id": "job-2",
                    "attainable": False,
                    "fit_score": 30,
                    "company_score": 70,
                    "seniority_level": "senior",
                    "summary": "Senior ops leadership role.",
                    "reject_reasons": ["requires significant experience"],
                    "labels": [],
                },
            ]
        }
        jobs = [
            {
                "job_id": "job-1",
                "job_title": "Business Operations Associate",
                "employer_name": "ExampleCo",
                "locations": ["Remote"],
                "fit_bucket": "strong",
                "role_family": "operations_strategy",
                "job_description": "Entry-level operations role.",
            },
            {
                "job_id": "job-2",
                "job_title": "Head of Operations",
                "employer_name": "ExampleCo",
                "locations": ["New York, NY"],
                "fit_bucket": "possible",
                "role_family": "operations_strategy",
                "job_description": "Requires 10+ years leading operations teams.",
            },
        ]

        result = ai_ranker.rank_jobs(jobs, session=FakeSession(payload))

        self.assertTrue(result["enabled"])
        self.assertEqual(result["ranked"], 2)
        self.assertEqual(jobs[0]["ai_fit_score"], 88)
        # role_family must NOT be overwritten by the AI ranker.
        self.assertEqual(jobs[0]["role_family"], "operations_strategy")
        # Attainable -> visibility left to the deterministic score.
        self.assertNotIn("visibility", jobs[0])
        # Not attainable -> hidden.
        self.assertEqual(jobs[1]["visibility"], "hidden")
        self.assertEqual(jobs[1]["ranking_version"], "ai-v2")

    def test_rank_jobs_skips_rejects(self):
        jobs = [{"job_id": "job-x", "job_title": "X", "fit_bucket": "reject"}]
        result = ai_ranker.rank_jobs(jobs, session=FakeSession({"jobs": []}))
        self.assertEqual(result["ranked"], 0)


if __name__ == "__main__":
    unittest.main()
