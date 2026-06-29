"""Browser-based scraper for Phenom People career sites.

Phenom sites (e.g. careers.circle.com, careers.ebayinc.com) are JS single-page
apps whose job API refuses direct calls ("Tenant not identified") — the tenant
is only resolved when the site's own code runs. So we drive a headless browser
to the search-results page, let the page issue its own authenticated API calls,
and capture the JSON responses off the network. The browser is reused across
all Phenom companies in one run.

Registry entry shape:
    {"type": "phenom", "host": "https://careers.circle.com",
     "search_path": "/us/en/search-results"}

The DOM-independent JSON parsing/normalization below is pure and unit-tested;
only _scrape_with_page touches Playwright.
"""

from . import filters

DEFAULT_SEARCH_PATH = "/us/en/search-results"
# Substrings that mark a Phenom jobs API response we want to capture.
_JOBS_URL_HINTS = ("/jobs", "careersite", "refinesearch", "/api/")
# Bounded scrolling to trigger Phenom's lazy pagination without runaway loops.
MAX_SCROLLS = 12
SCROLL_PAUSE_MS = 1200

_FAILURES = []


def _find_jobs_list(payload):
    """Recursively locate the first list of job dicts in a Phenom JSON body.

    Phenom wraps jobs under varying keys (data.jobs, refineSearch.data.jobs,
    eagerLoadRefineSearch...), so rather than hard-code a path we search for a
    list whose items look like jobs (have a title-ish field).
    """
    title_keys = ("title", "jobTitle", "name")
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and any(
            k in payload[0] for k in title_keys
        ):
            return payload
        for item in payload:
            found = _find_jobs_list(item)
            if found:
                return found
        return None
    if isinstance(payload, dict):
        jobs = payload.get("jobs")
        if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
            return jobs
        for value in payload.values():
            found = _find_jobs_list(value)
            if found:
                return found
    return None


def _first(raw, *keys):
    for key in keys:
        value = raw.get(key)
        if value:
            return value
    return ""


def _location_string(raw):
    explicit = _first(raw, "cityState", "location", "locationName", "primaryLocation")
    if explicit and isinstance(explicit, str):
        return explicit
    locations = raw.get("locations")
    if isinstance(locations, list) and locations:
        parts = []
        for loc in locations:
            if isinstance(loc, str):
                parts.append(loc)
            elif isinstance(loc, dict):
                parts.append(
                    ", ".join(
                        str(p).strip()
                        for p in (loc.get("city"), loc.get("state"), loc.get("country"))
                        if p
                    )
                )
        return "; ".join(p for p in parts if p)
    parts = [raw.get("city"), raw.get("state"), raw.get("country")]
    return ", ".join(str(p).strip() for p in parts if p)


def _normalize_job(raw, company_name, host):
    location = _location_string(raw)
    is_remote = "remote" in location.lower() or bool(raw.get("remote"))
    job_id = _first(raw, "jobId", "jobSeqNo", "id", "jobPostId", "reqId")
    apply_url = _first(raw, "applyUrl", "jobUrl", "url", "canonicalUrl", "jobDetailUrl")
    if apply_url and apply_url.startswith("/"):
        apply_url = host.rstrip("/") + apply_url
    description = _first(
        raw, "descriptionTeaser", "description", "jobDescription", "summary"
    )
    return {
        "job_id": f"phenom-{job_id}",
        "job_title": _first(raw, "title", "jobTitle", "name"),
        "employer_name": company_name,
        "job_city": "",
        "job_state": "",
        "job_country": "",
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "locations": [location] if location else [],
        "work_mode": "remote" if is_remote else "",
        "source": f"phenom:{company_name}",
        "job_description": description,
    }


def _dedupe(raw_jobs):
    seen = set()
    for raw in raw_jobs:
        key = (
            raw.get("jobId")
            or raw.get("jobSeqNo")
            or raw.get("id")
            or raw.get("applyUrl")
            or raw.get("title")
        )
        if key in seen:
            continue
        seen.add(key)
        yield raw


def _match(raw_jobs, company_name, host):
    """Pure pipeline: dedupe captured raw jobs -> normalize -> filter."""
    return filters.match_watchlist_jobs(
        _normalize_job(raw, company_name, host) for raw in _dedupe(raw_jobs)
    )


def _looks_like_jobs_response(url):
    low = url.lower()
    return any(hint in low for hint in _JOBS_URL_HINTS)


def _scrape_with_page(page, company_name, host, search_path):
    """Drive one Phenom site, capturing jobs JSON off the network."""
    captured = []

    def on_response(response):
        try:
            if not _looks_like_jobs_response(response.url):
                return
            ctype = (response.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            jobs = _find_jobs_list(response.json())
            if jobs:
                captured.extend(jobs)
        except Exception:
            return  # non-JSON / failed body / unrelated XHR — ignore

    page.on("response", on_response)
    url = host.rstrip("/") + (search_path or DEFAULT_SEARCH_PATH)
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception as e:
        print(f"  [!] Phenom: failed to load {company_name} ({url}): {e}")
        _FAILURES.append((company_name, str(e)))
        return []

    # Phenom lazy-loads more results as you scroll; keep going until the
    # captured count stops growing or we hit the scroll cap.
    last_count = -1
    for _ in range(MAX_SCROLLS):
        if len(captured) == last_count:
            break
        last_count = len(captured)
        try:
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(SCROLL_PAUSE_MS)
        except Exception:
            break

    matched = _match(captured, company_name, host)
    print(f"  {company_name}: captured {len(captured)} raw, {len(matched)} matching")
    return matched


def scrape_company(company_name, cfg):
    """Self-contained single-company scrape (used by `jobs.py test`)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            return _scrape_with_page(
                page, company_name, cfg["host"], cfg.get("search_path")
            )
        finally:
            page.close()
            browser.close()


def scrape_all(company_boards):
    """Scrape every Phenom company, reusing one browser. No-op if none."""
    _FAILURES.clear()
    companies = [
        (name, cfg)
        for name, cfg in company_boards.items()
        if cfg.get("ats") == "phenom"
    ]
    if not companies:
        return []

    from playwright.sync_api import sync_playwright

    print(f"Scraping {len(companies)} Phenom boards (browser)...")
    all_jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for company_name, cfg in companies:
            try:
                all_jobs.extend(
                    _scrape_with_page(
                        page, company_name, cfg["host"], cfg.get("search_path")
                    )
                )
            except Exception as e:
                print(f"  [!] Phenom: {company_name} errored: {e}")
                _FAILURES.append((company_name, str(e)))
        page.close()
        browser.close()
    return all_jobs


def get_failures():
    return [
        {"ats": "phenom", "company": company, "slug": "", "reason": reason}
        for company, reason in _FAILURES
    ]
