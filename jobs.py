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
    COMPANY_BOARDS,
)
from scrapers import getro, consider, yc, wellfound, greenhouse, lever, ashby

SEEN_JOBS_FILE = "seen_jobs.json"

MODES = ("discovery", "watchlist", "all")


def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)


def deduplicate(jobs, seen_ids):
    """Remove duplicates (including cross-board) and already-seen jobs."""
    unique = []
    seen_titles = set()  # (normalized_title, normalized_company) for cross-board dedup
    for job in jobs:
        jid = job["job_id"]
        if jid in seen_ids:
            continue

        # Cross-board dedup: same role at same company from different sources
        key = (job["job_title"].lower().strip(), job["employer_name"].lower().strip())
        if key in seen_titles:
            continue

        seen_ids.add(jid)
        seen_titles.add(key)
        unique.append(job)
    return unique


def send_email(jobs, heading, subject_prefix):
    if not jobs:
        print(f"\n[{heading}] No new jobs found.")
        return

    by_source = {}
    for job in jobs:
        source = job.get("source", "other")
        by_source.setdefault(source, []).append(job)

    body = f"<h2>{heading}</h2>"
    body += f"<p><b>{len(jobs)} new listings</b> from {len(by_source)} sources</p><hr>"

    for source, source_jobs in sorted(by_source.items()):
        if source.startswith("getro:"):
            source_label = source.replace("getro:", "") + " Portfolio"
        elif source.startswith("consider:"):
            source_label = source.replace("consider:", "") + " Portfolio"
        elif source.startswith("greenhouse:"):
            source_label = source.replace("greenhouse:", "")
        elif source.startswith("lever:"):
            source_label = source.replace("lever:", "")
        elif source == "Y Combinator":
            source_label = "Y Combinator (Work at a Startup)"
        elif source == "Wellfound":
            source_label = "Wellfound (AngelList)"
        else:
            source_label = source

        body += f"<h3>{source_label} ({len(source_jobs)})</h3>"

        for job in source_jobs:
            title = job.get("job_title", "N/A")
            company = job.get("employer_name", "N/A")

            locations = job.get("locations", [])
            city = job.get("job_city", "")
            state = job.get("job_state", "")
            if locations:
                location = ", ".join(locations)
            elif city or state:
                parts = [p for p in [city, state] if p]
                location = ", ".join(parts)
            else:
                location = "Unknown"

            if job.get("job_is_remote") or job.get("work_mode") == "remote":
                location = f"{location} (Remote)" if location != "Unknown" else "Remote"

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

    new_jobs = deduplicate(all_jobs, seen)
    print(f"Watchlist total new jobs after dedup: {len(new_jobs)}")
    send_email(
        new_jobs,
        heading="Daily Watchlist",
        subject_prefix="Daily Watchlist",
    )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discovery"
    if mode not in MODES:
        print(f"Unknown mode: {mode!r}. Expected one of {MODES}.")
        sys.exit(2)

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
