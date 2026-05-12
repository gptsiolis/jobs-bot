import datetime
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from playwright.sync_api import sync_playwright

from config import (
    SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL,
    GETRO_BOARDS, CONSIDER_BOARDS, ROLE_QUERIES, SKIP_SENIORITY,
    COMPANY_BOARDS, LOCATION_ALLOW,
)
from scrapers import getro, consider, yc, wellfound, greenhouse, lever, ashby, workday

SEEN_JOBS_FILE = "seen_jobs.json"
SEEN_TTL_DAYS = 60

MODES = ("discovery", "watchlist", "all", "test")


def _today_iso():
    return datetime.date.today().isoformat()


def load_seen_jobs():
    """Return seen_jobs as {job_id: ISO-date}. Migrates legacy flat list."""
    if not os.path.exists(SEEN_JOBS_FILE):
        return {}
    with open(SEEN_JOBS_FILE, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        # Legacy format: flat list of IDs. Treat all as seen today so they
        # don't get re-emailed on the next run; they'll age out in 60 days.
        today = _today_iso()
        return {jid: today for jid in data}
    return data


def save_seen_jobs(seen):
    """Drop entries older than SEEN_TTL_DAYS, then persist."""
    cutoff = datetime.date.today() - datetime.timedelta(days=SEEN_TTL_DAYS)
    fresh = {}
    for jid, iso in seen.items():
        try:
            seen_date = datetime.date.fromisoformat(iso)
        except (TypeError, ValueError):
            seen_date = datetime.date.today()  # malformed entry → keep but reset
        if seen_date >= cutoff:
            fresh[jid] = iso
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(fresh, f)


def deduplicate(jobs, seen_ids):
    """Remove duplicates (cross-board + already-seen). Stamps new IDs with today."""
    today = _today_iso()
    unique = []
    seen_titles = set()
    for job in jobs:
        jid = job["job_id"]
        if jid in seen_ids:
            continue
        key = (job["job_title"].lower().strip(), job["employer_name"].lower().strip())
        if key in seen_titles:
            continue
        seen_ids[jid] = today
        seen_titles.add(key)
        unique.append(job)
    return unique


def _job_location_string(job):
    """Build the display-ready location string for a job."""
    locations = job.get("locations", [])
    city = job.get("job_city", "")
    state = job.get("job_state", "")
    if locations:
        location = ", ".join(locations)
    elif city or state:
        location = ", ".join(p for p in [city, state] if p)
    else:
        location = "Unknown"
    if job.get("job_is_remote") or job.get("work_mode") == "remote":
        location = f"{location} (Remote)" if location != "Unknown" else "Remote"
    return location


def _categorize_metro(location_blob):
    blob = (location_blob or "").lower()
    if "remote" in blob:
        return "Remote"
    for metro, tokens in LOCATION_ALLOW.items():
        if any(tok in blob for tok in tokens):
            return metro
    return "Other"


def _format_source_label(source):
    if source.startswith("getro:"):
        return source.replace("getro:", "") + " Portfolio"
    if source.startswith("consider:"):
        return source.replace("consider:", "") + " Portfolio"
    if source.startswith("greenhouse:"):
        return source.replace("greenhouse:", "")
    if source.startswith("lever:"):
        return source.replace("lever:", "")
    if source.startswith("ashby:"):
        return source.replace("ashby:", "")
    if source.startswith("workday:"):
        return source.replace("workday:", "")
    if source == "Y Combinator":
        return "Y Combinator (Work at a Startup)"
    if source == "Wellfound":
        return "Wellfound (AngelList)"
    return source


def send_email(jobs, heading, subject_prefix):
    if not jobs:
        print(f"\n[{heading}] No new jobs found.")
        return

    # Metro breakdown for the email header
    metro_counts = {}
    for job in jobs:
        loc = _job_location_string(job)
        metro_counts[_categorize_metro(loc)] = metro_counts.get(_categorize_metro(loc), 0) + 1

    by_source = {}
    for job in jobs:
        source = job.get("source", "other")
        by_source.setdefault(source, []).append(job)

    body = f"<h2>{heading}</h2>"
    body += f"<p><b>{len(jobs)} new listings</b> from {len(by_source)} sources</p>"
    breakdown = " &middot; ".join(
        f"{metro}: {count}"
        for metro, count in sorted(metro_counts.items(), key=lambda x: (-x[1], x[0]))
    )
    body += f"<p style='color:#666'>{breakdown}</p><hr>"

    # Sources sorted by job count desc, ties alphabetical
    sources_sorted = sorted(
        by_source.items(),
        key=lambda x: (-len(x[1]), x[0]),
    )
    for source, source_jobs in sources_sorted:
        source_label = _format_source_label(source)
        body += f"<h3>{source_label} ({len(source_jobs)})</h3>"
        # Sort jobs within a source alphabetically by title
        for job in sorted(source_jobs, key=lambda j: j.get("job_title", "").lower()):
            title = job.get("job_title", "N/A")
            company = job.get("employer_name", "N/A")
            location = _job_location_string(job)
            link = job.get("job_apply_link", "#")
            body += f"<p><b>{title}</b> &mdash; {company} &mdash; {location}"
            if link and link != "#":
                body += f"<br><a href='{link}'>Apply</a>"
            body += "</p>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix} — {len(jobs)} new listings"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"\n[{heading}] Email sent with {len(jobs)} jobs.")


def run_discovery(seen):
    """Mode A — broad sweep across VC portfolio boards + YC + Wellfound.

    Filters: role queries (search-side), seniority + location + non-US (our
    side). No company allowlist — the point of discovery is to find new
    companies.
    """
    print("="*50)
    print("DISCOVERY MODE — scraping aggregators")
    print("="*50)
    all_jobs = []

    # 1. Getro boards (no browser)
    getro_jobs = getro.scrape_all(GETRO_BOARDS, ROLE_QUERIES, SKIP_SENIORITY)
    all_jobs.extend(getro_jobs)

    # 2. Browser-based boards
    print("\nLaunching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        consider_jobs = consider.scrape_all(
            browser, CONSIDER_BOARDS, ROLE_QUERIES, SKIP_SENIORITY,
        )
        all_jobs.extend(consider_jobs)

        page = browser.new_page()

        print("\nScraping Y Combinator (workatastartup.com)...")
        yc_jobs = yc.scrape(page, ROLE_QUERIES, SKIP_SENIORITY)
        print(f"  Found {len(yc_jobs)} matching jobs")
        all_jobs.extend(yc_jobs)

        print("Scraping Wellfound (wellfound.com)...")
        wf_jobs = wellfound.scrape(page, ROLE_QUERIES, SKIP_SENIORITY)
        print(f"  Found {len(wf_jobs)} matching jobs")
        all_jobs.extend(wf_jobs)

        page.close()
        browser.close()
    print("Browser closed.\n")

    new_jobs = deduplicate(all_jobs, seen)
    print(f"Discovery total new jobs after dedup: {len(new_jobs)}")
    send_email(
        new_jobs,
        heading="Daily VC Discovery",
        subject_prefix="Daily VC Discovery",
    )


def run_watchlist(seen):
    """Mode B — per-company ATS scrapers for the curated allowlist.

    Hits each allowlisted company's own Greenhouse/Lever/Ashby board directly
    and applies filters.passes_watchlist for role + location + seniority.
    """
    print("="*50)
    print("WATCHLIST MODE — per-company ATS scrapers")
    print("="*50)
    all_jobs = []
    all_jobs.extend(greenhouse.scrape_all(COMPANY_BOARDS))
    all_jobs.extend(lever.scrape_all(COMPANY_BOARDS))
    all_jobs.extend(ashby.scrape_all(COMPANY_BOARDS))
    all_jobs.extend(workday.scrape_all(COMPANY_BOARDS))

    new_jobs = deduplicate(all_jobs, seen)
    print(f"Watchlist total new jobs after dedup: {len(new_jobs)}")
    send_email(
        new_jobs,
        heading="Daily Watchlist",
        subject_prefix="Daily Watchlist",
    )


_ATS_TO_MODULE = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workday": workday,
}


def run_test(company_query):
    """Dry-run a single company. Prints matches; sends no email, updates no state."""
    query_norm = company_query.lower().strip()
    matched_name = None
    for name in COMPANY_BOARDS:
        if name.lower() == query_norm or query_norm in name.lower():
            matched_name = name
            break

    if not matched_name:
        print(f"No company in COMPANY_BOARDS matches {company_query!r}.")
        print(f"Available companies:")
        for name in sorted(COMPANY_BOARDS):
            print(f"  - {name}")
        sys.exit(1)

    cfg = COMPANY_BOARDS[matched_name]
    ats = cfg.get("ats")
    module = _ATS_TO_MODULE.get(ats)
    if not module:
        print(f"Unknown ATS {ats!r} for {matched_name}. Cannot run.")
        sys.exit(1)

    print(f"Testing {matched_name} via {ats}...")
    jobs = module.scrape_company(matched_name, cfg) if ats == "workday" else \
        module.scrape_company(matched_name, cfg["slug"])
    print(f"\n{len(jobs)} matching job(s):")
    for j in jobs:
        loc = ", ".join(j.get("locations", [])) or "Unknown"
        print(f"  - {j['job_title']}  ({loc})")
        if j.get("job_apply_link"):
            print(f"    {j['job_apply_link']}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discovery"
    if mode not in MODES:
        print(f"Unknown mode: {mode!r}. Expected one of {MODES}.")
        sys.exit(2)

    if mode == "test":
        if len(sys.argv) < 3:
            print("Usage: python jobs.py test <company-name>")
            sys.exit(2)
        run_test(" ".join(sys.argv[2:]))
        return

    seen = load_seen_jobs()
    try:
        if mode in ("discovery", "all"):
            run_discovery(seen)
        if mode in ("watchlist", "all"):
            run_watchlist(seen)
    finally:
        save_seen_jobs(seen)


if __name__ == "__main__":
    main()
