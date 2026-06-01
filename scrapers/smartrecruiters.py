"""Scraper for SmartRecruiters-hosted company job boards.

Public JSON API at https://api.smartrecruiters.com/v1/companies/<slug>/postings —
no auth, paginated (default 10/page, max 100). Used by NBCUniversal and a
handful of large enterprises.

A posting's location is nested at .location.{city,region,country,remote}; the
public-facing job ad lives at https://jobs.smartrecruiters.com/<slug>/<id>.
"""

import requests

from . import filters

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PUBLIC_URL = "https://jobs.smartrecruiters.com/{slug}/{posting_id}"

PAGE_SIZE = 100


def _fetch(slug):
    """Fetch all postings for a slug, paginating until exhausted."""
    all_postings = []
    offset = 0
    while True:
        try:
            resp = requests.get(
                API.format(slug=slug),
                params={"limit": PAGE_SIZE, "offset": offset},
                headers=HEADERS,
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"  [!] SmartRecruiters fetch failed for slug {slug!r}: {e}")
            return None
        if resp.status_code == 404:
            print(f"  [!] SmartRecruiters: slug {slug!r} not found (404)")
            return None
        if not resp.ok:
            print(f"  [!] SmartRecruiters: slug {slug!r} returned {resp.status_code}")
            return None
        try:
            data = resp.json()
        except ValueError:
            print(f"  [!] SmartRecruiters: slug {slug!r} returned non-JSON")
            return None
        page = data.get("content") or []
        all_postings.extend(page)
        total = data.get("totalFound", 0)
        offset += len(page)
        if not page or offset >= total:
            break
    return all_postings


def _custom_field_value(posting, field_label):
    for entry in (posting.get("customField") or []):
        if entry.get("fieldLabel") == field_label:
            return entry.get("valueLabel")
    return None


def _format_location(loc):
    """Build a display string from SmartRecruiters' location object."""
    if not loc:
        return ""
    parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    base = ", ".join(p for p in parts if p)
    if loc.get("remote"):
        return f"{base} (Remote)" if base else "Remote"
    return base


def _normalize_job(posting, company_name, slug):
    loc = posting.get("location") or {}
    location_str = _format_location(loc)
    is_remote = bool(loc.get("remote"))
    job_ad = posting.get("jobAd") or {}
    description = " ".join(
        p for p in [
            job_ad.get("sections", {}).get("jobDescription", "")
            if isinstance(job_ad.get("sections"), dict) else "",
            job_ad.get("sections", {}).get("qualifications", "")
            if isinstance(job_ad.get("sections"), dict) else "",
        ] if p
    )
    return {
        "job_id": f"smartrecruiters-{posting.get('id', '')}",
        "job_title": posting.get("name", ""),
        "employer_name": company_name,
        "job_city": loc.get("city", "") or "",
        "job_state": loc.get("region", "") or "",
        "job_country": loc.get("country", "") or "",
        "job_is_remote": is_remote,
        "job_apply_link": PUBLIC_URL.format(slug=slug, posting_id=posting.get("id", "")),
        "locations": [location_str] if location_str else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"smartrecruiters:{company_name}",
        "job_description": description,
    }


def scrape_company(company_name, slug, brand_filter=None, segment_filter=None):
    """Scrape one SmartRecruiters-hosted board.

    Mirrors the Greenhouse bu_filter pattern. If brand_filter or segment_filter
    is set, only postings whose customField "Brands"/"Business Segment"
    valueLabel matches are kept — lets us split a shared tenant (e.g., NBCU
    vs. Peacock) into separate digest entries.
    """
    raw = _fetch(slug)
    if not raw:
        return []
    matched = []
    for posting in raw:
        if brand_filter and _custom_field_value(posting, "Brands") != brand_filter:
            continue
        if segment_filter and _custom_field_value(posting, "Business Segment") != segment_filter:
            continue
        normalized = _normalize_job(posting, company_name, slug)
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
    sr_companies = [
        (name, cfg)
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "smartrecruiters"
    ]
    print(f"Scraping {len(sr_companies)} SmartRecruiters boards...")
    for company_name, cfg in sr_companies:
        jobs = scrape_company(
            company_name,
            cfg["slug"],
            brand_filter=cfg.get("brand_filter"),
            segment_filter=cfg.get("segment_filter"),
        )
        label = cfg["slug"]
        if cfg.get("brand_filter"):
            label += f"/brand={cfg['brand_filter']}"
        if cfg.get("segment_filter"):
            label += f"/segment={cfg['segment_filter']}"
        print(f"  {company_name} ({label}): {len(jobs)} matching")
        all_jobs.extend(jobs)
    return all_jobs
