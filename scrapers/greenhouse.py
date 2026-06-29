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
API_WITH_META = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


# Tiny cache so multiple companies pointing at the same slug (e.g., Block,
# Cash App, Square all on "block") only hit the API once per run.
_FETCH_CACHE = {}


def _fetch(slug, need_metadata=False):
    cache_key = slug
    if cache_key in _FETCH_CACHE:
        return _FETCH_CACHE[cache_key]
    url = API_WITH_META.format(slug=slug)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"  [!] Greenhouse fetch failed for slug {slug!r}: {e}")
        _FETCH_CACHE[cache_key] = None
        return None
    if resp.status_code == 404:
        print(f"  [!] Greenhouse: slug {slug!r} not found (404)")
        _FETCH_CACHE[cache_key] = None
        return None
    if not resp.ok:
        print(f"  [!] Greenhouse: slug {slug!r} returned {resp.status_code}")
        _FETCH_CACHE[cache_key] = None
        return None
    try:
        jobs = resp.json().get("jobs", [])
    except ValueError:
        print(f"  [!] Greenhouse: slug {slug!r} returned non-JSON")
        _FETCH_CACHE[cache_key] = None
        return None
    _FETCH_CACHE[cache_key] = jobs
    return jobs


def _job_business_unit(job):
    for entry in (job.get("metadata") or []):
        if entry.get("name") == "Business Unit":
            return entry.get("value")
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
        "job_description": job.get("content", "") or "",
    }


def scrape_company(company_name, slug, bu_filter=None):
    """Scrape one Greenhouse-hosted board.

    If bu_filter is set, only jobs whose Business Unit metadata equals it
    are kept — used by Block (Cash App / Square / Centralized Block share
    a slug but should appear as separate companies in the digest).
    """
    raw_jobs = _fetch(slug, need_metadata=bool(bu_filter))
    if not raw_jobs:
        return []
    return filters.match_watchlist_jobs(
        _normalize_job(job, company_name)
        for job in raw_jobs
        if not bu_filter or _job_business_unit(job) == bu_filter
    )


def scrape_all(company_boards):
    """Scrape all Greenhouse-hosted companies in the mapping.

    Args:
        company_boards: Dict of {company_name: {"ats": "greenhouse", "slug": ...}}.
            Optional "bu_filter" narrows to one Business Unit on shared boards.

    Returns:
        List of normalized job dicts across all companies.
    """
    all_jobs = []
    gh_companies = [
        (name, cfg)
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "greenhouse"
    ]
    print(f"Scraping {len(gh_companies)} Greenhouse boards...")
    for company_name, cfg in gh_companies:
        jobs = scrape_company(company_name, cfg["slug"], cfg.get("bu_filter"))
        label = f"{cfg['slug']}" + (f"/{cfg['bu_filter']}" if cfg.get("bu_filter") else "")
        print(f"  {company_name} ({label}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
