"""Broad Google Jobs ingestion through SerpApi."""

import os
import re

import requests

from . import filters

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
DEFAULT_DAILY_REQUEST_LIMIT = 80
RESULTS_PER_QUERY_PAGE = 10
MAX_PAGES_PER_QUERY = 2

JOB_SEARCH_QUERIES = [
    "entry level business development associate",
    "business development analyst",
    "business development representative entry level",
    "entry level sales development representative",
    "partnerships associate",
    "partnerships analyst",
    "growth associate",
    "growth analyst",
    "business operations analyst entry level",
    "strategy operations associate",
    "analyst program business operations",
    "investment analyst entry level",
    "acquisitions analyst real estate",
    "asset management analyst real estate",
]

JOB_SEARCH_LOCATIONS = [
    "Remote",
    "New York, NY",
    "Los Angeles, CA",
    "San Francisco, CA",
    "Miami, FL",
    "Austin, TX",
    "Washington, DC",
    "Chicago, IL",
]

SENIOR_HARD_BLOCKS = (
    "senior",
    "sr.",
    "principal",
    "director",
    "vice president",
    "vp",
    "head of",
    "manager",
)


def _limit():
    try:
        return max(0, int(os.getenv("JOB_SEARCH_DAILY_REQUEST_LIMIT", DEFAULT_DAILY_REQUEST_LIMIT)))
    except ValueError:
        return DEFAULT_DAILY_REQUEST_LIMIT


def _search_queries():
    configured = os.getenv("JOB_SEARCH_QUERIES", "").strip()
    if not configured:
        return JOB_SEARCH_QUERIES
    return [q.strip() for q in configured.split(";") if q.strip()]


def _search_locations():
    configured = os.getenv("JOB_SEARCH_LOCATIONS", "").strip()
    if not configured:
        return JOB_SEARCH_LOCATIONS
    return [q.strip() for q in configured.split(";") if q.strip()]


def _fetch(params, session):
    response = session.get(SERPAPI_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _apply_link(job):
    options = job.get("apply_options") or []
    if options:
        return options[0].get("link") or job.get("share_link") or ""
    return job.get("share_link") or ""


def _description(job):
    parts = [job.get("description", "")]
    for item in job.get("job_highlights") or []:
        parts.extend(item.get("items") or [])
    detected = job.get("detected_extensions") or {}
    if detected.get("salary"):
        parts.append(str(detected["salary"]))
    parts.extend(str(value) for value in (job.get("extensions") or []) if value)
    return " ".join(part for part in parts if part)


def _compensation(description):
    text = filters._normalize_text(description).lower()
    annual = re.search(
        r"\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3})\s*(k)?\s*"
        r"(?:-|to|–|—)?\s*\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3})?\s*(k)?\s*"
        r"(?:per year|annually|annual|base salary|salary|/year|/yr)",
        text,
    )
    if not annual:
        return None, None

    def to_number(raw, suffix):
        value = float((raw or "0").replace(",", ""))
        if suffix == "k" or value < 1000:
            value *= 1000
        return int(value)

    first = to_number(annual.group(1), annual.group(2))
    second = (
        to_number(annual.group(3), annual.group(4) or annual.group(2))
        if annual.group(3)
        else first
    )
    return min(first, second), max(first, second)


def _hard_reject_reasons(title, location, description):
    blob = f"{title or ''} {description or ''}".lower()
    reasons = []
    if filters.is_logistics_operations(title, description):
        reasons.append("warehouse/logistics operations")
    if filters.compensation_below_floor(description):
        reasons.append("compensation below floor")
    if filters.is_internship(title):
        reasons.append("internship")
    if any(token in (title or "").lower() for token in SENIOR_HARD_BLOCKS):
        reasons.append("senior title")
    if not filters.is_allowed_location(location, title):
        reasons.append("outside target locations")
    if not filters.sponsor_eligibility_metadata(description).get("sponsor_eligible"):
        reasons.append("sponsorship or work authorization block")
    if "contract" in blob and "full time" not in blob and "full-time" not in blob:
        reasons.append("contract role")
    return reasons


def normalize_job(job, query, search_location):
    title = job.get("title", "")
    company = job.get("company_name", "") or "Unknown"
    location = job.get("location", "") or search_location
    description = _description(job)
    apply_url = _apply_link(job)
    source_id = job.get("job_id") or apply_url or f"{company}|{title}|{location}"
    comp_min, comp_max = _compensation(description)
    normalized = {
        "job_id": f"serpapi-{filters.stable_job_hash(source_id)}",
        "job_title": title,
        "employer_name": company,
        "job_city": "",
        "job_state": "",
        "job_country": "US",
        "job_is_remote": "remote" in location.lower(),
        "job_apply_link": apply_url,
        "locations": [location] if location else [],
        "work_mode": "remote" if "remote" in location.lower() else "",
        "source": "serpapi:google_jobs",
        "job_description": description,
        "raw_source_query": query,
        "raw_search_location": search_location,
        "compensation_min": comp_min,
        "compensation_max": comp_max,
        "ranking_version": "deterministic-v2",
    }
    filters.add_fit_metadata(normalized, description)
    reasons = _hard_reject_reasons(title, location, description)
    if reasons:
        normalized["fit_bucket"] = "reject"
        normalized["fit_reasons"] = list(dict.fromkeys((normalized.get("fit_reasons") or []) + reasons))
        normalized["visibility"] = "hidden"
    return normalized


def scrape(api_key=None, session=None):
    api_key = api_key or os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SERPAPI_KEY for job_search mode.")

    session = session or requests.Session()
    request_limit = _limit()
    requests_used = 0
    seen = set()
    jobs = []

    for query in _search_queries():
        for location in _search_locations():
            next_page_token = None
            for page in range(MAX_PAGES_PER_QUERY):
                if requests_used >= request_limit:
                    print(f"  Job search request cap reached ({request_limit}).")
                    return jobs
                params = {
                    "engine": "google_jobs",
                    "q": query,
                    "location": location,
                    "google_domain": "google.com",
                    "gl": "us",
                    "hl": "en",
                    "api_key": api_key,
                }
                if next_page_token:
                    params["next_page_token"] = next_page_token
                print(f"  Searching Google Jobs: {query!r} in {location} page {page + 1}")
                data = _fetch(params, session)
                requests_used += 1
                for raw in data.get("jobs_results") or []:
                    normalized = normalize_job(raw, query, location)
                    if normalized["job_id"] in seen:
                        continue
                    seen.add(normalized["job_id"])
                    jobs.append(normalized)
                pagination = data.get("serpapi_pagination") or {}
                next_page_token = pagination.get("next_page_token")
                if not next_page_token or len(data.get("jobs_results") or []) < RESULTS_PER_QUERY_PAGE:
                    break
    return jobs
