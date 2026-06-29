"""Scraper for Workable-hosted company job boards.

Public widget API at https://apply.workable.com/api/v1/widget/accounts/<slug>?details=true
returns {"name": ..., "jobs": [...]} — no auth.
"""

import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"


def _fetch(slug):
    try:
        resp = requests.get(API.format(slug=slug), headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [!] Workable fetch failed for slug {slug!r}: {e}")
        return None
    if not resp.ok:
        print(f"  [!] Workable: slug {slug!r} returned {resp.status_code}")
        return None
    try:
        return resp.json().get("jobs", [])
    except ValueError:
        return None


def _normalize_job(job, company_name):
    title = job.get("title", "")
    locs = job.get("locations") or []
    city = job.get("city", "") or ""
    state = job.get("state", "") or ""
    country = job.get("country", "") or ""
    if locs:
        loc_str = ", ".join(
            ", ".join(p for p in [l.get("city"), l.get("region"), l.get("country")] if p)
            for l in locs
        ) or country
    else:
        loc_str = ", ".join(p for p in [city, state, country] if p)
    is_remote = bool(job.get("telecommuting"))
    return {
        "job_id": f"workable-{job.get('shortcode', '')}",
        "job_title": title,
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": job.get("url") or job.get("shortlink") or "",
        "locations": [loc_str] if loc_str else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"workable:{company_name}",
        "job_description": job.get("description", "") or "",
    }


def scrape_company(company_name, slug):
    raw = _fetch(slug)
    if not raw:
        return []
    return filters.match_watchlist_jobs(
        _normalize_job(job, company_name) for job in raw
    )


def scrape_all(company_boards):
    all_jobs = []
    companies = [
        (name, cfg["slug"])
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "workable"
    ]
    print(f"Scraping {len(companies)} Workable boards...")
    for company_name, slug in companies:
        jobs = scrape_company(company_name, slug)
        print(f"  {company_name} ({slug}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
