import os
import unittest

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

from scrapers import phenom


class PhenomParsingTests(unittest.TestCase):
    def test_find_jobs_list_nested(self):
        body = {"status": "success", "refineSearch": {"data": {"jobs": [
            {"title": "Ops Associate"}, {"title": "Analyst"}
        ]}}}
        jobs = phenom._find_jobs_list(body)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "Ops Associate")

    def test_find_jobs_list_direct_and_missing(self):
        self.assertEqual(
            phenom._find_jobs_list({"data": {"jobs": [{"jobTitle": "X"}]}})[0]["jobTitle"],
            "X",
        )
        self.assertIsNone(phenom._find_jobs_list({"data": {"totalCount": 0}}))
        self.assertIsNone(phenom._find_jobs_list({"jobs": []}))

    def test_location_string_variants(self):
        self.assertEqual(phenom._location_string({"cityState": "New York, NY"}), "New York, NY")
        self.assertEqual(
            phenom._location_string({"city": "Boston", "state": "MA", "country": "US"}),
            "Boston, MA, US",
        )
        self.assertEqual(
            phenom._location_string({"locations": [{"city": "Austin", "state": "TX"}]}),
            "Austin, TX",
        )

    def test_normalize_builds_absolute_apply_url(self):
        normalized = phenom._normalize_job(
            {"jobId": "42", "title": "Operations Associate", "applyUrl": "/us/en/job/42",
             "cityState": "New York, NY"},
            "Circle",
            "https://careers.circle.com",
        )
        self.assertEqual(normalized["job_id"], "phenom-42")
        self.assertEqual(normalized["source"], "phenom:Circle")
        self.assertEqual(normalized["job_apply_link"], "https://careers.circle.com/us/en/job/42")
        self.assertEqual(normalized["locations"], ["New York, NY"])

    def test_dedupe_by_job_id(self):
        raw = [{"jobId": "1", "title": "A"}, {"jobId": "1", "title": "A"}, {"jobId": "2", "title": "B"}]
        self.assertEqual(len(list(phenom._dedupe(raw))), 2)

    def test_match_filters_and_attaches_fit(self):
        raw = [
            {"jobId": "1", "title": "Business Operations Associate", "cityState": "New York, NY",
             "applyUrl": "https://careers.circle.com/us/en/job/1",
             "descriptionTeaser": "Entry level, 0-1 years."},
            {"jobId": "2", "title": "VP of Engineering", "cityState": "New York, NY",
             "applyUrl": "https://careers.circle.com/us/en/job/2",
             "descriptionTeaser": "12+ years, leadership."},
        ]
        matched = phenom._match(raw, "Circle", "https://careers.circle.com")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["job_title"], "Business Operations Associate")
        self.assertIn("fit_bucket", matched[0])

    def test_looks_like_jobs_response(self):
        self.assertTrue(phenom._looks_like_jobs_response("https://careers.circle.com/api/careersite/jobs"))
        self.assertFalse(phenom._looks_like_jobs_response("https://careers.circle.com/static/main.css"))

    def test_scrape_all_noop_without_phenom_boards(self):
        # Must not launch a browser when there are no phenom entries.
        self.assertEqual(phenom.scrape_all({"Stripe": {"ats": "greenhouse", "slug": "stripe"}}), [])


if __name__ == "__main__":
    unittest.main()
