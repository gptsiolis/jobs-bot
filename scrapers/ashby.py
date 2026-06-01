"""Scraper for Ashby-hosted company job boards.

Public JSON API at https://api.ashbyhq.com/posting-api/job-board/<slug>
"""

import requests
import time

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
TIMEOUTS = (20, 45, 75)
RETRY_PAUSE_SECONDS = 3
BOARD_PAUSE_SECONDS = 1

_FAILED_SLUGS = []


def _fetch(slug):
    last_error = None
    for attempt, timeout in enumerate(TIMEOUTS, start=1):
        try:
            resp = requests.get(API.format(slug=slug), headers=HEADERS, timeout=timeout)
        except requests.RequestException as e:
            last_error = str(e)
            if attempt < len(TIMEOUTS):
                print(
                    f"  [!] Ashby fetch retry {attempt}/{len(TIMEOUTS)} for "
                    f"slug {slug!r}: {e}"
                )
                time.sleep(RETRY_PAUSE_SECONDS * attempt)
                continue
            print(f"  [!] Ashby fetch failed for slug {slug!r}: {e}")
            _FAILED_SLUGS.append((slug, last_error))
            return None

        if resp.status_code == 404:
            print(f"  [!] Ashby: slug {slug!r} not found (404)")
            return None
        if not resp.ok:
            last_error = f"returned {resp.status_code}"
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < len(TIMEOUTS):
                print(
                    f"  [!] Ashby fetch retry {attempt}/{len(TIMEOUTS)} for "
                    f"slug {slug!r}: {last_error}"
                )
                time.sleep(RETRY_PAUSE_SECONDS * attempt)
                continue
            print(f"  [!] Ashby: slug {slug!r} {last_error}")
            _FAILED_SLUGS.append((slug, last_error))
            return None
        try:
            data = resp.json()
        except ValueError:
            last_error = "returned non-JSON"
            print(f"  [!] Ashby: slug {slug!r} {last_error}")
            _FAILED_SLUGS.append((slug, last_error))
            return None
        return data.get("jobs") or data.get("jobPostings") or []

    _FAILED_SLUGS.append((slug, last_error or "unknown error"))
    return None


def _job_description(job):
    parts = [
        job.get("description", ""),
        job.get("descriptionHtml", ""),
        job.get("descriptionPlain", ""),
        job.get("jobDescription", ""),
    ]
    return " ".join(p for p in parts if p)


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
    _FAILED_SLUGS.clear()
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
        time.sleep(BOARD_PAUSE_SECONDS)
    if _FAILED_SLUGS:
        failed = ", ".join(f"{slug} ({reason})" for slug, reason in _FAILED_SLUGS)
        print(f"  [!] Ashby skipped after retries: {failed}")
    return all_jobs


def get_failures():
    return [
        {"ats": "ashby", "company": "", "slug": slug, "reason": reason}
        for slug, reason in _FAILED_SLUGS
    ]
