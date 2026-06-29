"""Scraper for Breezy HR-hosted company job boards.

Breezy exposes an anonymous public board feed for each company at:

    https://<slug>.breezy.hr/json

It returns a JSON array of position objects (title, location, description
HTML, apply URL). No auth required.
"""

import requests

from . import filters

HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
API = "https://{slug}.breezy.hr/json"

_FAILED_SLUGS = []


def _fetch(slug):
    try:
        resp = requests.get(API.format(slug=slug), headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"  [!] Breezy fetch failed for slug {slug!r}: {e}")
        _FAILED_SLUGS.append((slug, str(e)))
        return None
    if resp.status_code == 404:
        print(f"  [!] Breezy: slug {slug!r} not found (404)")
        _FAILED_SLUGS.append((slug, "404"))
        return None
    if not resp.ok:
        print(f"  [!] Breezy: slug {slug!r} returned {resp.status_code}")
        _FAILED_SLUGS.append((slug, f"returned {resp.status_code}"))
        return None
    try:
        data = resp.json()
    except ValueError:
        print(f"  [!] Breezy: slug {slug!r} returned non-JSON")
        _FAILED_SLUGS.append((slug, "returned non-JSON"))
        return None
    if isinstance(data, list):
        return data
    return data.get("positions") or data.get("jobs") or []


def _location_string(location):
    """Breezy location may be a dict, a string, or missing."""
    if isinstance(location, dict):
        name = location.get("name") or ""
        if name:
            return name
        parts = [
            location.get("city"),
            location.get("state"),
            (location.get("country") or {}).get("name")
            if isinstance(location.get("country"), dict)
            else location.get("country"),
        ]
        return ", ".join(str(p).strip() for p in parts if p)
    if isinstance(location, str):
        return location
    return ""


def _is_remote(location):
    if isinstance(location, dict):
        if location.get("is_remote") or location.get("remote"):
            return True
    return "remote" in _location_string(location).lower()


def _normalize_job(job, company_name, slug):
    location = job.get("location")
    location_str = _location_string(location)
    is_remote = _is_remote(location)
    job_id = job.get("_id") or job.get("id") or job.get("friendly_id") or ""
    apply_url = job.get("url") or ""
    if not apply_url and job_id:
        apply_url = f"https://{slug}.breezy.hr/p/{job_id}"
    return {
        "job_id": f"breezy-{job_id}",
        "job_title": job.get("name", "") or job.get("title", "") or "",
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "locations": [location_str] if location_str else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"breezy:{company_name}",
        "job_description": job.get("description", "") or "",
    }


def scrape_company(company_name, slug):
    raw_jobs = _fetch(slug)
    if not raw_jobs:
        return []
    return filters.match_watchlist_jobs(
        _normalize_job(job, company_name, slug) for job in raw_jobs
    )


def scrape_all(company_boards):
    all_jobs = []
    _FAILED_SLUGS.clear()
    companies = [
        (name, cfg["slug"])
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "breezy"
    ]
    print(f"Scraping {len(companies)} Breezy boards...")
    for company_name, slug in companies:
        jobs = scrape_company(company_name, slug)
        print(f"  {company_name} ({slug}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs


def get_failures():
    return [
        {"ats": "breezy", "company": "", "slug": slug, "reason": reason}
        for slug, reason in _FAILED_SLUGS
    ]
