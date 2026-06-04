"""Optional AI ranking for broad job candidates."""

import json
import os

import requests

from scrapers import filters

OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_BATCH_SIZE = 12


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
        "source": job.get("source", ""),
        "fit_bucket": job.get("fit_bucket", ""),
        "fit_reasons": job.get("fit_reasons") or [],
        "description": filters._normalize_text(job.get("job_description", ""))[:2200],
    }


def _apply_result(job, result):
    if not isinstance(result, dict):
        return
    fit_score = result.get("fit_score")
    company_score = result.get("company_score")
    try:
        job["ai_fit_score"] = max(0, min(100, int(fit_score)))
    except (TypeError, ValueError):
        pass
    try:
        job["ai_company_score"] = max(0, min(100, int(company_score)))
    except (TypeError, ValueError):
        pass
    job["role_family"] = str(result.get("role_family") or "")[:80]
    job["seniority_level"] = str(result.get("seniority_level") or "")[:80]
    job["ai_summary"] = str(result.get("summary") or "")[:500]
    job["ai_reject_reasons"] = [
        str(reason)[:120] for reason in (result.get("reject_reasons") or []) if reason
    ][:8]
    job["ai_labels"] = [str(label)[:80] for label in (result.get("labels") or []) if label][:10]
    visibility = result.get("visibility")
    if visibility in {"default", "hidden", "needs_review"}:
        job["visibility"] = visibility
    job["ranking_version"] = "ai-v1"


def _request_rankings(batch, session):
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    prompt = {
        "instructions": (
            "Rank these jobs for an early-career candidate seeking business development, "
            "growth, partnerships, strategy/operations, or investment/alternative-assets "
            "analyst roles. Penalize warehouse/logistics operations, senior roles, low pay, "
            "contract roles, and unclear sponsor eligibility. Return JSON only."
        ),
        "jobs": [_job_payload(job) for job in batch],
    }
    schema = {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "fit_score": {"type": "integer"},
                        "company_score": {"type": "integer"},
                        "role_family": {"type": "string"},
                        "seniority_level": {"type": "string"},
                        "summary": {"type": "string"},
                        "reject_reasons": {"type": "array", "items": {"type": "string"}},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "visibility": {
                            "type": "string",
                            "enum": ["default", "hidden", "needs_review"],
                        },
                    },
                    "required": [
                        "job_id",
                        "fit_score",
                        "company_score",
                        "role_family",
                        "seniority_level",
                        "summary",
                        "reject_reasons",
                        "labels",
                        "visibility",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["jobs"],
        "additionalProperties": False,
    }
    response = session.post(
        OPENAI_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": json.dumps(prompt),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "job_rankings",
                    "schema": schema,
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
    daily_limit = _daily_limit()
    candidates = jobs[:daily_limit] if daily_limit is not None else jobs
    errors = []
    ranked = 0
    by_id = {job.get("job_id"): job for job in candidates}
    for start in range(0, len(candidates), _batch_size()):
        batch = candidates[start : start + _batch_size()]
        try:
            result = _request_rankings(batch, session)
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        for item in result.get("jobs") or []:
            job = by_id.get(item.get("job_id"))
            if not job:
                continue
            if job.get("fit_bucket") == "reject":
                item["visibility"] = "hidden"
            _apply_result(job, item)
            ranked += 1
    return {"enabled": True, "ranked": ranked, "errors": errors}
