"""Scraper for Dayforce-hosted company job boards.

Dayforce exposes an anonymous JobFeeds endpoint for public career-site
postings:

    https://www.dayforcehcm.com/api/<company>/V1/JobFeeds

The response is JSON when requested with Accept: application/json.
"""

import requests

from . import filters

HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
API = "https://www.dayforcehcm.com/api/{company}/V1/JobFeeds"


def _fetch(company, board_code=None):
    params = {"includeActivePostingOnly": "true"}
    if board_code:
        params["internalJobBoardCode"] = board_code
    try:
        resp = requests.get(
            API.format(company=company),
            params=params,
            headers=HEADERS,
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"  [!] Dayforce fetch failed for company {company!r}: {e}")
        return None
    if resp.status_code == 404:
        print(f"  [!] Dayforce: company {company!r} not found (404)")
        return None
    if not resp.ok:
        print(f"  [!] Dayforce: company {company!r} returned {resp.status_code}")
        return None
    try:
        data = resp.json()
    except ValueError:
        print(f"  [!] Dayforce: company {company!r} returned non-JSON")
        return None
    if isinstance(data, list):
        return data
    return data.get("Jobs") or data.get("jobs") or []


def _format_location(job):
    parts = [job.get("City"), job.get("State"), job.get("Country")]
    return ", ".join(str(part).strip() for part in parts if part)


def _is_remote(job):
    if job.get("IsVirtualLocation") is True:
        return True
    location_blob = _format_location(job).lower()
    description = (job.get("Description") or "").lower()
    telecommute = job.get("TelecommutePercentage")
    try:
        if telecommute is not None and float(telecommute) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return "remote" in location_blob or "virtual" in location_blob or "remote" in description


def _normalize_job(job, company_name, dayforce_company):
    location = _format_location(job)
    is_remote = _is_remote(job)
    reference = job.get("ReferenceNumber") or job.get("ParentRequisitionCode") or job.get("JobId")
    apply_url = job.get("ApplyUrl") or job.get("JobDetailsUrl") or ""
    return {
        "job_id": f"dayforce-{dayforce_company}-{reference or apply_url}",
        "job_title": job.get("Title", "") or "",
        "employer_name": company_name,
        "job_city": job.get("City", "") or "",
        "job_state": job.get("State", "") or "",
        "job_country": job.get("Country", "") or "",
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "locations": [location] if location else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"dayforce:{company_name}",
        "job_description": job.get("Description", "") or "",
    }


def scrape_company(company_name, company, board_code=None):
    raw = _fetch(company, board_code=board_code)
    if not raw:
        return []
    matched = []
    seen_ids = set()
    for job in raw:
        normalized = _normalize_job(job, company_name, company)
        if normalized["job_id"] in seen_ids:
            continue
        seen_ids.add(normalized["job_id"])
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
    companies = [
        (name, cfg)
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "dayforce"
    ]
    print(f"Scraping {len(companies)} Dayforce boards...")
    for company_name, cfg in companies:
        jobs = scrape_company(
            company_name,
            cfg["company"],
            board_code=cfg.get("board_code"),
        )
        label = cfg["company"] + (f"/{cfg['board_code']}" if cfg.get("board_code") else "")
        print(f"  {company_name} ({label}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs

