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
from company_registry import (
    QUALITY_RANK,
    SPONSOR_RANK,
    metadata_for_company,
    sponsor_label,
)
from scrapers import (
    getro, consider, yc, wellfound, greenhouse, lever, ashby, workday,
    workable, smartrecruiters, dayforce, breezy, phenom, board_resolver,
    job_search,
)
from scrapers.filters import FIT_BUCKET_LABELS, add_fit_metadata
from storage import (
    SupabaseJobStore,
    counts_by_source,
    job_location_string,
    normalize_job_record,
)
import ai_ranker
import company_leads

SEEN_JOBS_FILE = "seen_jobs.json"
SEEN_TTL_DAYS = 60

MODES = ("discovery", "watchlist", "job_search", "source_expansion", "all", "test", "sync")

FIT_BUCKET_ORDER = ("strong", "possible", "unknown")


def _render_job(job):
    title = job.get("job_title", "N/A")
    company = job.get("employer_name", "N/A")
    location = job_location_string(job)
    link = job.get("job_apply_link", "#")
    reasons = job.get("fit_reasons") or []
    sponsor = sponsor_label(job.get("sponsor_tier"))
    quality = (job.get("quality_tier") or "acceptable").replace("_", " ")
    html = f"<p><b>{title}</b> &mdash; {company} &mdash; {location}"
    html += f"<br><span style='color:#666'>Sponsor: {sponsor} &middot; Company: {quality}</span>"
    if reasons:
        html += f"<br><span style='color:#666'>Fit: {', '.join(reasons)}</span>"
    sponsor_reasons = job.get("sponsor_reasons") or []
    if sponsor_reasons:
        html += f"<br><span style='color:#666'>Work auth: {', '.join(sponsor_reasons)}</span>"
    if link and link != "#":
        html += f"<br><a href='{link}'>Apply</a>"
    html += "</p>"
    return html


def _enrich_company_metadata(job):
    metadata = metadata_for_company(job.get("employer_name", ""))
    for key, value in metadata.items():
        job.setdefault(key, value)
    return job


def _job_sort_key(job):
    return (
        SPONSOR_RANK.get(job.get("sponsor_tier"), 99),
        QUALITY_RANK.get(job.get("quality_tier"), 99),
        job.get("employer_name", "").lower(),
        job.get("job_title", "").lower(),
    )


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
    if source.startswith("dayforce:"):
        return source.replace("dayforce:", "")
    if source == "Y Combinator":
        return "Y Combinator (Work at a Startup)"
    if source == "Wellfound":
        return "Wellfound (AngelList)"
    return source


def send_email(jobs, heading, subject_prefix):
    if not jobs:
        print(f"\n[{heading}] No new jobs found.")
        return
    if not (SENDER_EMAIL and SENDER_PASSWORD and RECIPIENT_EMAIL):
        raise RuntimeError(
            "Email mode requires SENDER_EMAIL, SENDER_PASSWORD, and RECIPIENT_EMAIL."
        )

    # Metro breakdown for the email header
    metro_counts = {}
    for job in jobs:
        metro = _categorize_metro(job_location_string(job))
        metro_counts[metro] = metro_counts.get(metro, 0) + 1

    by_bucket = {}
    for job in jobs:
        _enrich_company_metadata(job)
        if not job.get("fit_bucket"):
            add_fit_metadata(job)
        by_bucket.setdefault(job.get("fit_bucket", "unknown"), []).append(job)

    total_sources = len({j.get("source", "other") for j in jobs})

    body = f"<h2>{heading}</h2>"
    body += f"<p><b>{len(jobs)} new listings</b> from {total_sources} sources</p>"
    breakdown = " &middot; ".join(
        f"{metro}: {count}"
        for metro, count in sorted(metro_counts.items(), key=lambda x: (-x[1], x[0]))
    )
    body += f"<p style='color:#666'>{breakdown}</p><hr>"

    # Sections in fit order, each sub-grouped by source.
    for bucket in FIT_BUCKET_ORDER:
        bucket_jobs = by_bucket.get(bucket, [])
        if not bucket_jobs:
            continue
        label = FIT_BUCKET_LABELS.get(bucket, bucket.title())
        body += f"<h3>{label} ({len(bucket_jobs)})</h3>"

        by_source = {}
        for job in bucket_jobs:
            by_source.setdefault(job.get("source", "other"), []).append(job)

        # Sources sorted by best sponsor/company quality, then job count.
        sources_sorted = sorted(
            by_source.items(),
            key=lambda x: (min(_job_sort_key(j) for j in x[1]), -len(x[1]), x[0]),
        )
        for source, source_jobs in sources_sorted:
            source_label = _format_source_label(source)
            body += f"<h4>{source_label} ({len(source_jobs)})</h4>"
            for job in sorted(source_jobs, key=_job_sort_key):
                body += _render_job(job)
        body += "<hr>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject_prefix} — {len(jobs)} new listings"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"\n[{heading}] Email sent with {len(jobs)} jobs.")


def _prepare_jobs(jobs):
    for job in jobs:
        _enrich_company_metadata(job)
        if not job.get("fit_bucket"):
            add_fit_metadata(job)
    return jobs


def _apply_board_metadata(jobs, company_boards):
    metadata_by_company = {
        name.lower(): {
            "sector": cfg.get("sector", "other"),
            "quality_tier": cfg.get("quality_tier", "acceptable"),
            "sponsor_tier": cfg.get("sponsor_tier", "unknown_no_ban"),
            "source_notes": cfg.get("source_notes", ""),
        }
        for name, cfg in company_boards.items()
    }
    for job in jobs:
        metadata = metadata_by_company.get((job.get("employer_name") or "").lower())
        if not metadata:
            continue
        for key, value in metadata.items():
            job.setdefault(key, value)
    return jobs


def _coerce_ats_config(ats_config, company_name):
    """Return a resolved request's ats_config as a dict, or None if unusable.

    Resolved watchlist requests normally store ats_config as a JSON object, but a
    row can come back as a JSON-encoded *string* (double-encoded on write). Passing
    that string to dict() raises ValueError and would crash the entire watchlist
    run, so parse defensively and skip any row we can't turn into a mapping rather
    than taking down every other company with it.
    """
    if isinstance(ats_config, dict):
        return dict(ats_config)
    if isinstance(ats_config, str):
        try:
            parsed = json.loads(ats_config)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    print(f"[Watchlist] Skipping {company_name!r}: unusable ats_config {ats_config!r}")
    return None


def _load_dynamic_company_boards(store=None):
    try:
        store = store or SupabaseJobStore()
        requests = store.list_company_watchlist_requests()
    except RuntimeError:
        return {}

    boards = {}
    for request in requests:
        company_name = request.get("company_name") or ""
        status = request.get("status")
        ats_config = request.get("ats_config")
        if status == "resolved" and ats_config:
            config = _coerce_ats_config(ats_config, company_name)
            if config is None:
                continue
        elif status in {"pending", "unresolved"}:
            config, error = board_resolver.resolve_company_board(company_name)
            if not config:
                store.update_company_watchlist_request(
                    request["id"],
                    "unresolved",
                    ats_config=None,
                    error=error or "No supported public ATS board found",
                )
                continue
            store.update_company_watchlist_request(
                request["id"],
                "resolved",
                ats_config=config,
                error=None,
            )
        else:
            continue

        # Defense in depth: a resolver regression (or corrupt stored config) must
        # never reach setdefault and take down the whole watchlist run. Skip any
        # row whose config didn't end up a usable mapping.
        if not isinstance(config, dict):
            print(f"[Watchlist] Skipping {company_name!r}: non-dict config {config!r}")
            continue

        config.setdefault("sector", request.get("sector") or "user_added")
        config.setdefault("quality_tier", request.get("quality_tier") or "acceptable")
        config.setdefault("sponsor_tier", request.get("sponsor_tier") or "unknown_no_ban")
        config.setdefault("source_notes", request.get("source_notes") or "Added from dashboard")
        boards[company_name] = config
    return boards


def _company_boards_for_watchlist(store=None):
    boards = dict(COMPANY_BOARDS)
    boards.update(_load_dynamic_company_boards(store=store))
    return boards


def collect_discovery_jobs():
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

    return _prepare_jobs(all_jobs)


def run_discovery(seen):
    all_jobs = collect_discovery_jobs()
    new_jobs = deduplicate(all_jobs, seen)
    print(f"Discovery total new jobs after dedup: {len(new_jobs)}")
    send_email(
        new_jobs,
        heading="Daily VC Discovery",
        subject_prefix="Daily VC Discovery",
    )


def collect_watchlist_jobs(store=None):
    """Mode B — per-company ATS scrapers for the curated allowlist.

    Hits each allowlisted company's own Greenhouse/Lever/Ashby board directly
    and applies filters.passes_watchlist for role + location + seniority.
    """
    print("="*50)
    print("WATCHLIST MODE — per-company ATS scrapers")
    print("="*50)
    company_boards = _company_boards_for_watchlist(store=store)
    all_jobs = []
    all_jobs.extend(greenhouse.scrape_all(company_boards))
    all_jobs.extend(lever.scrape_all(company_boards))
    all_jobs.extend(ashby.scrape_all(company_boards))
    all_jobs.extend(workday.scrape_all(company_boards))
    all_jobs.extend(workable.scrape_all(company_boards))
    all_jobs.extend(smartrecruiters.scrape_all(company_boards))
    all_jobs.extend(dayforce.scrape_all(company_boards))
    all_jobs.extend(breezy.scrape_all(company_boards))
    all_jobs.extend(phenom.scrape_all(company_boards))

    _apply_board_metadata(all_jobs, company_boards)
    return _prepare_jobs(all_jobs)


def run_watchlist(seen):
    all_jobs = collect_watchlist_jobs()
    new_jobs = deduplicate(all_jobs, seen)
    print(f"Watchlist total new jobs after dedup: {len(new_jobs)}")
    send_email(
        new_jobs,
        heading="Daily Watchlist",
        subject_prefix="Daily Watchlist",
    )


def collect_job_search_jobs():
    jobs = job_search.scrape()
    return _prepare_jobs(jobs)

def run_source_expansion(store):
    if not store:
        return []
    _load_dynamic_company_boards(store=store)
    print("[Source expansion] Auto-promotion from broad search is disabled; use manual dashboard additions.")
    return []


_ATS_TO_MODULE = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workday": workday,
    "workable": workable,
    "smartrecruiters": smartrecruiters,
    "dayforce": dayforce,
    "breezy": breezy,
    "phenom": phenom,
}


def _scraper_failures():
    failures = []
    for module in (getro, consider, yc, wellfound, greenhouse, lever, ashby,
                   workday, workable, smartrecruiters, dayforce, breezy, phenom):
        if hasattr(module, "get_failures"):
            failures.extend(module.get_failures())
    return failures


def collect_jobs_for_mode(mode, store=None):
    if mode == "watchlist":
        return collect_watchlist_jobs(store=store)
    if mode == "discovery":
        return collect_discovery_jobs()
    if mode == "job_search":
        return collect_job_search_jobs()
    if mode == "source_expansion":
        return run_source_expansion(store)
    if mode == "all":
        jobs = []
        jobs.extend(collect_discovery_jobs())
        jobs.extend(collect_watchlist_jobs(store=store))
        jobs.extend(collect_job_search_jobs())
        return jobs
    raise ValueError("Unknown sync mode: " + repr(mode))

def run_sync(mode, dry_run=False):
    if mode not in ("watchlist", "discovery", "job_search", "source_expansion", "all"):
        print("Usage: python jobs.py sync [watchlist|discovery|job_search|source_expansion|all] [--dry-run]")
        sys.exit(2)

    store = None if dry_run else SupabaseJobStore()
    run_id = None
    jobs = []
    result = {"total_written": 0, "total_new": 0}
    ai_result = {"enabled": False, "ranked": 0, "errors": []}
    company_leads_recorded = 0
    company_leads_promoted = 0
    archived_stale = 0
    rejected_stale = 0
    try:
        if store:
            run_id = store.create_run(mode)
        jobs = collect_jobs_for_mode(mode, store=store)
        ai_result = ai_ranker.rank_jobs(jobs)
        source_counts = counts_by_source(jobs)
        if dry_run:
            normalized = [normalize_job_record(job) for job in jobs if job.get("job_id")]
            result = {
                "total_written": len(normalized),
                "total_new": 0,
                "records": normalized,
                "dry_run": True,
            }
        else:
            result = store.upsert_jobs(jobs)
            if mode in ("job_search", "all"):
                company_leads_recorded = company_leads.record_company_leads(store, jobs)
                company_leads_promoted = 0
            if mode == "watchlist":
                archived_stale = store.archive_unmatched_new_jobs(
                    [job["job_id"] for job in jobs if job.get("job_id")]
                )
                rejected_stale = store.reject_stale_applied_jobs(max_age_days=60)
        if store:
            store.finish_run(
                run_id,
                "success",
                total_found=len(jobs),
                total_written=result["total_written"],
                total_new=result["total_new"],
                counts=source_counts,
                failures=_scraper_failures() + ([{"component": "ai_ranker", "errors": ai_result.get("errors", [])}] if ai_result.get("errors") else []),
            )
        suffix = " (dry run)" if dry_run else ""
        print(
            f"\n[Sync{suffix}] {len(jobs)} matched; "
            f"{result['total_written']} written; {result['total_new']} new."
        )
        if archived_stale:
            print(f"[Sync] Archived {archived_stale} unmatched new watchlist jobs.")
        if rejected_stale:
            print(f"[Sync] Rejected {rejected_stale} applied jobs older than 60 days.")
        if ai_result.get("ranked"):
            print(f"[Sync] AI ranked {ai_result['ranked']} jobs.")
        if company_leads_recorded or company_leads_promoted:
            print(f"[Sync] Recorded {company_leads_recorded} company leads; promoted {company_leads_promoted}.")
    except Exception as exc:
        if store and run_id:
            store.finish_run(
                run_id,
                "failed",
                total_found=len(jobs),
                total_written=result.get("total_written", 0),
                total_new=result.get("total_new", 0),
                counts=counts_by_source(jobs),
                failures=_scraper_failures() + ([{"component": "ai_ranker", "errors": ai_result.get("errors", [])}] if ai_result.get("errors") else []),
                error=str(exc),
            )
        raise


def run_test(company_query):
    """Dry-run a single company. Prints matches; sends no email, updates no state."""
    query_norm = company_query.lower().strip()
    # Prefer exact match; fall back to substring
    company_boards = _company_boards_for_watchlist()
    matched_name = next((n for n in company_boards if n.lower() == query_norm), None)
    if not matched_name:
        matched_name = next(
            (n for n in company_boards if query_norm in n.lower()), None,
        )

    if not matched_name:
        print(f"No company in COMPANY_BOARDS matches {company_query!r}.")
        print(f"Available companies:")
        for name in sorted(company_boards):
            print(f"  - {name}")
        sys.exit(1)

    cfg = company_boards[matched_name]
    ats = cfg.get("ats")
    module = _ATS_TO_MODULE.get(ats)
    if not module:
        print(f"Unknown ATS {ats!r} for {matched_name}. Cannot run.")
        sys.exit(1)

    print(f"Testing {matched_name} via {ats}...")
    if ats in ("workday", "phenom"):
        jobs = module.scrape_company(matched_name, cfg)
    elif ats == "greenhouse":
        jobs = module.scrape_company(matched_name, cfg["slug"], cfg.get("bu_filter"))
    elif ats == "smartrecruiters":
        jobs = module.scrape_company(
            matched_name, cfg["slug"],
            brand_filter=cfg.get("brand_filter"),
            segment_filter=cfg.get("segment_filter"),
        )
    elif ats == "dayforce":
        jobs = module.scrape_company(
            matched_name,
            cfg["company"],
            board_code=cfg.get("board_code"),
        )
    else:
        jobs = module.scrape_company(matched_name, cfg["slug"])
    print(f"\n{len(jobs)} matching job(s):")
    for j in jobs:
        _enrich_company_metadata(j)
        loc = ", ".join(j.get("locations", [])) or "Unknown"
        print(f"  - {j['job_title']}  ({loc})")
        print(
            f"    Sponsor: {sponsor_label(j.get('sponsor_tier'))}; "
            f"Company: {j.get('quality_tier', 'acceptable')}"
        )
        reasons = ", ".join(j.get("fit_reasons") or [])
        if reasons:
            print(f"    Fit: {j.get('fit_bucket', 'unknown')} - {reasons}")
        if j.get("job_apply_link"):
            print(f"    {j['job_apply_link']}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discovery"
    if mode not in MODES:
        print(f"Unknown mode: {mode!r}. Expected one of {MODES}.")
        sys.exit(2)

    if mode == "sync":
        sync_mode = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "watchlist"
        dry_run = "--dry-run" in sys.argv
        run_sync(sync_mode, dry_run=dry_run)
        return

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
