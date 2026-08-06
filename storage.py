"""Supabase storage for scraped jobs.

Uses Supabase's REST and RPC endpoints instead of adding a heavy client
dependency. Scheduled runs should use a service-role key.
"""

import datetime as _dt
import os
import re
import time
from collections import Counter
from urllib.parse import quote

import requests


JOB_STATUSES = (
    "new",
    "saved",
    "applied",
    "next_round",
    "rejected",
    "dismissed",
    "archived",
)
JOB_VISIBILITIES = ("default", "hidden", "needs_review")
# Statuses a job can hold while an inbound email might still move it forward or
# end it. Used by the email status updater to scope which jobs to match against.
INFLIGHT_STATUSES = ("applied", "applied_messaged", "next_round")
WATCHLIST_SOURCE_PREFIXES = (
    "greenhouse:",
    "lever:",
    "ashby:",
    "workday:",
    "workable:",
    "smartrecruiters:",
    "dayforce:",
)

FIT_SCORE = {
    "strong": 50,
    "possible": 35,
    "unknown": 15,
    "reject": -100,
}
SPONSOR_SCORE = {
    "strong_history": 25,
    "some_history": 15,
    "unknown_no_ban": 5,
    "explicit_no": -40,
}
QUALITY_SCORE = {
    "excellent": 15,
    "strong": 10,
    "acceptable": 3,
}

# Location tier bonuses. The user strongly prefers a handful of metros; every
# other allowed location still earns a small floor bonus. Most non-US jobs are
# filtered out before scoring, with explicit target metros such as Toronto
# allowed through by the shared location filter.
LOCATION_TIER_POINTS = {
    "top": 15,      # Miami, New York City — max points
    "a": 10,        # San Francisco, Los Angeles
    "b": 6,         # Chicago, Boston, Austin, Washington DC, Toronto
    "other_us": 2,  # anywhere else allowed by filters (incl. US-remote)
}
# Checked top tier first; the first tier with a matching city substring wins, so
# a posting tagged with several cities takes its highest-ranked metro. Matched by
# substring against the lowercased location string.
LOCATION_TIER_CITIES = (
    ("top", ("miami", "new york", "nyc", "manhattan", "brooklyn")),
    ("a", ("san francisco", "los angeles", "bay area")),
    ("b", (
        "chicago", "boston", "austin",
        # DC shows up in several spellings; "washington" alone is avoided so it
        # doesn't collide with Washington state (Seattle).
        "washington, dc", "washington dc", "washington d.c", "d.c.",
        "district of columbia", "toronto",
    )),
)

UPSERT_CHUNK_SIZE = 40
UPSERT_RETRIES = 3

# Operations / strategy / chief-of-staff is the top-priority target: these get
# a ranking bonus and are never auto-hidden on a low score.
PRIORITY_TITLE_TERMS = (
    "chief of staff",
    "operations",
    "strategy",
    "founder's associate",
    "founders associate",
    "founder associate",
)


def is_priority_role(job):
    if job.get("role_family") == "operations_strategy":
        return True
    title = (job.get("job_title") or "").lower()
    return any(term in title for term in PRIORITY_TITLE_TERMS)


def utc_now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def clean_text(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def job_location_string(job):
    locations = job.get("locations", [])
    city = job.get("job_city", "")
    state = job.get("job_state", "")
    if locations:
        location = ", ".join(locations)
    elif city or state:
        location = ", ".join(p for p in [city, state] if p)
    else:
        location = "Unknown"
    if job.get("job_is_remote") or job.get("work_mode") == "remote":
        return f"{location} (Remote)" if location != "Unknown" else "Remote"
    return location


def ats_from_source(source):
    source = source or ""
    if ":" in source:
        return source.split(":", 1)[0]
    if source in {"Y Combinator", "Wellfound"}:
        return source.lower().replace(" ", "_")
    return source.lower() or "unknown"


def _location_tier_bonus(location):
    """Points for how strongly the user prefers a job's metro.

    `location` is the already-lowercased location string. Named metros earn the
    tiered bonuses in LOCATION_TIER_POINTS (Miami/NYC highest); any other
    non-empty location that reached scoring is treated as elsewhere-in-the-US /
    remote and gets the small floor bonus. An empty/unknown location earns
    nothing, since we can't confirm it's even in the US.
    """
    if not location.strip():
        return 0
    for tier, cities in LOCATION_TIER_CITIES:
        if any(city in location for city in cities):
            return LOCATION_TIER_POINTS[tier]
    return LOCATION_TIER_POINTS["other_us"]


def calculate_applicability_score(job):
    """Score jobs on a 0-100 scale using the current fit/company metadata."""
    score = 0
    fit_bucket = job.get("fit_bucket") or "unknown"
    sponsor_tier = job.get("sponsor_tier") or "unknown_no_ban"
    quality_tier = job.get("quality_tier") or "acceptable"
    reasons = " ".join(job.get("fit_reasons") or []).lower()
    title = (job.get("job_title") or "").lower()
    description = clean_text(job.get("job_description", "")).lower()
    location = job_location_string(job).lower()

    score += FIT_SCORE.get(fit_bucket, 0)
    score += SPONSOR_SCORE.get(sponsor_tier, 0)
    score += QUALITY_SCORE.get(quality_tier, 0)

    if "new grad" in reasons or "entry-level" in reasons or "0-1 years" in reasons:
        score += 8
    if any(word in title for word in ("associate", "analyst", "coordinator", "new grad")):
        score += 10
    if is_priority_role(job):
        score += 15
    if any(word in title for word in ("business development", "partnership", "growth")):
        score += 8
    if "remote" in location:
        score += 4
    # Tiered metro preference: Miami/NYC max, SF/LA next, Chicago/Boston/Austin/DC
    # below that, and a small floor for anywhere else in the US. Stacks on top of
    # the remote bonus above (a US-remote role still counts as a location).
    score += _location_tier_bonus(location)
    if fit_bucket == "unknown":
        score -= 8
    if "2+ years" in reasons:
        score -= 12
    if "contract" in title or "contract" in description[:1500]:
        score -= 15
    if any(word in title for word in ("manager", "director", "lead", "head of")):
        score -= 25
    if any(
        word in f"{title} {description[:1500]}"
        for word in ("warehouse", "logistics", "supply chain", "inventory", "fleet")
    ):
        score -= 35
    if sponsor_tier == "unknown_no_ban":
        score -= 3

    ai_fit_score = _int_or_none(job.get("ai_fit_score"))
    if ai_fit_score is not None:
        # The AI judges attainability/fit from the full JD, so let it carry real
        # weight in the ordering (not just a light nudge).
        score = int(round((score * 0.55) + (max(0, min(100, ai_fit_score)) * 0.45)))

    ai_company_score = _int_or_none(job.get("ai_company_score"))
    if ai_company_score is not None:
        score += int(round((max(0, min(100, ai_company_score)) - 50) / 10))

    return max(0, min(100, score))


def job_visibility(job):
    explicit = job.get("visibility")
    if explicit in JOB_VISIBILITIES:
        return explicit
    if job.get("fit_bucket") == "reject":
        return "hidden"
    if calculate_applicability_score(job) < 55:
        return "hidden"
    return "default"


def normalize_job_record(job, now=None, status="new"):
    now = now or utc_now_iso()
    raw_payload = dict(job)
    description = clean_text(job.get("job_description", ""))
    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("job_title", ""),
        "company": job.get("employer_name", ""),
        "location_text": job_location_string(job),
        "apply_url": job.get("job_apply_link", ""),
        "source": job.get("source", ""),
        "ats": ats_from_source(job.get("source", "")),
        "first_seen_at": now,
        "last_seen_at": now,
        "fit_bucket": job.get("fit_bucket") or "unknown",
        "fit_reasons": list(job.get("fit_reasons") or []),
        "sponsor_tier": job.get("sponsor_tier") or "unknown_no_ban",
        "sponsor_reasons": list(job.get("sponsor_reasons") or []),
        "quality_tier": job.get("quality_tier") or "acceptable",
        "sector": job.get("sector") or "unknown",
        "applicability_score": calculate_applicability_score(job),
        "status": status,
        "visibility": job_visibility(job),
        "role_family": job.get("role_family") or "",
        "seniority_level": job.get("seniority_level") or "",
        "compensation_min": _int_or_none(job.get("compensation_min")),
        "compensation_max": _int_or_none(job.get("compensation_max")),
        "ai_fit_score": _int_or_none(job.get("ai_fit_score")),
        "ai_company_score": _int_or_none(job.get("ai_company_score")),
        "ai_summary": clean_text(job.get("ai_summary", "")),
        "ai_reject_reasons": list(job.get("ai_reject_reasons") or []),
        "ai_labels": list(job.get("ai_labels") or []),
        "ranking_version": job.get("ranking_version") or "deterministic-v2",
        "description_excerpt": description[:1200],
        "raw_payload": raw_payload,
    }


def migrated_seen_record(job_id, now=None):
    now = now or utc_now_iso()
    return {
        "job_id": job_id,
        "title": "Previously seen job",
        "company": "Unknown",
        "location_text": "Unknown",
        "apply_url": "",
        "source": "seen_jobs.json",
        "ats": "legacy",
        "first_seen_at": now,
        "last_seen_at": now,
        "fit_bucket": "unknown",
        "fit_reasons": [],
        "sponsor_tier": "unknown_no_ban",
        "sponsor_reasons": [],
        "quality_tier": "acceptable",
        "sector": "legacy",
        "applicability_score": 0,
        "status": "archived",
        "visibility": "hidden",
        "role_family": "",
        "seniority_level": "",
        "compensation_min": None,
        "compensation_max": None,
        "ai_fit_score": None,
        "ai_company_score": None,
        "ai_summary": "",
        "ai_reject_reasons": [],
        "ai_labels": [],
        "ranking_version": "legacy",
        "description_excerpt": "",
        "raw_payload": {"migrated_from": "seen_jobs.json", "legacy_job_id": job_id},
    }


def counts_by_source(jobs):
    return dict(Counter(job.get("source", "unknown") for job in jobs))


class SupabaseJobStore:
    def __init__(self, url=None, key=None, session=None):
        self.url = (url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.key = (
            key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or ""
        )
        self.session = session or requests.Session()
        if not self.url or not self.key:
            raise RuntimeError(
                "Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY."
            )

    @property
    def headers(self):
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _request(self, method, path, **kwargs):
        response = self.session.request(
            method,
            f"{self.url}{path}",
            headers={**self.headers, **kwargs.pop("headers", {})},
            timeout=kwargs.pop("timeout", 60),
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase {method} {path} failed: {response.text}")
        if not response.text:
            return None
        return response.json()

    def create_run(self, mode):
        data = self._request(
            "POST",
            "/rest/v1/job_runs",
            headers={"Prefer": "return=representation"},
            json={"mode": mode, "status": "running"},
        )
        return data[0]["id"]

    def finish_run(
        self,
        run_id,
        status,
        total_found=0,
        total_written=0,
        total_new=0,
        counts=None,
        failures=None,
        error=None,
    ):
        if not run_id:
            return None
        payload = {
            "status": status,
            "finished_at": utc_now_iso(),
            "total_found": total_found,
            "total_written": total_written,
            "total_new": total_new,
            "counts_by_source": counts or {},
            "failures": failures or [],
            "error": error,
        }
        return self._request(
            "PATCH",
            f"/rest/v1/job_runs?id=eq.{run_id}",
            headers={"Prefer": "return=minimal"},
            json=payload,
        )

    def upsert_jobs(self, jobs, dry_run=False):
        records = [normalize_job_record(job) for job in jobs if job.get("job_id")]
        if dry_run:
            return {
                "records": records,
                "total_written": len(records),
                "total_new": 0,
                "dry_run": True,
            }
        data = self._upsert_normalized_records(records)
        return {
            "records": records,
            "total_written": len(data or []),
            "total_new": sum(1 for row in data or [] if row.get("inserted")),
            "dry_run": False,
        }

    def upsert_records(self, records, dry_run=False):
        if dry_run:
            return {
                "records": records,
                "total_written": len(records),
                "total_new": 0,
                "dry_run": True,
            }
        data = self._upsert_normalized_records(records)
        return {
            "records": records,
            "total_written": len(data or []),
            "total_new": sum(1 for row in data or [] if row.get("inserted")),
            "dry_run": False,
        }

    def _upsert_normalized_records(self, records):
        written = []
        for start in range(0, len(records), UPSERT_CHUNK_SIZE):
            chunk = records[start : start + UPSERT_CHUNK_SIZE]
            for attempt in range(1, UPSERT_RETRIES + 1):
                try:
                    data = self._request(
                        "POST",
                        "/rest/v1/rpc/upsert_jobs",
                        json={"payload": chunk},
                        timeout=180,
                    )
                    written.extend(data or [])
                    break
                except requests.RequestException:
                    if attempt == UPSERT_RETRIES:
                        raise
                    time.sleep(2 * attempt)
        return written
    def archive_unmatched_new_jobs(self, current_job_ids, source_prefixes=None):
        data = self._request(
            "POST",
            "/rest/v1/rpc/archive_unmatched_new_jobs",
            json={
                "current_job_ids": list(current_job_ids),
                "source_prefixes": list(source_prefixes or WATCHLIST_SOURCE_PREFIXES),
            },
            timeout=120,
        )
        return int(data or 0)

    def reject_stale_applied_jobs(self, max_age_days=60):
        data = self._request(
            "POST",
            "/rest/v1/rpc/reject_stale_applied_jobs",
            json={"max_age_days": max_age_days},
            timeout=120,
        )
        return int(data or 0)

    def list_company_watchlist_requests(self):
        return self._request(
            "GET",
            "/rest/v1/company_watchlist_requests"
            "?select=id,company_name,normalized_name,status,ats_config,sector,quality_tier,"
            "sponsor_tier,source_notes,last_checked_at,last_error"
            "&status=in.(pending,resolved,unresolved)"
            "&order=created_at.asc",
        ) or []

    def update_company_watchlist_request(self, request_id, status, ats_config=None, error=None):
        payload = {
            "status": status,
            "ats_config": ats_config,
            "last_checked_at": utc_now_iso(),
            "last_error": error,
        }
        return self._request(
            "PATCH",
            f"/rest/v1/company_watchlist_requests?id=eq.{quote(str(request_id), safe='')}",
            headers={"Prefer": "return=minimal"},
            json=payload,
        )

    # --- Email status updater -------------------------------------------------

    def list_inflight_jobs(self):
        """Jobs that can still receive a status update from an inbound email."""
        statuses = ",".join(INFLIGHT_STATUSES)
        return self._request(
            "GET",
            "/rest/v1/jobs"
            "?select=job_id,title,company,status,apply_url,ats,source,applied_at"
            f"&status=in.({statuses})"
            "&order=applied_at.desc.nullslast",
        ) or []

    def processed_message_ids(self, message_ids):
        """Return the subset of message ids already handled in a prior run."""
        ids = [m for m in message_ids if m]
        if not ids:
            return set()
        in_list = ",".join(quote(str(m), safe="") for m in ids)
        rows = self._request(
            "GET",
            f"/rest/v1/processed_emails?select=message_id&message_id=in.({in_list})",
        ) or []
        return {row["message_id"] for row in rows}

    def record_processed_email(self, message_id, thread_id=None, job_id=None,
                               decision=None, confidence=None):
        if not message_id:
            return None
        return self._request(
            "POST",
            "/rest/v1/processed_emails?on_conflict=message_id",
            headers={"Prefer": "return=minimal,resolution=ignore-duplicates"},
            json={
                "message_id": message_id,
                "thread_id": thread_id,
                "job_id": job_id,
                "decision": decision,
                "confidence": confidence,
            },
        )

    def set_job_status(self, job_id, status):
        return self._request(
            "PATCH",
            f"/rest/v1/jobs?job_id=eq.{quote(str(job_id), safe='')}",
            headers={"Prefer": "return=minimal"},
            json={"status": status},
        )

    def log_job_note_event(self, job_id, event_type, old_status, new_status, notes):
        """Record an annotated status change so the audit trail keeps the
        email evidence alongside the bare change the trigger already logs."""
        return self._request(
            "POST",
            "/rest/v1/job_events",
            headers={"Prefer": "return=minimal"},
            json={
                "job_id": job_id,
                "event_type": event_type,
                "old_status": old_status,
                "new_status": new_status,
                "notes": notes,
            },
        )

    def insert_status_suggestion(self, suggestion):
        return self._request(
            "POST",
            "/rest/v1/status_suggestions?on_conflict=gmail_message_id,job_id",
            headers={"Prefer": "return=minimal,resolution=ignore-duplicates"},
            json=suggestion,
        )

    # --- Auto-apply engine ----------------------------------------------------

    def get_applicant_profile(self):
        rows = self._request(
            "GET",
            "/rest/v1/applicant_profile"
            "?select=full_name,email,phone,location,postal_code,linkedin_url,github_url,"
            "portfolio_url,years_experience,work_authorized,requires_sponsorship,"
            "willing_to_relocate,earliest_start,salary_expectation,minimum_salary,"
            "standard_answers,resume_path,resume_filename,resume_text"
            "&limit=1",
        ) or []
        return rows[0] if rows else None

    def list_drafts_by_status(self, status):
        """Queued (or other) drafts joined with the job they target."""
        return self._request(
            "GET",
            "/rest/v1/application_drafts"
            "?select=id,job_id,status,ats,apply_url,field_values,drafted_answers,"
            "jobs(title,company,apply_url,ats,location_text,description_excerpt,"
            "compensation_min,compensation_max)"
            f"&status=eq.{status}"
            "&order=created_at.asc",
        ) or []

    def update_draft(self, draft_id, payload):
        return self._request(
            "PATCH",
            f"/rest/v1/application_drafts?id=eq.{quote(str(draft_id), safe='')}",
            headers={"Prefer": "return=minimal"},
            json=payload,
        )

    def download_resume(self, resume_path):
        """Fetch raw resume bytes from the private Storage bucket (service role)."""
        response = self.session.get(
            f"{self.url}/storage/v1/object/resumes/{resume_path}",
            headers=self.headers,
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Resume download failed: {response.text}")
        return response.content

    def save_resume_text(self, resume_path, text):
        return self._request(
            "PATCH",
            f"/rest/v1/applicant_profile?resume_path=eq.{quote(str(resume_path), safe='')}",
            headers={"Prefer": "return=minimal"},
            json={"resume_text": text},
        )

    def upload_application_screenshot(self, dest_path, content, content_type="image/png"):
        """Upload (upsert) a confirmation/flag screenshot to the applications bucket."""
        response = self.session.post(
            f"{self.url}/storage/v1/object/applications/{dest_path}",
            headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"},
            data=content,
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Screenshot upload failed: {response.text}")
        return dest_path

    # --- Enrichment (enrich.py) ----------------------------------------------
    # The scrapers source a lot of jobs but shallowly: Getro/Consider carry no
    # description, and only the scrape-time AI ranker (capped) ever wrote AI
    # fields. enrich.py deepens the promising shortlist — fetch the real
    # description, then write an AI summary + personalized fit score. These two
    # helpers are how it reads the shortlist and writes results back.

    def list_jobs_needing_enrichment(self, limit=300, min_score=55):
        """Highest-scoring visible jobs that haven't been AI-enriched yet.

        "Not enriched yet" == empty ai_summary. We enrich only visible
        (non-hidden) jobs above the auto-hide score, best-first, so model spend
        goes to the jobs the user will actually see. Raise min_score to spend
        less; lower it for broader coverage.
        """
        return self._request(
            "GET",
            "/rest/v1/jobs"
            "?select=job_id,title,company,location_text,apply_url,ats,source,"
            "fit_bucket,role_family,applicability_score,description_excerpt"
            f"&visibility=eq.default&applicability_score=gte.{int(min_score)}"
            "&ai_summary=eq."
            "&order=applicability_score.desc,last_seen_at.desc"
            f"&limit={int(limit)}",
        ) or []

    def update_job_enrichment(self, job_id, fields):
        """Write fetched description and/or AI fields onto an existing job row.

        Direct PATCH (not the upsert) so enrichment is independent of the scrape
        path. Migration 017 stops the next scrape from clobbering these fields.
        """
        return self._request(
            "PATCH",
            f"/rest/v1/jobs?job_id=eq.{quote(str(job_id), safe='')}",
            headers={"Prefer": "return=minimal"},
            json=fields,
        )
