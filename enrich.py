"""Job enrichment — the "shortlist then deepen" pass.

WHY THIS EXISTS
---------------
The scrapers source a lot of jobs but shallowly. Getro/Consider (the dominant
boards) carry only title + company + location — no description. And the
scrape-time AI ranker (ai_ranker.py) only scores ~100 jobs/run and never covers
the backlog. Net result observed in prod: ~87% of jobs had NO description and
~93% had NO AI summary/score, so ranking was blunt (title keywords) and the
dashboard detail panel showed raw scrape text or nothing.

WHAT IT DOES
------------
For a capped shortlist of the highest-scoring *visible* jobs that haven't been
enriched yet, it:
  Stage A — fetches the real job description by following apply_url to the ATS
            behind it (Greenhouse/Lever/Ashby JSON APIs we already speak, HTML
            fallback otherwise).
  Stage B — one Claude Haiku call writes a clean one-line summary + a fit score
            PERSONALIZED to the user's résumé and applied/dismissed history.
It writes both back to the job row (storage.update_job_enrichment). Migration 017
stops the next nightly scrape from wiping these fields.

HOW TO RUN
----------
    python enrich.py               # enrich the default shortlist
    python enrich.py --dry-run     # fetch + summarize a few, print, write nothing
    python enrich.py --limit 50    # cap this run

Scheduled as the `enrich` mode in .github/workflows/scrape.yml (daily, after the
scrapes). Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY.
Optional: ENRICH_MODEL (default claude-haiku-4-5), ENRICH_LIMIT (default 300),
ENRICH_MIN_SCORE (default 55).

HOW TO EXTEND (notes for a future session)
------------------------------------------
- Description coverage: `fetch_description` handles Greenhouse/Lever/Ashby via
  their APIs + a generic HTML fallback. Workday and other SPA/company pages fall
  through to the HTML fallback, which is weak for JS-rendered pages — a future
  improvement is a per-ATS fetcher (or a headless render) for those.
- Ranking authority: this pass writes ai_* and supersedes ai_ranker for display.
  If you want it to be the ONLY ranker, set AI_RANKING_ENABLED=false so the
  scrape-time OpenAI pass stops (avoids double spend / conflicting scores).
- The frontend sorts by ai_fit_score when present (jobs-dashboard.tsx).
"""

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

from storage import SupabaseJobStore, clean_text
import ai_ranker  # reuse _load_feedback_examples (applied/dismissed history)

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
DESC_CHARS = 2000  # how much cleaned description we store / feed the model


def _model():
    return os.getenv("ENRICH_MODEL") or os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL


def _limit():
    try:
        return max(1, int(os.getenv("ENRICH_LIMIT", "300")))
    except ValueError:
        return 300


def _min_score():
    try:
        return int(os.getenv("ENRICH_MIN_SCORE", "55"))
    except ValueError:
        return 55


# --- Stage A: fetch the real description ------------------------------------


def _http_get(url, as_json=False):
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json() if as_json else resp.text


def _from_greenhouse(url):
    # apply_url like https://boards.greenhouse.io/<slug>/jobs/<id> ->
    # boards-api.greenhouse.io/v1/boards/<slug>/jobs/<id> returns {content: HTML}.
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?#]+)/jobs/(\d+)", url)
    if not m:
        return ""
    slug, jid = m.group(1), m.group(2)
    data = _http_get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{jid}", as_json=True)
    return clean_text(data.get("content", ""))


def _from_lever(url):
    # apply_url like https://jobs.lever.co/<slug>/<uuid> ->
    # api.lever.co/v0/postings/<slug>/<uuid> returns descriptionPlain/description.
    m = re.search(r"lever\.co/([^/]+)/([^/?#]+)", url)
    if not m:
        return ""
    slug, pid = m.group(1), m.group(2)
    data = _http_get(f"https://api.lever.co/v0/postings/{slug}/{pid}", as_json=True)
    if isinstance(data, list):  # some endpoints return a list
        data = data[0] if data else {}
    text = data.get("descriptionPlain") or data.get("description") or ""
    # append the posting's list sections (responsibilities/requirements) if present
    for lst in data.get("lists") or []:
        text += "\n" + (lst.get("text") or "") + " " + clean_text(lst.get("content", ""))
    return clean_text(text)


def _from_ashby(url):
    # apply_url like https://jobs.ashbyhq.com/<slug>/<uuid>. The posting-api
    # returns the whole board; find our posting by id.
    m = re.search(r"ashbyhq\.com/([^/?#]+)/([^/?#]+)", url)
    if not m:
        return ""
    slug, pid = m.group(1), m.group(2)
    data = _http_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", as_json=True)
    for job in data.get("jobs", []):
        if job.get("id") == pid or pid in (job.get("jobUrl", "") or ""):
            return clean_text(job.get("descriptionPlain") or job.get("descriptionHtml") or "")
    return ""


def _from_html(url):
    # Generic fallback: strip a page down to readable text. Weak for JS-rendered
    # SPAs (Workday etc.) — see "HOW TO EXTEND" in the module docstring.
    html = _http_get(url)
    html = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html)
    return clean_text(html)


def _sanitize(text):
    """Strip NUL and other C0 control chars (keep tab/newline). Postgres text
    columns reject \\u0000, and scraped HTML occasionally carries control bytes —
    an un-sanitized description crashed the whole run (Supabase error 22P05)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text or "")


def fetch_description(apply_url):
    """Best-effort real description for a job, following its apply_url."""
    if not apply_url:
        return ""
    try:
        low = apply_url.lower()
        if "greenhouse.io" in low:
            text = _from_greenhouse(apply_url)
        elif "lever.co" in low:
            text = _from_lever(apply_url)
        elif "ashbyhq.com" in low:
            text = _from_ashby(apply_url)
        else:
            text = _from_html(apply_url)
        return _sanitize(text)[:DESC_CHARS]
    except Exception as exc:
        print(f"  [desc] fetch failed for {apply_url[:60]}: {exc}")
        return ""


# --- Stage B: AI summary + personalized fit score ---------------------------

ENRICH_SCHEMA_HINT = (
    '{"summary": string (one clear sentence, no fluff), '
    '"fit_score": int 0-100, "company_score": int 0-100, '
    '"seniority_level": one of ["entry","mid","senior"], '
    '"reject_reasons": [string], "labels": [string]}'
)


def _candidate_block(resume_text, applied, dismissed):
    applied_block = "\n".join("  - " + a for a in applied[:20]) or "  (none yet)"
    dismissed_block = "\n".join("  - " + d for d in dismissed[:20]) or "  (none yet)"
    resume = (resume_text or "").strip()
    block = (
        "Candidate targets US (or US-remote) roles at venture-backed startups. "
        "Priority order: (1) operations/strategy/chief-of-staff, "
        "(2) business development/partnerships/sales, (3) other early-career.\n"
        "APPLIED TO (wants more like these):\n" + applied_block + "\n"
        "DISMISSED/REJECTED (avoid):\n" + dismissed_block
    )
    if resume:
        block += "\n\nCandidate résumé:\n" + resume[:3500]
    return block


def enrich_job(job, candidate_block):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")
    system = (
        "You screen a single job for the candidate below and return JSON only, "
        "matching: " + ENRICH_SCHEMA_HINT + ".\n"
        "- summary: one plain, specific sentence describing the role (what they'd "
        "do + notable context). No marketing language, no 'This role...'.\n"
        "- fit_score: overall desirability for THIS candidate, weighting role-type "
        "priority, attainability (entry/early-career reachable; 5+ yrs or clear "
        "management -> low), and resemblance to APPLIED vs DISMISSED.\n"
        "- company_score: company quality/desirability.\n"
        "- reject_reasons: brief disqualifiers if any (e.g. 'senior', 'commodity "
        "cold-call SDR', 'not US').\n"
        "- labels: a few short tags.\n"
        + candidate_block
    )
    user = json.dumps({
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location_text", ""),
        "description": (job.get("description_excerpt") or "")[:DESC_CHARS],
    })
    resp = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": _model(), "max_tokens": 500, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=60,
    )
    resp.raise_for_status()
    text = "".join(
        b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text"
    )
    return _extract_json(text)


def _extract_json(text):
    """Parse a JSON object out of a model reply. The model sometimes wraps it in
    ``` fences or adds a trailing sentence (which trips json.loads with 'Extra
    data'), so grab the first {...} block."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip()).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0) if match else text)


def _int0100(value):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


# --- Orchestration ----------------------------------------------------------


def process(dry_run=False, limit=None):
    store = None if dry_run else SupabaseJobStore()
    read_store = store or SupabaseJobStore()

    profile = read_store.get_applicant_profile() or {}
    session = requests.Session()
    applied, dismissed = ai_ranker._load_feedback_examples(session)
    candidate_block = _candidate_block(profile.get("resume_text"), applied, dismissed)

    jobs = read_store.list_jobs_needing_enrichment(limit=limit or _limit(), min_score=_min_score())
    run_id = store.create_run("enrich") if store else None
    stats = {"shortlist": len(jobs), "described": 0, "enriched": 0, "errors": 0}
    print(f"[Enrich] shortlist of {len(jobs)} job(s) (min_score={_min_score()})")

    try:
        for job in jobs:
            label = f"{job.get('company', '?')} — {job.get('title', '?')}"
            fields = {}

            # Stage A: fetch a description if we don't already have one.
            if not (job.get("description_excerpt") or "").strip():
                desc = fetch_description(job.get("apply_url"))
                if desc:
                    job["description_excerpt"] = desc
                    fields["description_excerpt"] = desc
                    stats["described"] += 1

            # Stage B: AI summary + personalized scores.
            try:
                result = enrich_job(job, candidate_block)
            except Exception as exc:
                stats["errors"] += 1
                print(f"  [ai] {label}: {exc}")
                continue

            fields.update({
                "ai_summary": _sanitize(str(result.get("summary") or ""))[:500],
                "ai_fit_score": _int0100(result.get("fit_score")),
                "ai_company_score": _int0100(result.get("company_score")),
                "seniority_level": str(result.get("seniority_level") or "")[:40],
                "ai_reject_reasons": [str(r)[:120] for r in (result.get("reject_reasons") or [])][:8],
                "ai_labels": [str(l)[:60] for l in (result.get("labels") or [])][:10],
                "ranking_version": "enriched-v1",
            })
            # Write per-job inside its own guard: a single failed PATCH (bad
            # data, transient Supabase error) should skip that job, not abort the
            # whole nightly run.
            if not dry_run:
                try:
                    store.update_job_enrichment(job["job_id"], fields)
                except Exception as exc:
                    stats["errors"] += 1
                    print(f"  [write] {label}: {exc}")
                    continue
            stats["enriched"] += 1
            print(f"  [{fields['ai_fit_score']}] {label} :: {fields['ai_summary'][:70]}")

        if store:
            store.finish_run(run_id, "success", total_found=stats["shortlist"],
                             total_written=stats["enriched"], total_new=stats["described"],
                             counts=stats)
        print(f"\n[Enrich] described {stats['described']}; enriched {stats['enriched']}; "
              f"errors {stats['errors']}.")
        return stats
    except Exception as exc:
        if store and run_id:
            store.finish_run(run_id, "failed", counts=stats, error=str(exc))
        raise


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        try:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        except (ValueError, IndexError):
            pass
    process(dry_run=dry_run, limit=limit)


if __name__ == "__main__":
    main()
