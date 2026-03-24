import requests
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import (
    SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, RAPIDAPI_KEY,
    SEARCH_QUERIES, ALLOWED_LOCATIONS, STARTUP_KEYWORDS,
)

SEEN_JOBS_FILE = "seen_jobs.json"

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return []

def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f)

def fetch_jobs(query):
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {
        "query": query,
        "page": "1",
        "num_pages": "1",
        "date_posted": "week"
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    print("API response:", json.dumps(data, indent=2)[:500])
    return data.get("data", [])

def matches_location(job):
    """Return True if the job is in Miami, Florida, or remote."""
    city = (job.get("job_city") or "").lower()
    state = (job.get("job_state") or "").lower()
    country = (job.get("job_country") or "").lower()
    is_remote = job.get("job_is_remote", False)
    title = (job.get("job_title") or "").lower()
    description = (job.get("job_description") or "").lower()

    if is_remote:
        return True

    location_blob = f"{city} {state} {country} {title} {description}"
    return any(loc in location_blob for loc in ALLOWED_LOCATIONS)


def matches_startup_keywords(job):
    """Return True if the job looks like it's at a VC-backed / startup company."""
    description = (job.get("job_description") or "").lower()
    employer = (job.get("employer_name") or "").lower()
    title = (job.get("job_title") or "").lower()
    blob = f"{description} {employer} {title}"
    return any(kw in blob for kw in STARTUP_KEYWORDS)


def filter_jobs(jobs, seen_ids):
    filtered = []
    for job in jobs:
        job_id = job.get("job_id")
        if job_id in seen_ids:
            continue
        if not matches_location(job):
            continue
        if not matches_startup_keywords(job):
            continue
        filtered.append(job)
    return filtered

def send_email(jobs):
    if not jobs:
        print("No new jobs found.")
        return

    body = "<h2>New Sales Jobs at VC-Backed Startups</h2>"
    for job in jobs:
        title = job.get("job_title", "N/A")
        company = job.get("employer_name", "N/A")
        is_remote = job.get("job_is_remote", False)
        city = job.get("job_city") or ""
        state = job.get("job_state") or ""
        parts = [p for p in [city, state] if p]
        location = ", ".join(parts) if parts else job.get("job_country") or "Unknown"
        if is_remote:
            location = f"{location} (Remote)" if parts else "Remote"
        link = job.get("job_apply_link", "#")
        body += f"<p><b>{title}</b> — {company} — {location}<br><a href='{link}'>Apply</a></p>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Jobs Digest — {len(jobs)} new listings"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"Email sent with {len(jobs)} jobs.")

def run():
    seen = load_seen_jobs()
    all_new_jobs = []

    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        jobs = fetch_jobs(query)
        new_jobs = filter_jobs(jobs, seen)
        all_new_jobs.extend(new_jobs)
        for job in new_jobs:
            seen.append(job.get("job_id"))

    save_seen_jobs(seen)
    send_email(all_new_jobs)

if __name__ == "__main__":
    run()