import unittest

from storage import (
    SupabaseJobStore,
    calculate_applicability_score,
    counts_by_source,
    job_visibility,
    migrated_seen_record,
    normalize_job_record,
)


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload
        self.text = "ok"

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/rest/v1/rpc/archive_unmatched_new_jobs"):
            return FakeResponse(17)
        if url.endswith("/rest/v1/rpc/reject_stale_applied_jobs"):
            return FakeResponse(3)
        return FakeResponse([{"job_id": "greenhouse-123", "inserted": True}])


class StorageTests(unittest.TestCase):
    def test_score_prioritizes_fit_sponsor_and_quality(self):
        strong = {
            "job_title": "Operations Associate",
            "job_description": "0-1 years of experience.",
            "locations": ["New York, NY"],
            "fit_bucket": "strong",
            "fit_reasons": ["entry-level ops title", "0-1 years mentioned"],
            "sponsor_tier": "strong_history",
            "quality_tier": "excellent",
        }
        unknown = {
            "job_title": "Operations",
            "locations": ["Remote"],
            "fit_bucket": "unknown",
            "fit_reasons": ["experience unknown"],
            "sponsor_tier": "unknown_no_ban",
            "quality_tier": "acceptable",
        }
        self.assertGreater(
            calculate_applicability_score(strong),
            calculate_applicability_score(unknown),
        )

    def test_operations_strategy_outranks_business_development(self):
        ops = {
            "job_title": "Business Operations Associate",
            "locations": ["New York, NY"],
            "fit_bucket": "strong",
            "role_family": "operations_strategy",
            "sponsor_tier": "unknown_no_ban",
            "quality_tier": "acceptable",
        }
        bd = {
            "job_title": "Business Development Associate",
            "locations": ["New York, NY"],
            "fit_bucket": "possible",
            "role_family": "business_development",
            "sponsor_tier": "unknown_no_ban",
            "quality_tier": "acceptable",
        }
        self.assertGreater(
            calculate_applicability_score(ops),
            calculate_applicability_score(bd),
        )

    def test_location_tiers_rank_metros_in_order(self):
        # Identical jobs that differ only by location should score strictly in
        # the user's preferred order: Miami/NYC > SF/LA > Chicago/Boston/Austin/DC
        # > anywhere else in the US.
        def job_in(location):
            return {
                "job_title": "Operations Associate",
                "locations": [location],
                "fit_bucket": "strong",
                "fit_reasons": ["entry-level ops title"],
                "sponsor_tier": "unknown_no_ban",
                "quality_tier": "acceptable",
            }

        top = calculate_applicability_score(job_in("Miami, FL"))
        nyc = calculate_applicability_score(job_in("New York, NY"))
        a_tier = calculate_applicability_score(job_in("San Francisco, CA"))
        b_tier = calculate_applicability_score(job_in("Chicago, IL"))
        dc = calculate_applicability_score(job_in("Washington, DC"))
        toronto = calculate_applicability_score(job_in("Toronto, ON"))
        other = calculate_applicability_score(job_in("Denver, CO"))

        self.assertEqual(top, nyc)
        self.assertEqual(b_tier, dc)
        self.assertEqual(b_tier, toronto)
        self.assertGreater(top, a_tier)
        self.assertGreater(a_tier, b_tier)
        self.assertGreater(b_tier, other)

    def test_low_fit_priority_role_is_hidden(self):
        # Priority roles still get the ranking boost, but a low-scoring one is
        # tucked behind the toggle rather than always shown.
        stretch = {
            "job_title": "Chief of Staff",
            "job_description": "Strong operating background preferred.",
            "locations": ["Remote"],
            "fit_bucket": "unknown",
            "role_family": "operations_strategy",
            "fit_reasons": ["experience unknown"],
            "sponsor_tier": "unknown_no_ban",
            "quality_tier": "acceptable",
        }
        self.assertLess(calculate_applicability_score(stretch), 55)
        self.assertEqual(job_visibility(stretch), "hidden")

    def test_normalize_job_record_maps_scraper_shape_to_database_shape(self):
        record = normalize_job_record(
            {
                "job_id": "greenhouse-123",
                "job_title": "Business Operations Analyst",
                "employer_name": "Stripe",
                "locations": ["Remote"],
                "job_is_remote": True,
                "job_apply_link": "https://example.com/apply",
                "source": "greenhouse:Stripe",
                "fit_bucket": "strong",
                "fit_reasons": ["entry-level ops title"],
                "sponsor_tier": "strong_history",
                "quality_tier": "excellent",
                "sector": "fintech",
            },
            now="2026-05-29T00:00:00+00:00",
        )
        self.assertEqual(record["job_id"], "greenhouse-123")
        self.assertEqual(record["title"], "Business Operations Analyst")
        self.assertEqual(record["ats"], "greenhouse")
        self.assertEqual(record["status"], "new")
        self.assertIn("Remote", record["location_text"])

    def test_migrated_seen_jobs_are_archived(self):
        record = migrated_seen_record("legacy-1", now="2026-05-29T00:00:00+00:00")
        self.assertEqual(record["status"], "archived")
        self.assertEqual(record["source"], "seen_jobs.json")
        self.assertEqual(record["raw_payload"]["legacy_job_id"], "legacy-1")

    def test_counts_by_source(self):
        self.assertEqual(
            counts_by_source([
                {"source": "greenhouse:Stripe"},
                {"source": "greenhouse:Stripe"},
                {"source": "lever:Plaid"},
            ]),
            {"greenhouse:Stripe": 2, "lever:Plaid": 1},
        )

    def test_upsert_jobs_uses_rpc_payload(self):
        session = FakeSession()
        store = SupabaseJobStore(
            url="https://example.supabase.co",
            key="service-role",
            session=session,
        )
        result = store.upsert_jobs([
            {
                "job_id": "greenhouse-123",
                "job_title": "Operations Associate",
                "employer_name": "Stripe",
                "source": "greenhouse:Stripe",
                "fit_bucket": "strong",
            }
        ])

        self.assertEqual(result["total_written"], 1)
        self.assertEqual(result["total_new"], 1)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/rest/v1/rpc/upsert_jobs"))
        self.assertEqual(kwargs["json"]["payload"][0]["status"], "new")

    def test_archive_unmatched_new_jobs_uses_rpc(self):
        session = FakeSession()
        store = SupabaseJobStore(
            url="https://example.supabase.co",
            key="service-role",
            session=session,
        )
        archived = store.archive_unmatched_new_jobs(["greenhouse-123"])

        self.assertEqual(archived, 17)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/rest/v1/rpc/archive_unmatched_new_jobs"))
        self.assertEqual(kwargs["json"]["current_job_ids"], ["greenhouse-123"])


class StaleAppliedStorageTests(unittest.TestCase):
    def test_reject_stale_applied_jobs_uses_rpc(self):
        session = FakeSession()
        store = SupabaseJobStore(
            url="https://example.supabase.co",
            key="service-role",
            session=session,
        )
        rejected = store.reject_stale_applied_jobs(max_age_days=60)

        self.assertEqual(rejected, 3)
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/rest/v1/rpc/reject_stale_applied_jobs"))
        self.assertEqual(kwargs["json"]["max_age_days"], 60)


if __name__ == "__main__":
    unittest.main()
