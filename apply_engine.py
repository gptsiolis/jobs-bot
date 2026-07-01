"""Auto-apply draft engine (Phase 3, backbone).

Reads jobs the user queued for application from the dashboard, and for each one:
  1. Enforces the hard salary floor (skip jobs known to pay below
     applicant_profile.minimum_salary).
  2. Maps the applicant profile onto standard application fields.
  3. Drafts concise answers to the common free-text questions, tailored to the
     job, using Claude.
  4. Saves the result back to the draft as 'needs_review'.

It deliberately does NOT submit anything — submission happens only after the
user approves a draft on the dashboard, via the browser runner. Run with:

    python apply_engine.py            # draft all queued jobs
    python apply_engine.py --dry-run  # draft and print, write nothing

Required env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY.
Optional: ANTHROPIC_DRAFT_MODEL (default claude-sonnet-4-6).
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
except Exception:  # pragma: no cover
    pass

from storage import SupabaseJobStore

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_DRAFT_MODEL = "claude-sonnet-4-6"

# The free-text questions almost every application asks. We pre-draft these so
# they're ready to review; the browser runner maps them onto the real form.
COMMON_QUESTIONS = [
    "Why are you interested in this role at {company}?",
    "What makes you a strong fit for this position?",
    "Briefly introduce yourself.",
]


def _draft_model():
    return os.getenv("ANTHROPIC_DRAFT_MODEL") or os.getenv("ANTHROPIC_MODEL") or DEFAULT_DRAFT_MODEL


def _split_name(full_name):
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def salary_skip_reason(job, floor):
    """Return a skip reason if the job is KNOWN to pay below the floor, else None.

    Unknown compensation is allowed through — most startups don't post a number,
    and blocking all of them would skip nearly everything. We only skip when even
    the top of the posted range is below the floor.
    """
    if not floor:
        return None
    comp_max = job.get("compensation_max")
    if comp_max is not None and comp_max < floor:
        return f"below salary floor (${floor:,})"
    return None


def map_profile_fields(profile):
    """Standard form fields, drawn truthfully from the profile.

    Location rule: we fill the applicant's real location (which may be blank) and
    always carry the relocation flag. We never fabricate a location or copy the
    job's city — that's what risks an automated location mismatch rejection.
    """
    first, last = _split_name(profile.get("full_name"))
    return {
        "full_name": profile.get("full_name", ""),
        "first_name": first,
        "last_name": last,
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "location": profile.get("location", ""),
        "postal_code": profile.get("postal_code", ""),
        "open_to_relocation": bool(profile.get("willing_to_relocate")),
        "linkedin_url": profile.get("linkedin_url", ""),
        "github_url": profile.get("github_url", ""),
        "portfolio_url": profile.get("portfolio_url", ""),
        "years_experience": profile.get("years_experience", ""),
        "work_authorized": profile.get("work_authorized"),
        "requires_sponsorship": profile.get("requires_sponsorship"),
        "earliest_start": profile.get("earliest_start", ""),
        "salary_expectation": profile.get("salary_expectation", ""),
        "resume_filename": profile.get("resume_filename", ""),
    }


def ensure_resume_text(store, profile):
    """Parse the uploaded resume PDF to text once, so drafts can use real
    experience instead of generic filler. Stores the text back on the profile.
    Best-effort: on any failure, returns "" and leaves drafting to profile data.
    """
    if (profile.get("resume_text") or "").strip():
        return profile["resume_text"]
    path = profile.get("resume_path")
    if not path or not path.lower().endswith(".pdf"):
        return ""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        raw = store.download_resume(path)
        b64 = base64.standard_b64encode(raw).decode("ascii")
        resp = requests.post(
            ANTHROPIC_ENDPOINT,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _draft_model(),
                "max_tokens": 4000,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {
                            "type": "base64", "media_type": "application/pdf", "data": b64}},
                        {"type": "text", "text":
                            "Extract the full plain text of this resume. Return only the text."},
                    ],
                }],
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = "".join(
            b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text"
        ).strip()
        if text:
            store.save_resume_text(path, text)
            profile["resume_text"] = text
            print(f"[resume] parsed {len(text)} chars from {profile.get('resume_filename', path)}")
        return text
    except Exception as exc:
        print(f"[resume] parse skipped: {exc}")
        return ""


def _candidate_summary(profile):
    bits = []
    if profile.get("years_experience"):
        bits.append(f"~{profile['years_experience']} years experience")
    if profile.get("location"):
        bits.append(f"based in {profile['location']}")
    if profile.get("willing_to_relocate"):
        bits.append("open to relocation")
    summary = "; ".join(bits)
    resume = (profile.get("resume_text") or "").strip()
    if resume:
        summary += "\nResume:\n" + resume[:4000]
    return summary or "an early-career candidate"


def draft_answers(job, profile):
    """Draft concise, honest answers to the common questions for this job."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")

    company = job.get("company", "")
    questions = [q.format(company=company or "the company") for q in COMMON_QUESTIONS]
    system = (
        "You help a job seeker draft application answers. Write in the "
        "candidate's first person, concise (2-4 sentences each), specific, and "
        "honest — never invent facts, employers, degrees, or metrics not given. "
        "If you lack a detail, stay general rather than fabricate. NEVER write a "
        "bracketed placeholder like [location], [company], or [X years]; if a "
        "detail is unknown, simply omit it and phrase the sentence naturally. Do "
        "not state a specific city or current employer unless it is given. Return "
        'JSON only: {"answers": [{"question": str, "answer": str}, ...]} covering '
        "exactly the questions provided, in order."
    )
    user = (
        f"Candidate: {_candidate_summary(profile)}\n\n"
        f"Job: {job.get('title', '')} at {company}\n"
        f"Job description:\n{(job.get('description_excerpt') or '')[:2500]}\n\n"
        "Questions:\n" + "\n".join(f"- {q}" for q in questions)
    )

    resp = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _draft_model(),
            "max_tokens": 1200,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    text = "".join(
        b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text"
    ).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    try:
        data = json.loads(text)
        answers = data.get("answers", [])
    except (json.JSONDecodeError, ValueError):
        answers = [{"question": q, "answer": ""} for q in questions]
    return answers


def process_queue(dry_run=False):
    store = SupabaseJobStore()
    profile = store.get_applicant_profile()
    if not profile:
        print("[Apply] No applicant profile found — fill it in on the dashboard first.")
        return {"queued": 0, "drafted": 0, "skipped": 0}

    ensure_resume_text(store, profile)
    floor = profile.get("minimum_salary")
    drafts = store.list_drafts_by_status("queued")
    stats = {"queued": len(drafts), "drafted": 0, "skipped": 0}

    for draft in drafts:
        job = draft.get("jobs") or {}
        label = f"{job.get('company', '?')} — {job.get('title', '?')}"

        reason = salary_skip_reason(job, floor)
        if reason:
            print(f"[skip] {label} :: {reason}")
            stats["skipped"] += 1
            if not dry_run:
                store.update_draft(draft["id"], {"status": "skipped", "skip_reason": reason})
            continue

        field_values = map_profile_fields(profile)
        try:
            answers = draft_answers(job, profile)
        except Exception as exc:  # keep going on a single failure
            print(f"[error] {label} :: {exc}")
            if not dry_run:
                store.update_draft(draft["id"], {"status": "failed", "error": str(exc)[:500]})
            continue

        print(f"[draft] {label} :: {len(answers)} answers, "
              f"{len(field_values)} fields")
        stats["drafted"] += 1
        if dry_run:
            continue
        store.update_draft(draft["id"], {
            "status": "needs_review",
            "ats": job.get("ats", "") or draft.get("ats", ""),
            "apply_url": job.get("apply_url", "") or draft.get("apply_url", ""),
            "field_values": field_values,
            "drafted_answers": answers,
            "skip_reason": None,
            "error": None,
        })

    print(f"\n[Apply] queued {stats['queued']}; drafted {stats['drafted']}; "
          f"skipped {stats['skipped']}.")
    return stats


def main():
    process_queue(dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
