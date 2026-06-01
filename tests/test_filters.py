import os
import unittest

os.environ.setdefault("SENDER_EMAIL", "sender@example.com")
os.environ.setdefault("SENDER_PASSWORD", "password")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")

from scrapers import filters


class FilterTests(unittest.TestCase):
    def test_new_grad_title_passes(self):
        self.assertTrue(
            filters.passes_discovery(
                "New Grad Business Operations Associate",
                "Remote",
                "ExampleCo",
            )
        )
        metadata = filters.fit_metadata("New Grad Business Operations Associate")
        self.assertEqual(metadata["fit_bucket"], "strong")
        self.assertIn("new grad title", metadata["fit_reasons"])

    def test_entry_level_ops_titles_pass(self):
        titles = [
            "Operations Associate",
            "Business Operations Analyst",
            "Program Coordinator",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(filters.passes_watchlist(title, "New York, NY", "ExampleCo"))
                self.assertEqual(filters.fit_metadata(title)["fit_bucket"], "strong")

    def test_internships_are_excluded(self):
        self.assertFalse(
            filters.passes_discovery(
                "New Grad Operations Intern",
                "Remote",
                "ExampleCo",
            )
        )
        self.assertFalse(
            filters.passes_discovery(
                "Summer Analyst, Strategy",
                "Remote",
                "ExampleCo",
            )
        )

    def test_sales_only_no_longer_passes_without_early_career_signal(self):
        self.assertFalse(
            filters.passes_discovery(
                "Sales Development Representative",
                "Remote",
                "ExampleCo",
            )
        )
        self.assertTrue(
            filters.passes_discovery(
                "New Grad Sales Development Representative",
                "Remote",
                "ExampleCo",
            )
        )

    def test_positive_experience_description_ranks_strong(self):
        metadata = filters.fit_metadata(
            "Operations Analyst",
            "This role is designed for candidates with 0-1 years of experience.",
        )
        self.assertEqual(metadata["fit_bucket"], "strong")
        self.assertIn("0-1 years mentioned", metadata["fit_reasons"])

    def test_senior_description_rejects_broad_ops_but_keeps_entry_level_ops_possible(self):
        senior_description = "Requires 3+ years of experience in operations."
        self.assertFalse(
            filters.passes_watchlist(
                "Operations Manager",
                "Remote",
                "ExampleCo",
                senior_description,
            )
        )
        self.assertTrue(
            filters.passes_watchlist(
                "Operations Associate",
                "Remote",
                "ExampleCo",
                senior_description,
            )
        )
        metadata = filters.fit_metadata("Operations Associate", senior_description)
        self.assertEqual(metadata["fit_bucket"], "possible")

    def test_no_sponsorship_language_is_excluded(self):
        description = "Candidates must be authorized to work without sponsorship now or in the future."
        self.assertFalse(
            filters.passes_watchlist(
                "Operations Associate",
                "Remote",
                "ExampleCo",
                description,
            )
        )

    def test_citizenship_clearance_and_itar_language_are_excluded(self):
        blocked_descriptions = [
            "US citizenship is required for this role.",
            "This role requires an active security clearance.",
            "This position is subject to ITAR restrictions.",
        ]
        for description in blocked_descriptions:
            with self.subTest(description=description):
                self.assertFalse(
                    filters.passes_watchlist(
                        "Operations Associate",
                        "Remote",
                        "ExampleCo",
                        description,
                    )
                )

    def test_stem_opt_language_is_not_rejected(self):
        job = {
            "job_title": "Operations Associate",
            "job_description": "STEM OPT candidates are welcome to apply.",
        }
        filters.add_fit_metadata(job)
        self.assertTrue(job["sponsor_eligible"])
        self.assertIn("OPT/STEM OPT friendly", job["sponsor_reasons"])


if __name__ == "__main__":
    unittest.main()
