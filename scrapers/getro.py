"""Scraper for Getro-powered VC portfolio job boards.

Used by: General Catalyst, Accel, Khosla Ventures, Thrive Capital,
         Craft Ventures, Insight Partners.

Getro boards are Next.js apps that embed job data in __NEXT_DATA__ JSON.
No auth required — just HTTP GET + JSON parsing.
"""

import re
import json
import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _extract_next_data(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def _parse_jobs(data):
    """Extract job list from Getro __NEXT_DATA__ structure."""
    try:
        return data["props"]["pageProps"]["initialState"]["jobs"]["found"]
    except (KeyError, TypeError):
        return []


def _normalize_job(job, vc_name):
    """Convert a Getro job dict into our standard format."""
    org = job.get("organization") or {}
    locations = job.get("locations") or job.get("searchableLocations") or []
    work_mode = (job.get("workMode") or "").lower()
    is_remote = work_mode == "remote"

    return {
        "job_id": f"getro-{job.get('id', '')}",
        "job_title": job.get("title", ""),
        "employer_name": org.get("name", "Unknown"),
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": job.get("url", ""),
        "locations": locations,
        "work_mode": work_mode,
        "source": f"getro:{vc_name}",
        "job_description": job.get("description", "") or "",
    }


def scrape_board(board_url, vc_name, role_queries, skip_seniority):
    """Scrape a single Getro board for matching jobs.

    Args:
        board_url: Base URL like "https://jobs.generalcatalyst.com"
        vc_name: Display name like "General Catalyst"
        role_queries: List of search terms like ["SDR", "BDR", "account executive"]
        skip_seniority: List of title keywords to exclude (e.g. ["senior", "director"])

    Returns:
        List of normalized job dicts.
    """
    seen_ids = set()
    matched_jobs = []

    for query in role_queries:
        url = f"{board_url}/jobs?q={query}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [!] Failed to fetch {vc_name} for '{query}': {e}")
            continue

        data = _extract_next_data(resp.text)
        if not data:
            print(f"  [!] No __NEXT_DATA__ found on {vc_name} for '{query}'")
            continue

        raw_jobs = _parse_jobs(data)

        for job in raw_jobs:
            job_id = job.get("id")
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            normalized = _normalize_job(job, vc_name)
            location_blob = " ".join(normalized["locations"])
            description = normalized.get("job_description", "")
            if not filters.passes_discovery(
                normalized["job_title"], location_blob, normalized["employer_name"],
                description,
            ):
                continue

            filters.add_fit_metadata(normalized, description)
            matched_jobs.append(normalized)

    return matched_jobs


def scrape_all(boards, role_queries, skip_seniority):
    """Scrape all configured Getro boards.

    Args:
        boards: Dict of {vc_name: board_url}
        role_queries: Search terms for sales / BD roles
        skip_seniority: Title keywords to exclude

    Returns:
        List of all matched jobs across all boards.
    """
    all_jobs = []
    for vc_name, board_url in boards.items():
        print(f"Scraping {vc_name} ({board_url})...")
        jobs = scrape_board(board_url, vc_name, role_queries, skip_seniority)
        print(f"  Found {len(jobs)} matching jobs")
        all_jobs.extend(jobs)
    return all_jobs
