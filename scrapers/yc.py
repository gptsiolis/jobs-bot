"""Scraper for Y Combinator's Work at a Startup job board.

workatastartup.com — large aggregator of jobs at YC-backed companies.
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
        // Try common listing patterns on workatastartup
        const rows = document.querySelectorAll(
            '[class*="job"], [class*="listing"], [class*="role"], tr[data-href], a[href*="/jobs/"]'
        );
        const seen = new Set();
        rows.forEach(row => {
            const link = row.querySelector('a[href*="/jobs/"]') || row.closest('a[href*="/jobs/"]');
            const url = link ? link.href : '';
            if (!url || seen.has(url)) return;
            seen.add(url);

            // Try to find title and company text
            const texts = Array.from(row.querySelectorAll('*')).map(el => el.textContent.trim()).filter(t => t.length > 0 && t.length < 200);
            const titleEl = row.querySelector('[class*="title"], h3, h4, [class*="name"]');
            const companyEl = row.querySelector('[class*="company"], [class*="org"]');
            const locationEl = row.querySelector('[class*="location"], [class*="loc"]');

            jobs.push({
                title: titleEl ? titleEl.textContent.trim() : (texts[0] || ''),
                company: companyEl ? companyEl.textContent.trim() : '',
                location: locationEl ? locationEl.textContent.trim() : '',
                url: url,
            });
        });
        return jobs;
    }''')


def scrape(page, role_queries, skip_seniority):
    """Scrape Work at a Startup for matching jobs.

    Args:
        page: Playwright Page instance.
        role_queries: Search terms for sales / BD roles.
        skip_seniority: Title keywords to exclude.

    Returns:
        List of normalized job dicts.
    """
    try:
        page.goto("https://www.workatastartup.com/jobs", wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"  [!] Failed to load Work at a Startup: {e}")
        return []

    seen_urls = set()
    matched_jobs = []

    for query in role_queries:
        print(f"  Searching YC for '{query}'...")
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
                "job_id": f"yc-{filters.stable_job_hash(url)}",
                "job_title": job.get("title", ""),
                "employer_name": job.get("company", "Unknown"),
                "job_city": "",
                "job_state": "",
                "job_country": "",
                "job_is_remote": is_remote,
                "job_apply_link": url,
                "locations": [location] if location else [],
                "work_mode": "remote" if is_remote else "on_site",
                "source": "Y Combinator",
                "job_description": "",
            }
            filters.add_fit_metadata(normalized)
            matched_jobs.append(normalized)

    return matched_jobs
