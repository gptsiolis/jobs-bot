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
        self.assertEqual(metadata["role_family"], "operations_strategy")
        self.assertIn("operations/strategy/chief-of-staff title", metadata["fit_reasons"])

    def test_operations_strategy_is_top_priority_family(self):
        # The user's priority family: surfaced as strong even with no body text.
        for title in ["Chief of Staff", "Business Operations Associate", "Strategy & Operations"]:
            with self.subTest(title=title):
                metadata = filters.fit_metadata(title)
                self.assertEqual(metadata["fit_bucket"], "strong")
                self.assertEqual(metadata["role_family"], "operations_strategy")

    def test_entry_level_ops_titles_pass(self):
        # Operations / strategy / chief-of-staff (priority family) rank strong.
        strong_titles = [
            "Operations Associate",
            "Business Operations Analyst",
        ]
        for title in strong_titles:
            with self.subTest(title=title):
                self.assertTrue(filters.passes_watchlist(title, "New York, NY", "ExampleCo"))
                self.assertEqual(filters.fit_metadata(title)["fit_bucket"], "strong")
        # Business development / partnerships are secondary: still surfaced, ranked possible.
        secondary_titles = [
            "Business Development Representative",
            "Partnerships Associate",
        ]
        for title in secondary_titles:
            with self.subTest(title=title):
                self.assertTrue(filters.passes_watchlist(title, "New York, NY", "ExampleCo"))
                self.assertEqual(filters.fit_metadata(title)["fit_bucket"], "possible")

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

    def test_sales_titles_surface_with_entry_level_signal(self):
        # Sales is broadened now: SDR carries an entry-level signal
        # ('representative') and is surfaced.
        self.assertTrue(
            filters.passes_discovery(
                "Sales Development Representative",
                "Remote",
                "ExampleCo",
            )
        )
        # A bare sales title with no entry-level word or body signal stays out.
        self.assertFalse(
            filters.passes_discovery(
                "Account Executive",
                "Remote",
                "ExampleCo",
            )
        )

    def test_coordinator_titles_are_excluded(self):
        for title in ["Workplace Coordinator", "Office Coordinator", "Program Coordinator"]:
            with self.subTest(title=title):
                self.assertFalse(filters.passes_watchlist(title, "New York, NY", "ExampleCo"))
                self.assertFalse(filters.passes_discovery(title, "Remote", "ExampleCo"))

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

    def test_generalist_operations_is_surfaced_but_senior_is_dropped(self):
        # Generalist ops is the priority family now -> surfaced (not rejected).
        self.assertTrue(
            filters.passes_watchlist(
                "Operations Specialist",
                "Remote",
                "ExampleCo",
                "Own cross-functional operational processes.",
            )
        )
        # Senior ops titles are still dropped by the seniority gate.
        self.assertFalse(
            filters.passes_watchlist(
                "Product Operations Manager",
                "Remote",
                "ExampleCo",
                "Own cross-functional operational processes.",
            )
        )

    def test_non_us_locations_are_excluded_even_when_remote(self):
        blocked = [
            "Remote - Ireland",
            "Sydney, NSW, Australia",
            "Quezon City, Metro Manila, Philippines",
            "Canada - Remote (ON, AB, BC, or NS Only)",
            "Israel (Remote)",
            "London, UK",
        ]
        for location in blocked:
            with self.subTest(location=location):
                self.assertFalse(filters.is_allowed_location(location))

    def test_us_remote_and_target_metros_are_allowed(self):
        allowed = [
            "Remote - US",
            "United States, Remote",
            "New York, NY",
            "San Francisco, CA",
            "Toronto, ON, Canada",
            "Indianapolis, IN (Remote)",  # US remote; must not be flagged non-US
            "Milwaukee, WI (Remote)",     # must not match "uk" in Milwaukee
        ]
        for location in allowed:
            with self.subTest(location=location):
                self.assertTrue(filters.is_allowed_location(location))

    def test_other_cities_in_target_states_are_excluded(self):
        # State abbreviations must not leak the whole state.
        for location in ["Lake Charles, LA, United States", "Buffalo, NY, USA", "Rochester, NY"]:
            with self.subTest(location=location):
                self.assertFalse(filters.is_allowed_location(location))

    def test_five_plus_years_is_rejected(self):
        for desc in [
            "Requires 5+ years of experience.",
            "Minimum of 7 years in operations.",
            "8-10 years of relevant experience required.",
        ]:
            with self.subTest(desc=desc):
                self.assertEqual(
                    filters.fit_metadata("Operations Associate", desc)["fit_bucket"], "reject"
                )
        # An explicit entry-level signal protects against a stray high number.
        self.assertNotEqual(
            filters.fit_metadata(
                "Operations Associate",
                "Great for new grads with 0-1 years; our team has 10+ years combined.",
            )["fit_bucket"],
            "reject",
        )

    def test_warehouse_and_logistics_operations_are_excluded(self):
        blocked = [
            ("Warehouse Operations Associate", "New York, NY", ""),
            ("Operations Coordinator", "Los Angeles, CA", "Support logistics and inventory control."),
            ("Food Operations Specialist", "Remote", "Manage food operations vendors."),
        ]
        for title, location, description in blocked:
            with self.subTest(title=title):
                self.assertFalse(
                    filters.passes_watchlist(title, location, "ExampleCo", description)
                )

    def test_low_compensation_is_excluded_when_posted(self):
        low_comp = [
            "This role pays $25/hour.",
            "The salary range is $55,000 - $65,000 per year.",
        ]
        for description in low_comp:
            with self.subTest(description=description):
                self.assertFalse(
                    filters.passes_watchlist(
                        "Operations Associate",
                        "Remote",
                        "ExampleCo",
                        description,
                    )
                )

    def test_compensation_floor_allows_ranges_that_can_clear_70k(self):
        self.assertTrue(
            filters.passes_watchlist(
                "Business Development Associate",
                "Remote",
                "ExampleCo",
                "The salary range is $65,000 - $80,000 per year.",
            )
        )

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

    def test_investment_roles_must_be_art_collectibles_or_crypto(self):
        self.assertFalse(
            filters.passes_watchlist(
                "Investment Analyst",
                "New York, NY",
                "RealEstateCo",
                "Analyze real estate acquisitions and property investment opportunities.",
            )
        )
        self.assertFalse(
            filters.passes_watchlist(
                "Asset Management Analyst",
                "New York, NY",
                "RealEstateCo",
                "Support real estate portfolio operations.",
            )
        )
        self.assertTrue(
            filters.passes_watchlist(
                "Crypto Investment Analyst",
                "New York, NY",
                "ExampleCo",
                "Analyze digital assets, blockchain markets, and token investments.",
            )
        )
        self.assertTrue(
            filters.passes_watchlist(
                "Investment Analyst",
                "New York, NY",
                "Sothebys",
                "Analyze art and collectibles markets.",
            )
        )


if __name__ == "__main__":
    unittest.main()
