"""Scraper for Ashby-hosted company job boards.

Public JSON API at https://api.ashbyhq.com/posting-api/job-board/<slug>
"""

import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def _fetch(slug):
    try:
        resp = requests.get(API.format(slug=slug), headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [!] Ashby fetch failed for slug {slug!r}: {e}")
        return None
    if resp.status_code == 404:
        print(f"  [!] Ashby: slug {slug!r} not found (404)")
        return None
    if not resp.ok:
        print(f"  [!] Ashby: slug {slug!r} returned {resp.status_code}")
        return None
    try:
        data = resp.json()
    except ValueError:
        print(f"  [!] Ashby: slug {slug!r} returned non-JSON")
        return None
    return data.get("jobs") or data.get("jobPostings") or []


def _normalize_job(job, company_name):
    location = job.get("location") or job.get("locationName") or ""
    is_remote = bool(job.get("isRemote")) or "remote" in location.lower()
    return {
        "job_id": f"ashby-{job.get('id', '')}",
        "job_title": job.get("title", ""),
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": job.get("jobUrl") or job.get("applyUrl") or "",
        "locations": [location] if location else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"ashby:{company_name}",
    }


def scrape_company(company_name, slug):
    raw_jobs = _fetch(slug)
    if not raw_jobs:
        return []
    matched = []
    for job in raw_jobs:
        normalized = _normalize_job(job, company_name)
        location_blob = " ".join(normalized["locations"])
        if not filters.passes_watchlist(
            normalized["job_title"], location_blob, normalized["employer_name"]
        ):
            continue
        matched.append(normalized)
    return matched


def scrape_all(company_boards):
    all_jobs = []
    ashby_companies = [
        (name, cfg["slug"])
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "ashby"
    ]
    print(f"Scraping {len(ashby_companies)} Ashby boards...")
    for company_name, slug in ashby_companies:
        jobs = scrape_company(company_name, slug)
        print(f"  {company_name} ({slug}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
