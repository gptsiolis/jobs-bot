"""Scraper for Workday-hosted company job boards.

Most enterprise companies (eBay, Etsy, Disney, NBCUniversal, etc.) use
Workday. The API is a POST endpoint at:

    https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

It accepts a JSON body with appliedFacets/limit/offset/searchText and
returns up to 20 jobs by default (we ask for 100). Anti-bot is moderate —
sometimes returns 403 from Cloudflare. We catch + log + continue so one
blocked company doesn't tank the whole watchlist run.
"""

import requests

from config import ROLE_QUERIES
from . import filters

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
API = "https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

# Workday caps `limit` at 20. We loop over ROLE_QUERIES and let Workday's
# searchText narrow the feed instead of pulling everything and filtering
# client-side — for tenants like Disney (600+ jobs) the role-search
# approach is dramatically cheaper.
PAGE_SIZE = 20
MAX_PAGES_PER_QUERY = 5  # = 100 jobs per role query per company


def _fetch_paged(tenant, wd, site, search_text):
    url = API.format(tenant=tenant, wd=wd, site=site)
    all_postings = []
    for page in range(MAX_PAGES_PER_QUERY):
        payload = {
            "appliedFacets": {},
            "limit": PAGE_SIZE,
            "offset": page * PAGE_SIZE,
            "searchText": search_text,
        }
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"  [!] Workday fetch failed for {tenant}/{site} q={search_text!r}: {e}")
            return None
        if resp.status_code in (403, 404):
            print(f"  [!] Workday: {tenant}/{site} returned {resp.status_code}")
            return None
        if not resp.ok:
            print(f"  [!] Workday: {tenant}/{site} q={search_text!r} returned {resp.status_code}")
            return None
        try:
            data = resp.json()
        except ValueError:
            print(f"  [!] Workday: {tenant}/{site} returned non-JSON")
            return None
        page_jobs = data.get("jobPostings") or []
        all_postings.extend(page_jobs)
        if len(page_jobs) < PAGE_SIZE:
            break
    return all_postings


def _normalize_job(job, company_name, tenant, wd, site):
    title = job.get("title", "")
    location = job.get("locationsText", "") or ""
    is_remote = "remote" in location.lower()
    external_path = job.get("externalPath", "") or ""
    apply_url = (
        f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{external_path}"
        if external_path else ""
    )
    return {
        "job_id": f"workday-{tenant}-{job.get('bulletFields', [''])[0] or external_path}",
        "job_title": title,
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "locations": [location] if location else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"workday:{company_name}",
    }


def scrape_company(company_name, cfg):
    seen_paths = set()
    matched = []
    for query in ROLE_QUERIES:
        raw = _fetch_paged(cfg["tenant"], cfg["wd"], cfg["site"], query)
        if not raw:
            continue
        for job in raw:
            path = job.get("externalPath", "")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            normalized = _normalize_job(
                job, company_name, cfg["tenant"], cfg["wd"], cfg["site"],
            )
            location_blob = " ".join(normalized["locations"])
            if not filters.passes_watchlist(
                normalized["job_title"], location_blob, normalized["employer_name"]
            ):
                continue
            matched.append(normalized)
    return matched


def scrape_all(company_boards):
    all_jobs = []
    wd_companies = [
        (name, cfg)
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "workday"
    ]
    print(f"Scraping {len(wd_companies)} Workday boards...")
    for company_name, cfg in wd_companies:
        jobs = scrape_company(company_name, cfg)
        print(f"  {company_name} ({cfg['tenant']}/{cfg['site']}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
