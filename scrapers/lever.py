"""Scraper for Lever-hosted company job boards.

Public JSON API at https://api.lever.co/v0/postings/<slug>?mode=json —
no auth, returns a list of postings.
"""

import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _fetch(slug):
    try:
        resp = requests.get(API.format(slug=slug), headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [!] Lever fetch failed for slug {slug!r}: {e}")
        return None
    if resp.status_code == 404:
        print(f"  [!] Lever: slug {slug!r} not found (404)")
        return None
    if not resp.ok:
        print(f"  [!] Lever: slug {slug!r} returned {resp.status_code}")
        return None
    try:
        data = resp.json()
    except ValueError:
        print(f"  [!] Lever: slug {slug!r} returned non-JSON")
        return None
    if not isinstance(data, list):
        return None
    return data


def _job_description(job):
    parts = [
        job.get("description", ""),
        job.get("descriptionPlain", ""),
        job.get("additionalPlain", ""),
    ]
    for section in job.get("lists") or []:
        parts.append(section.get("text", ""))
        parts.append(section.get("content", ""))
    return " ".join(p for p in parts if p)


def _normalize_job(job, company_name):
    cats = job.get("categories") or {}
    location = cats.get("location") or ""
    commitment = cats.get("commitment") or ""
    workplace = (job.get("workplaceType") or "").lower()
    is_remote = workplace == "remote" or "remote" in location.lower()
    return {
        "job_id": f"lever-{job.get('id', '')}",
        "job_title": job.get("text", "") or job.get("title", ""),
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": job.get("hostedUrl") or job.get("applyUrl") or "",
        "locations": [location] if location else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"lever:{company_name}",
        "job_description": _job_description(job),
    }


def scrape_company(company_name, slug):
    raw_jobs = _fetch(slug)
    if not raw_jobs:
        return []
    matched = []
    for job in raw_jobs:
        normalized = _normalize_job(job, company_name)
        location_blob = " ".join(normalized["locations"])
        description = normalized.get("job_description", "")
        if not filters.passes_watchlist(
            normalized["job_title"], location_blob, normalized["employer_name"],
            description,
        ):
            continue
        filters.add_fit_metadata(normalized, description)
        matched.append(normalized)
    return matched


def scrape_all(company_boards):
    all_jobs = []
    lever_companies = [
        (name, cfg["slug"])
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "lever"
    ]
    print(f"Scraping {len(lever_companies)} Lever boards...")
    for company_name, slug in lever_companies:
        jobs = scrape_company(company_name, slug)
        print(f"  {company_name} ({slug}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
