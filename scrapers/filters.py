"""Shared filters applied across all scrapers.

Keeps role/location/company/seniority logic in one place so the four
scrapers stay thin.
"""

import hashlib
import re

from config import (
    SKIP_SENIORITY,
    LOCATION_ALLOW,
    ALLOW_REMOTE,
    COMPANY_ALLOWLIST,
    ROLE_TIERS,
    EXCLUDE_KEYWORDS,
    INTERNSHIP_KEYWORDS,
)

NON_US_KEYWORDS = [
    "europe", "emea", "apac", "latam", "asia", "apj",
    "dach", "nordics", "benelux", "mena", "anz",
    "uk", "u.k.", "united kingdom", "london", "berlin",
    "paris", "amsterdam", "dublin", "singapore", "tokyo",
    "sydney", "australia", "canada", "india", "brazil",
    "mexico", "latin america", "middle east", "africa",
    "germany", "france", "spain", "italy", "japan",
    "korea", "china", "hong kong", "taiwan",
]


def stable_job_hash(value):
    """Deterministic short hash for building cross-run-stable job IDs.

    Python's builtin hash() is per-process randomized (PYTHONHASHSEED), so
    using it for *persisted* job IDs silently breaks seen-job dedup across
    runs — the same URL hashes differently every process. This is stable.
    """
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:16]


def _normalize_company(name):
    if not name:
        return ""
    s = name.lower()
    s = re.sub(r"[\.,&']", " ", s)
    s = re.sub(r"\b(inc|llc|corp|co|ltd|the)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Each entry is the token set of one allowlisted company name. A job's
# employer matches if some entry is a subset of the employer's tokens —
# so "Disney" matches "The Walt Disney Company" and "NBCUniversal"
# matches "NBCUniversal Media, LLC", but "Block" won't match "blocking".
_ALLOWED_COMPANY_TOKEN_SETS = [
    frozenset(_normalize_company(name).split())
    for industry_names in COMPANY_ALLOWLIST.values()
    for name in industry_names
]
_ALLOWED_COMPANY_TOKEN_SETS = [s for s in _ALLOWED_COMPANY_TOKEN_SETS if s]

_ALLOWED_LOCATION_TOKENS = [
    token
    for tokens in LOCATION_ALLOW.values()
    for token in tokens
]


# Titles matching these always pass the seniority filter — needed because
# "Chief of Staff" would otherwise be caught by the "staff" exclusion.
SENIORITY_BYPASS = ["chief of staff"]

FIT_BUCKET_LABELS = {
    "strong": "Strong matches",
    "possible": "Possible matches",
    "unknown": "Experience unclear",
}

POSITIVE_EXPERIENCE_PATTERNS = [
    re.compile(r"\b0\s*(?:-|to)\s*1\s+(?:year|years|yr|yrs)\b"),
    re.compile(r"\b1\+?\s+(?:year|years|yr|yrs)\b"),
    re.compile(r"\bone\s+(?:year|yr)\b"),
]

POSITIVE_EXPERIENCE_TEXT = [
    "new graduate",
    "recent graduate",
    "new grad",
    "early career",
    "entry level",
    "entry-level",
    "no experience required",
]

NEGATIVE_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:minimum of |at least |requires? )?([2-9]|[1-9][0-9])\+?\s+"
    r"(?:year|years|yr|yrs)\b"
)

NEGATIVE_SENIORITY_TEXT = [
    "senior-level",
    "senior level",
    "manager-level",
    "manager level",
    "director-level",
    "director level",
    "management experience",
    "people management",
    "team leadership experience",
]

SPONSOR_BLOCK_TEXT = [
    "will not sponsor",
    "does not sponsor",
    "do not sponsor",
    "cannot sponsor",
    "unable to sponsor",
    "no visa sponsorship",
    "not offer sponsorship",
    "without sponsorship",
    "now or in the future",
    "not able to provide sponsorship",
]

WORK_AUTH_BLOCK_TEXT = [
    "us citizen",
    "u.s. citizen",
    "u.s. citizenship",
    "us citizenship",
    "must be a citizen",
    "security clearance",
    "active clearance",
    "secret clearance",
    "top secret",
    "ts/sci",
    "itar",
    "export control",
    "export-controlled",
    "u.s. person",
    "us person",
]

SPONSOR_POSITIVE_TEXT = [
    "stem opt",
    "visa sponsorship available",
    "sponsorship available",
    "will sponsor",
    "we sponsor",
]


def is_excluded_seniority(title):
    t = (title or "").lower()
    if any(b in t for b in SENIORITY_BYPASS):
        return False
    return any(s in t for s in SKIP_SENIORITY)


def is_internship(title):
    t = (title or "").lower()
    return any(kw in t for kw in INTERNSHIP_KEYWORDS)


def is_non_us(text):
    t = (text or "").lower()
    return any(r in t for r in NON_US_KEYWORDS)


def is_allowed_location(location_blob, title=""):
    """True if location matches an allowed metro, or is remote (when allowed)."""
    blob = ((location_blob or "") + " " + (title or "")).lower()
    if ALLOW_REMOTE and "remote" in blob:
        return True
    return any(tok in blob for tok in _ALLOWED_LOCATION_TOKENS)


def is_allowed_company(employer_name):
    employer_tokens = set(_normalize_company(employer_name).split())
    if not employer_tokens:
        return False
    return any(
        allowed.issubset(employer_tokens) for allowed in _ALLOWED_COMPANY_TOKEN_SETS
    )


def role_tier(title):
    """Return the priority tier (1=highest) a title falls into, or None.

    Tiers are checked in order, so a title matching keywords in multiple
    tiers is assigned the highest-priority (lowest-numbered) one. None
    means the title matched no tier and should be excluded entirely.
    """
    t = (title or "").lower()
    for tier in sorted(ROLE_TIERS):
        if any(kw in t for kw in ROLE_TIERS[tier]):
            return tier
    return None


def is_excluded_keyword(title):
    """True if the title contains a hard-exclusion keyword (engineering,
    etc.) — drops the job even if it matched a role tier."""
    t = (title or "").lower()
    return any(kw in t for kw in EXCLUDE_KEYWORDS)


def _normalize_text(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _has_positive_experience(text):
    t = (text or "").lower()
    return any(p.search(t) for p in POSITIVE_EXPERIENCE_PATTERNS) or any(
        phrase in t for phrase in POSITIVE_EXPERIENCE_TEXT
    )


def _has_negative_experience(text):
    t = (text or "").lower()
    if any(phrase in t for phrase in NEGATIVE_SENIORITY_TEXT):
        return True
    return any(int(match.group(1)) >= 2 for match in NEGATIVE_EXPERIENCE_PATTERN.finditer(t))


def sponsor_eligibility_metadata(text):
    """Return sponsor/work-auth eligibility metadata from posting text."""
    normalized = _normalize_text(text).lower()
    reasons = []
    if any(phrase in normalized for phrase in SPONSOR_BLOCK_TEXT):
        reasons.append("sponsorship blocked")
    if any(phrase in normalized for phrase in WORK_AUTH_BLOCK_TEXT):
        reasons.append("citizenship/clearance restriction")
    if reasons:
        return {"sponsor_eligible": False, "sponsor_reasons": reasons}
    positive = [
        "OPT/STEM OPT friendly"
        for phrase in SPONSOR_POSITIVE_TEXT
        if phrase in normalized
    ]
    return {
        "sponsor_eligible": True,
        "sponsor_reasons": positive[:1],
    }


def fit_metadata(title, description=""):
    """Return permissive fit scoring metadata for a title + optional body text."""
    tier = role_tier(title)
    text = _normalize_text(description)
    positive_desc = _has_positive_experience(text)
    negative_desc = _has_negative_experience(text)

    reasons = []
    if tier == 1:
        reasons.append("new grad title")
    elif tier == 2:
        reasons.append("entry-level ops title")
    elif tier == 3:
        reasons.append("ops/strategy title")

    if positive_desc:
        reasons.append("0-1 years mentioned")
    if negative_desc:
        reasons.append("2+ years mentioned")

    early_title = tier in (1, 2)
    if negative_desc and not early_title and not positive_desc:
        return {
            "fit_bucket": "reject",
            "fit_reasons": reasons or ["experience too senior"],
            "job_description": text,
        }
    if negative_desc and early_title:
        return {
            "fit_bucket": "possible",
            "fit_reasons": reasons,
            "job_description": text,
        }
    if tier in (1, 2) or positive_desc:
        return {
            "fit_bucket": "strong",
            "fit_reasons": reasons,
            "job_description": text,
        }
    return {
        "fit_bucket": "unknown",
        "fit_reasons": reasons + ["experience unknown"],
        "job_description": text,
    }


def add_fit_metadata(job, description=None):
    """Attach fit_bucket / fit_reasons to a normalized job dict in place."""
    text = job.get("job_description", "") if description is None else description
    metadata = fit_metadata(job.get("job_title", ""), text)
    metadata.update(sponsor_eligibility_metadata(text))
    job.update(metadata)
    return job


def is_role_match(title):
    """True if title falls into one of the configured role tiers.

    Used by the watchlist scrapers, which fetch every job from a company's
    own board and need to filter title-side. Discovery scrapers also apply
    this now so that off-tier roles are excluded even when the aggregator
    search returns adjacent titles.
    """
    return role_tier(title) is not None


def passes_discovery(title, location_blob, employer_name, description=""):
    """Filter for the aggregator discovery path (VC portfolios + YC + Wellfound).

    Drops the company allowlist — the point of discovery is to surface new
    companies. Role-keyword check is unnecessary because the aggregator
    search already filtered by query.

    Note: non-US check is title-only. A location string like "SF, NY, or
    Remote within US/Canada" mentions "canada" but is still a US-friendly
    role — the location allowlist below already requires a US metro or
    remote anyway.
    """
    if not is_role_match(title):
        return False
    if is_excluded_keyword(title):
        return False
    if is_internship(title):
        return False
    if is_excluded_seniority(title):
        return False
    if is_non_us(title):
        return False
    if not is_allowed_location(location_blob, title):
        return False
    if not sponsor_eligibility_metadata(description).get("sponsor_eligible"):
        return False
    return fit_metadata(title, description).get("fit_bucket") != "reject"


def passes_watchlist(title, location_blob, employer_name, description=""):
    """Filter for the per-company watchlist path (Greenhouse, Lever, etc.).

    Skips the company allowlist (the scraper is already pinned to an
    allowlisted company by virtue of which board it hit) but adds a
    title-side role-keyword check, since these boards return all jobs.
    """
    if not is_role_match(title):
        return False
    if is_excluded_keyword(title):
        return False
    if is_internship(title):
        return False
    if is_excluded_seniority(title):
        return False
    if is_non_us(title):
        return False
    if not is_allowed_location(location_blob, title):
        return False
    if not sponsor_eligibility_metadata(description).get("sponsor_eligible"):
        return False
    return fit_metadata(title, description).get("fit_bucket") != "reject"
