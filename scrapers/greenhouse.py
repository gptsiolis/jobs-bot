"""Scraper for Greenhouse-hosted company job boards.

Most VC-backed and public-tech companies use Greenhouse. Public JSON API
at https://boards-api.greenhouse.io/v1/boards/<slug>/jobs — no auth, fast.

Each entry in config.COMPANY_BOARDS that uses "greenhouse" passes its
slug here. The bot fetches all jobs, then applies filters.passes_watchlist
to narrow on role + location + seniority.
"""

import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _fetch(slug):
    url = API.format(slug=slug)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [!] Greenhouse fetch failed for slug {slug!r}: {e}")
        return None
    if resp.status_code == 404:
        print(f"  [!] Greenhouse: slug {slug!r} not found (404)")
        return None
    if not resp.ok:
        print(f"  [!] Greenhouse: slug {slug!r} returned {resp.status_code}")
        return None
    try:
        return resp.json().get("jobs", [])
    except ValueError:
        print(f"  [!] Greenhouse: slug {slug!r} returned non-JSON")
        return None


def _normalize_job(job, company_name):
    location = (job.get("location") or {}).get("name", "") or ""
    return {
        "job_id": f"greenhouse-{job.get('id', '')}",
        "job_title": job.get("title", ""),
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": "remote" in location.lower(),
        "job_apply_link": job.get("absolute_url", ""),
        "locations": [location] if location else [],
        "work_mode": "remote" if "remote" in location.lower() else "",
        "source": f"greenhouse:{company_name}",
    }


def scrape_company(company_name, slug):
    """Scrape one Greenhouse-hosted board.

    Returns a list of normalized job dicts that pass the watchlist filter
    (role match + seniority + location + non-US).
    """
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
    """Scrape all Greenhouse-hosted companies in the mapping.

    Args:
        company_boards: Dict of {company_name: {"ats": "greenhouse", "slug": ...}}.
            Entries with ats != "greenhouse" are skipped.

    Returns:
        List of normalized job dicts across all companies.
    """
    all_jobs = []
    gh_companies = [
        (name, cfg["slug"])
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "greenhouse"
    ]
    print(f"Scraping {len(gh_companies)} Greenhouse boards...")
    for company_name, slug in gh_companies:
        jobs = scrape_company(company_name, slug)
        print(f"  {company_name} ({slug}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
