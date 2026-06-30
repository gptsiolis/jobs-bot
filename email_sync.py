"""Email-driven job status updates.

Reads the user's Gmail, matches recruiter / ATS notification emails to jobs that
are already in flight, and classifies each as a rejection or an advancement.
High-confidence calls flip the job's status directly (audited in job_events);
anything less certain is written to status_suggestions for one-click review on
the dashboard.

Runs like the scrapers: a scheduled, service-role process. Invoke with

    python email_sync.py            # process the inbox
    python email_sync.py --dry-run  # classify and print, write nothing

Required environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   (DB writes; reuses storage.py)
    ANTHROPIC_API_KEY                         (classification)
    GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN  (read-only inbox)

Optional environment:
    ANTHROPIC_MODEL              default claude-haiku-4-5
    GMAIL_SEARCH_QUERY           default "newer_than:7d -in:chats -from:me"
    EMAIL_MAX_MESSAGES           default 60
    EMAIL_AUTOAPPLY_CONFIDENCE   default 0.8
"""

import base64
import json
import os
import re
import sys

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass

from storage import SupabaseJobStore, utc_now_iso

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_QUERY = "newer_than:7d -in:chats -from:me"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# decision -> resulting job status. "offer" is an advancement, tracked as
# next_round (the evidence note preserves that it was an offer).
DECISION_TO_STATUS = {
    "rejected": "rejected",
    "next_round": "next_round",
    "offer": "next_round",
}

_COMPANY_STOPWORDS = {
    "inc", "llc", "corp", "corporation", "co", "ltd", "the", "labs", "ai",
    "technologies", "technology", "io", "hq", "group", "team", "careers",
    "talent", "recruiting", "people", "no", "reply", "noreply", "notification",
}


def _normalize_company(value):
    value = (value or "").lower()
    value = re.sub(r"[\.,&'/]", " ", value)
    tokens = [t for t in value.split() if t and t not in _COMPANY_STOPWORDS]
    return tokens


def _max_messages():
    try:
        return max(1, int(os.getenv("EMAIL_MAX_MESSAGES", "60")))
    except ValueError:
        return 60


def _autoapply_confidence():
    try:
        return float(os.getenv("EMAIL_AUTOAPPLY_CONFIDENCE", "0.8"))
    except ValueError:
        return 0.8


# --- Gmail ------------------------------------------------------------------


def _gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError(
            "Missing GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN."
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=GMAIL_SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _list_message_ids(service, query, limit):
    ids = []
    page_token = None
    while len(ids) < limit:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=min(100, limit - len(ids)),
                  pageToken=page_token)
            .execute()
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids[:limit]


def _decode_part(data):
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "ignore")
    except Exception:
        return ""


def _extract_body(payload):
    """Walk a Gmail payload tree and return plain-ish text (prefer text/plain)."""
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    if mime == "text/plain" and body_data:
        return _decode_part(body_data)
    parts = payload.get("parts") or []
    texts = [_extract_body(p) for p in parts]
    text = "\n".join(t for t in texts if t)
    if not text and mime == "text/html" and body_data:
        html = _decode_part(body_data)
        text = re.sub(r"<[^>]+>", " ", html)
    return text


def _fetch_message(service, message_id):
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_body(msg.get("payload", {})) or msg.get("snippet", "")
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "body": re.sub(r"\s+", " ", body).strip()[:4000],
    }


# --- Matching ---------------------------------------------------------------


def _candidate_jobs(email, jobs):
    """Jobs whose company plausibly appears in the email's sender/subject/body."""
    haystack = " ".join([email.get("from", ""), email.get("subject", ""),
                         email.get("body", "")]).lower()
    candidates = []
    for job in jobs:
        tokens = _normalize_company(job.get("company"))
        if not tokens:
            continue
        # Require the most distinctive token (longest) to appear, to avoid
        # matching every email on a stopword-ish fragment.
        anchor = max(tokens, key=len)
        if len(anchor) >= 3 and anchor in haystack:
            candidates.append(job)
    return candidates


# --- Classification ---------------------------------------------------------


def _classify(email, candidates):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")
    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)

    job_lines = "\n".join(
        f'  - job_id="{j["job_id"]}": {j.get("title", "")} @ {j.get("company", "")}'
        for j in candidates
    )
    system = (
        "You read a job-seeker's email and decide whether it reports a change to "
        "one of their pending job applications. Respond with JSON only, no prose.\n"
        "Schema: {\"job_id\": string, \"decision\": one of "
        "[\"rejected\", \"next_round\", \"offer\", \"none\"], \"confidence\": number "
        "0..1, \"evidence\": short quote}.\n"
        "- rejected: the company declines / will not move forward.\n"
        "- next_round: invitation to interview, assessment, scheduling, or a "
        "request to move ahead in the process.\n"
        "- offer: a job offer.\n"
        "- none: marketing, newsletters, auto-acknowledgements ('we received your "
        "application'), or anything not about one of the listed jobs.\n"
        "Pick job_id ONLY from the provided list; if no listed job clearly fits, "
        "return job_id=\"\" and decision=\"none\". Be conservative: a generic "
        "auto-acknowledgement is \"none\", not next_round."
    )
    user = (
        f"Candidate jobs in flight:\n{job_lines}\n\n"
        f"Email From: {email.get('from', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Body:\n{email.get('body', '')}"
    )

    resp = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 400,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    ).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"job_id": "", "decision": "none", "confidence": 0.0, "evidence": ""}


# --- Orchestration ----------------------------------------------------------


def process_inbox(dry_run=False):
    store = None if dry_run else SupabaseJobStore()
    # In dry-run we still need read access; build a store unless creds missing.
    read_store = store or _maybe_store()

    service = _gmail_service()
    query = os.getenv("GMAIL_SEARCH_QUERY", DEFAULT_QUERY)
    message_ids = _list_message_ids(service, query, _max_messages())

    already = read_store.processed_message_ids(message_ids) if read_store else set()
    pending_ids = [m for m in message_ids if m not in already]

    jobs = read_store.list_inflight_jobs() if read_store else []
    threshold = _autoapply_confidence()

    run_id = store.create_run("email_sync") if store else None
    stats = {"scanned": len(pending_ids), "matched": 0, "auto_applied": 0,
             "suggested": 0, "skipped": 0}

    try:
        for message_id in pending_ids:
            email = _fetch_message(service, message_id)
            candidates = _candidate_jobs(email, jobs)
            if not candidates:
                stats["skipped"] += 1
                if store:
                    store.record_processed_email(message_id, email["thread_id"],
                                                 decision="no_candidate")
                continue

            result = _classify(email, candidates)
            decision = str(result.get("decision", "none"))
            job_id = str(result.get("job_id", "")).strip()
            confidence = _as_float(result.get("confidence"))
            evidence = str(result.get("evidence", ""))[:500]
            new_status = DECISION_TO_STATUS.get(decision)
            job = next((j for j in candidates if j["job_id"] == job_id), None)

            if not new_status or not job:
                stats["skipped"] += 1
                if store:
                    # Only record a job_id that actually exists (a matched
                    # candidate); the model may echo a plausible-looking id that
                    # isn't in the jobs table, which would break the FK.
                    store.record_processed_email(message_id, email["thread_id"],
                                                 job_id=(job["job_id"] if job else None),
                                                 decision=decision, confidence=confidence)
                continue

            stats["matched"] += 1
            note = _evidence_note(email, decision, confidence, evidence)
            print(f"[{decision} {confidence:.2f}] {job.get('company')} — "
                  f"{job.get('title')} :: {email.get('subject')}")

            if dry_run:
                continue

            if confidence >= threshold and job["status"] != new_status:
                store.set_job_status(job["job_id"], new_status)
                store.log_job_note_event(job["job_id"], "email_auto_update",
                                         job["status"], new_status, note)
                store.insert_status_suggestion(_suggestion(
                    job, new_status, decision, confidence, evidence, email,
                    auto_applied=True, resolved=True, resolution="auto"))
                stats["auto_applied"] += 1
            else:
                store.insert_status_suggestion(_suggestion(
                    job, new_status, decision, confidence, evidence, email,
                    auto_applied=False, resolved=False))
                stats["suggested"] += 1

            store.record_processed_email(message_id, email["thread_id"],
                                         job_id=job["job_id"], decision=decision,
                                         confidence=confidence)

        if store:
            store.finish_run(run_id, "success", total_found=stats["scanned"],
                             total_written=stats["auto_applied"] + stats["suggested"],
                             total_new=stats["auto_applied"], counts=stats)
        print(f"\n[Email sync] scanned {stats['scanned']}; matched {stats['matched']}; "
              f"auto-applied {stats['auto_applied']}; suggested {stats['suggested']}.")
        return stats
    except Exception as exc:
        if store and run_id:
            store.finish_run(run_id, "failed", counts=stats, error=str(exc))
        raise


def _evidence_note(email, decision, confidence, evidence):
    return json.dumps({
        "source": "email_agent",
        "decision": decision,
        "confidence": confidence,
        "subject": email.get("subject", ""),
        "from": email.get("from", ""),
        "evidence": evidence,
        "at": utc_now_iso(),
    })


def _suggestion(job, new_status, decision, confidence, evidence, email,
                auto_applied, resolved, resolution=None):
    return {
        "job_id": job["job_id"],
        "suggested_status": new_status,
        "current_status": job["status"],
        "decision": decision,
        "confidence": confidence,
        "evidence": evidence,
        "email_subject": email.get("subject", ""),
        "email_from": email.get("from", ""),
        "gmail_thread_id": email.get("thread_id"),
        "gmail_message_id": email.get("id"),
        "auto_applied": auto_applied,
        "resolved": resolved,
        "resolution": resolution,
        "resolved_at": utc_now_iso() if resolved else None,
    }


def _as_float(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _maybe_store():
    try:
        return SupabaseJobStore()
    except RuntimeError:
        return None


def main():
    # Email subjects can carry any Unicode; make stdout tolerant so logging a
    # match never crashes the run on a legacy (cp1252) Windows console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    dry_run = "--dry-run" in sys.argv
    process_inbox(dry_run=dry_run)


if __name__ == "__main__":
    main()
