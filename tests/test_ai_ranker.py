import json
import os
import unittest

import ai_ranker


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "jobs": [
                                        {
                                            "job_id": "job-1",
                                            "fit_score": 91,
                                            "company_score": 80,
                                            "role_family": "business development",
                                            "seniority_level": "entry",
                                            "summary": "Strong early-career BD fit.",
                                            "reject_reasons": [],
                                            "labels": ["bd", "entry"],
                                            "visibility": "default",
                                        }
                                    ]
                                }
                            ),
                        }
                    ]
                }
            ]
        }


class FakeSession:
    def post(self, *args, **kwargs):
        return FakeResponse()


class AiRankerTests(unittest.TestCase):
    def setUp(self):
        self.old_enabled = os.environ.get("AI_RANKING_ENABLED")
        self.old_key = os.environ.get("OPENAI_API_KEY")
        os.environ["AI_RANKING_ENABLED"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-key"

    def tearDown(self):
        if self.old_enabled is None:
            os.environ.pop("AI_RANKING_ENABLED", None)
        else:
            os.environ["AI_RANKING_ENABLED"] = self.old_enabled
        if self.old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self.old_key

    def test_rank_jobs_applies_ai_metadata(self):
        jobs = [
            {
                "job_id": "job-1",
                "job_title": "Business Development Associate",
                "employer_name": "ExampleCo",
                "locations": ["Remote"],
                "source": "serpapi:google_jobs",
                "fit_bucket": "strong",
                "fit_reasons": [],
                "job_description": "Entry level BD role.",
            }
        ]

        result = ai_ranker.rank_jobs(jobs, session=FakeSession())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["ranked"], 1)
        self.assertEqual(jobs[0]["ai_fit_score"], 91)
        self.assertEqual(jobs[0]["role_family"], "business development")
        self.assertEqual(jobs[0]["visibility"], "default")


if __name__ == "__main__":
    unittest.main()
