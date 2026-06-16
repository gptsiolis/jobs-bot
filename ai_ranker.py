"""Optional OpenAI-powered attainability ranking for job candidates.

Judges each job for an early-career candidate, personalized by the user's own
applied/dismissed history, and can hide roles it deems out of reach. Gated by
AI_RANKING_ENABLED + OPENAI_API_KEY; falls back to deterministic scoring when
disabled or on any error.
"""

import json
import os

import requests

from scrapers import filters

OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_BATCH_SIZE = 12
EXAMPLE_LIMIT = 25

# The candidate's experience baseline that attainability is judged against.
# Override per-run with the CANDIDATE_EXPERIENCE env var rather than editing
# this prompt.
DEFAULT_EXPERIENCE = "a candidate with new-grad to roughly 2 years of full-time experience"

RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "attainable": {"type": "boolean"},
                    "fit_score": {"type": "integer"},
                    "company_score": {"type": "integer"},
                    "seniority_level": {"type": "string"},
                    "summary": {"type": "string"},
                    "reject_reasons": {"type": "array", "items": {"type": "string"}},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "job_id", "attainable", "fit_score", "company_score",
                    "seniority_level", "summary", "reject_reasons", "labels",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["jobs"],
    "additionalProperties": False,
}


def _experience_profile():
    return os.getenv("CANDIDATE_EXPERIENCE", "").strip() or DEFAULT_EXPERIENCE


def enabled():
    return os.getenv("AI_RANKING_ENABLED", "").lower() in {"1", "true", "yes"} and bool(
        os.getenv("OPENAI_API_KEY")
    )


def _batch_size():
    try:
        return max(1, int(os.getenv("AI_BATCH_SIZE", DEFAULT_BATCH_SIZE)))
    except ValueError:
        return DEFAULT_BATCH_SIZE


def _daily_limit():
    raw = os.getenv("AI_DAILY_JOB_LIMIT", "").strip()
    if not raw:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def _job_payload(job):
    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("job_title", ""),
        "company": job.get("employer_name", ""),
        "location": ", ".join(job.get("locations") or []),
        "fit_bucket": job.get("fit_bucket", ""),
        "role_family": job.get("role_family", ""),
        "description": filters._normalize_text(job.get("job_description", ""))[:2000],
    }


def _load_feedback_examples(session=None):
    """Return (applied, dismissed) example label lists from the user's history."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return [], []
    session = session or requests.Session()
    headers = {"apikey": key, "Authorization": "Bearer " + key}

    def fetch(statuses):
        status_filter = ",".join(statuses)
        endpoint = (
            url + "/rest/v1/jobs?select=title,company"
            f"&status=in.({status_filter})&order=last_seen_at.desc&limit={EXAMPLE_LIMIT}"
        )
        try:
            resp = session.get(endpoint, headers=headers, timeout=15)
            resp.raise_for_status()
            rows = resp.json()
        except (requests.RequestException, ValueError):
            return []
        labels = []
        for row in rows or []:
            title = (row.get("title") or "").strip()
            company = (row.get("company") or "").strip()
            if title:
                labels.append(f"{title} — {company}" if company else title)
        return labels

    return fetch(["applied", "applied_messaged", "next_round"]), fetch(["dismissed", "rejected"])


def _instructions(applied, dismissed):
    applied_block = "\n".join("  - " + label for label in applied) or "  (none yet)"
    dismissed_block = "\n".join("  - " + label for label in dismissed) or "  (none yet)"
    return (
        "You screen jobs for " + _experience_profile() + ", targeting US (or "
        "US-remote) roles at venture-backed startups. Priority order of role types: "
        "(1) operations / strategy / chief-of-staff, (2) business development / "
        "partnerships / sales, (3) other early-career business roles.\n\n"
        "For each job return:\n"
        "- attainable: true if this candidate could realistically be hired. Roles "
        "asking up to ~2-3 years of experience are in range; treat 3-4 years as a "
        "stretch (still attainable, but a reach). Clearly senior or lead roles, 5+ "
        "years required, or real management/leadership responsibility -> false.\n"
        "- fit_score (0-100): overall desirability combining role-type priority "
        "(ops/strategy/chief-of-staff highest), attainability, and resemblance to "
        "the roles the candidate has APPLIED to versus DISMISSED.\n"
        "- company_score (0-100): quality/desirability of the company.\n"
        "- seniority_level: one of entry, mid, senior.\n"
        "- summary: one short sentence.\n"
        "- reject_reasons: brief reasons it's a poor fit, if any.\n"
        "- labels: a few short tags.\n\n"
        "The candidate's own history is the strongest signal — weight it heavily.\n"
        "APPLIED TO (wants more like these):\n" + applied_block + "\n"
        "DISMISSED / REJECTED (avoid these):\n" + dismissed_block + "\n\n"
        "Return JSON only."
    )


def _apply_result(job, result):
    if not isinstance(result, dict):
        return
    try:
        job["ai_fit_score"] = max(0, min(100, int(result.get("fit_score"))))
    except (TypeError, ValueError):
        pass
    try:
        job["ai_company_score"] = max(0, min(100, int(result.get("company_score"))))
    except (TypeError, ValueError):
        pass
    job["seniority_level"] = str(result.get("seniority_level") or "")[:80]
    job["ai_summary"] = str(result.get("summary") or "")[:500]
    job["ai_reject_reasons"] = [
        str(reason)[:120] for reason in (result.get("reject_reasons") or []) if reason
    ][:8]
    job["ai_labels"] = [str(label)[:80] for label in (result.get("labels") or []) if label][:10]
    # A confident "not attainable" verdict hides the role; otherwise leave
    # visibility to the deterministic score. role_family is deliberately NOT
    # overwritten — it drives the dashboard grouping/priority logic.
    if result.get("attainable") is False:
        job["visibility"] = "hidden"
    job["ranking_version"] = "ai-v2"


def _request_rankings(instructions, batch, session):
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    payload = {"instructions": instructions, "jobs": [_job_payload(job) for job in batch]}
    response = session.post(
        OPENAI_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": json.dumps(payload),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "job_rankings",
                    "schema": RANKING_SCHEMA,
                    "strict": True,
                }
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    output = data.get("output") or []
    text_parts = []
    for item in output:
        for content in item.get("content") or []:
            if content.get("type") in {"output_text", "text"}:
                text_parts.append(content.get("text", ""))
    if not text_parts and data.get("output_text"):
        text_parts.append(data["output_text"])
    return json.loads("".join(text_parts))


def rank_jobs(jobs, session=None):
    if not enabled() or not jobs:
        return {"enabled": False, "ranked": 0, "errors": []}

    session = session or requests.Session()
    applied, dismissed = _load_feedback_examples(session)
    instructions = _instructions(applied, dismissed)

    # Only rank jobs that cleared the deterministic gate; rejects are already
    # hidden, so spending model calls on them is wasted.
    candidates = [job for job in jobs if job.get("fit_bucket") != "reject"]
    daily_limit = _daily_limit()
    if daily_limit is not None:
        candidates = candidates[:daily_limit]

    errors = []
    ranked = 0
    by_id = {job.get("job_id"): job for job in candidates}
    for start in range(0, len(candidates), _batch_size()):
        batch = candidates[start : start + _batch_size()]
        try:
            result = _request_rankings(instructions, batch, session)
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        for item in result.get("jobs") or []:
            job = by_id.get(item.get("job_id"))
            if not job:
                continue
            _apply_result(job, item)
            ranked += 1
    return {"enabled": True, "ranked": ranked, "errors": errors}
