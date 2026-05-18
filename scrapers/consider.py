"""Scraper for Consider-powered VC portfolio job boards.

Used by: Sequoia, a16z, Bessemer, Greylock, First Round Capital,
         Lightspeed, Kleiner Perkins, Union Square Ventures.

Consider boards are client-side rendered — requires Playwright to
execute JavaScript and extract job data from the DOM.
"""

from . import filters


def _extract_location(badges):
    """Pull location string from badge list, skipping salary/date/dept badges."""
    for badge in badges:
        lower = badge.lower()
        # Skip non-location badges
        if any(skip in lower for skip in [
            "salary", "posted", "employee", "usd", "eur", "gbp",
        ]):
            continue
        # Likely a location if it contains geographic terms
        if any(geo in lower for geo in [
            "remote", "united states", "usa", "new york", "san francisco",
            "miami", "florida", "california", "texas", "chicago",
            "boston", "seattle", "denver", "austin", "los angeles",
            "atlanta", ",",  # comma usually indicates "City, State"
        ]):
            return badge
    return ""


def _search_and_extract(page, query):
    """Type a search query and extract resulting job cards."""
    search = page.query_selector('input[placeholder="Search by title"]')
    if not search:
        return []

    search.fill("")
    search.fill(query)
    page.wait_for_timeout(1500)

    return page.evaluate('''() => {
        const cards = document.querySelectorAll('.job-list-job');
        return Array.from(cards).map(card => {
            const companyEl = card.querySelector('.job-list-job-company-link');
            const titleEl = card.querySelector('.job-list-job-title a');
            const badges = card.querySelectorAll('.job-list-badge');
            const badgeTexts = Array.from(badges).map(b => b.textContent.trim());
            return {
                company: companyEl ? companyEl.textContent.trim() : '',
                title: titleEl ? titleEl.textContent.trim() : '',
                url: titleEl ? titleEl.href : '',
                badges: badgeTexts,
            };
        });
    }''')


def scrape_board(page, board_url, vc_name, role_queries, skip_seniority):
    """Scrape a single Consider board using an existing Playwright page.

    Returns:
        List of normalized job dicts.
    """
    try:
        page.goto(f"{board_url}/jobs", wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"  [!] Failed to load {vc_name}: {e}")
        return []

    seen_ids = set()
    matched_jobs = []

    for query in role_queries:
        raw_jobs = _search_and_extract(page, query)

        for job in raw_jobs:
            url = job.get("url", "")
            if url in seen_ids or not url:
                continue
            seen_ids.add(url)

            location = _extract_location(job.get("badges", []))
            if not filters.passes_discovery(
                job.get("title", ""), location, job.get("company", ""),
            ):
                continue
            is_remote = "remote" in location.lower()

            matched_jobs.append({
                "job_id": f"consider-{filters.stable_job_hash(url)}",
                "job_title": job.get("title", ""),
                "employer_name": job.get("company", "Unknown"),
                "job_city": "",
                "job_state": "",
                "job_country": "",
                "job_is_remote": is_remote,
                "job_apply_link": url,
                "locations": [location] if location else [],
                "work_mode": "remote" if is_remote else "on_site",
                "source": f"consider:{vc_name}",
            })

    return matched_jobs


def scrape_all(browser, boards, role_queries, skip_seniority):
    """Scrape all configured Consider boards using a shared Playwright browser.

    Args:
        browser: Playwright Browser instance.
        boards: Dict of {vc_name: board_url}.
        role_queries: Search terms for sales / BD roles.
        skip_seniority: Title keywords to exclude.

    Returns:
        List of all matched jobs across all boards.
    """
    page = browser.new_page()
    all_jobs = []

    for vc_name, board_url in boards.items():
        print(f"Scraping {vc_name} ({board_url})...")
        jobs = scrape_board(page, board_url, vc_name, role_queries, skip_seniority)
        print(f"  Found {len(jobs)} matching jobs")
        all_jobs.extend(jobs)

    page.close()
    return all_jobs
