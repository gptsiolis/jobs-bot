"""Scraper for Wellfound (formerly AngelList Talent) job board.

wellfound.com — large aggregator of startup jobs.
Client-side rendered, requires Playwright.
"""

from . import filters


def _search_and_extract(page, query):
    """Type a search query and extract resulting job listings."""
    search = page.query_selector('input[type="text"], input[placeholder*="Search"], input[name*="query"]')
    if not search:
        return []

    search.fill("")
    search.fill(query)
    page.wait_for_timeout(2000)

    return page.evaluate('''() => {
        const jobs = [];
        const seen = new Set();
        // Wellfound uses startup-list-item cards or similar job card patterns
        const cards = document.querySelectorAll(
            '[class*="job"], [class*="listing"], [class*="styles_component"], a[href*="/jobs/"]'
        );
        cards.forEach(card => {
            const link = card.querySelector('a[href*="/jobs/"]') || card.closest('a[href*="/jobs/"]');
            const url = link ? link.href : '';
            if (!url || seen.has(url)) return;
            seen.add(url);

            const titleEl = card.querySelector('[class*="title"], h3, h4');
            const companyEl = card.querySelector('[class*="company"], [class*="org"], [class*="startup"]');
            const locationEl = card.querySelector('[class*="location"], [class*="loc"]');

            jobs.push({
                title: titleEl ? titleEl.textContent.trim() : '',
                company: companyEl ? companyEl.textContent.trim() : '',
                location: locationEl ? locationEl.textContent.trim() : '',
                url: url,
            });
        });
        return jobs;
    }''')


def scrape(page, role_queries, skip_seniority):
    """Scrape Wellfound for matching jobs.

    Args:
        page: Playwright Page instance.
        role_queries: Search terms for sales / BD roles.
        skip_seniority: Title keywords to exclude.

    Returns:
        List of normalized job dicts.
    """
    try:
        page.goto("https://wellfound.com/jobs", wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"  [!] Failed to load Wellfound: {e}")
        return []

    seen_urls = set()
    matched_jobs = []

    for query in role_queries:
        print(f"  Searching Wellfound for '{query}'...")
        raw_jobs = _search_and_extract(page, query)

        for job in raw_jobs:
            url = job.get("url", "")
            if url in seen_urls or not url:
                continue
            seen_urls.add(url)

            location = job.get("location", "")
            if not filters.passes_discovery(
                job.get("title", ""), location, job.get("company", ""),
            ):
                continue

            is_remote = "remote" in location.lower()

            normalized = {
                "job_id": f"wellfound-{filters.stable_job_hash(url)}",
                "job_title": job.get("title", ""),
                "employer_name": job.get("company", "Unknown"),
                "job_city": "",
                "job_state": "",
                "job_country": "",
                "job_is_remote": is_remote,
                "job_apply_link": url,
                "locations": [location] if location else [],
                "work_mode": "remote" if is_remote else "on_site",
                "source": "Wellfound",
                "job_description": "",
            }
            filters.add_fit_metadata(normalized)
            matched_jobs.append(normalized)

    return matched_jobs
