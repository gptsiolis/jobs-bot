"""Resolve likely public ATS boards from a company name."""

import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 12


def _base_name(company_name):
    text = (company_name or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(
        r"\b(inc|llc|corp|corporation|company|co|ltd|limited|holdings|group|the)\b",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def slug_candidates(company_name):
    base = _base_name(company_name)
    if not base:
        return []

    compact = re.sub(r"[^a-z0-9]", "", base)
    hyphen = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    nospace = base.replace(" ", "")

    candidates = []
    for value in (compact, hyphen, nospace, base):
        slug = re.sub(r"\s+", "-", value.strip().lower())
        if slug and slug not in candidates:
            candidates.append(slug)
    return candidates[:6]


def _get_json(session, url):
    try:
        response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return None, str(exc)
    if response.status_code == 404:
        return None, "404"
    if not response.ok:
        return None, f"HTTP {response.status_code}"
    try:
        return response.json(), None
    except ValueError:
        return None, "non-JSON response"


def _probe_greenhouse(session, slug):
    data, error = _get_json(
        session,
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    )
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return {"ats": "greenhouse", "slug": slug}
    return None, error


def _probe_lever(session, slug):
    data, error = _get_json(session, f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if isinstance(data, list):
        return {"ats": "lever", "slug": slug}
    return None, error


def _probe_ashby(session, slug):
    data, error = _get_json(
        session,
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
    )
    if isinstance(data, dict) and isinstance(data.get("jobs") or data.get("jobPostings"), list):
        return {"ats": "ashby", "slug": slug}
    return None, error


def _probe_workable(session, slug):
    data, error = _get_json(
        session,
        f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true",
    )
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return {"ats": "workable", "slug": slug}
    return None, error


def _probe_smartrecruiters(session, slug):
    data, error = _get_json(
        session,
        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1&offset=0",
    )
    if isinstance(data, dict) and "content" in data:
        return {"ats": "smartrecruiters", "slug": slug}
    return None, error


def _probe_dayforce(session, slug):
    data, error = _get_json(
        session,
        f"https://www.dayforcehcm.com/api/{slug}/V1/JobFeeds?includeActivePostingOnly=true",
    )
    if isinstance(data, list):
        return {"ats": "dayforce", "company": slug}
    return None, error


PROBES = (
    _probe_greenhouse,
    _probe_lever,
    _probe_ashby,
    _probe_workable,
    _probe_smartrecruiters,
    _probe_dayforce,
)


def resolve_company_board(company_name, session=None):
    """Return an ATS config for company_name, or (None, reason)."""
    session = session or requests.Session()
    last_error = "no slug candidates"
    for slug in slug_candidates(company_name):
        for probe in PROBES:
            config, error = probe(session, slug)
            if config:
                return config, None
            if error:
                last_error = f"{probe.__name__.replace('_probe_', '')}:{slug}:{error}"
    return None, last_error
