"""Shared filters applied across all scrapers.

Keeps role/location/company/seniority logic in one place so the four
scrapers stay thin.
"""

import re

from config import (
    SKIP_SENIORITY,
    LOCATION_ALLOW,
    ALLOW_REMOTE,
    COMPANY_ALLOWLIST,
    ROLE_QUERIES,
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


def is_excluded_seniority(title):
    t = (title or "").lower()
    if any(b in t for b in SENIORITY_BYPASS):
        return False
    return any(s in t for s in SKIP_SENIORITY)


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


def is_role_match(title):
    """True if title contains one of the configured role keywords.

    Used by the watchlist scrapers, which fetch every job from a company's
    own board and need to filter title-side. Discovery scrapers don't need
    this because they pass ROLE_QUERIES as search queries to the aggregator.
    """
    t = (title or "").lower()
    return any(q in t for q in ROLE_QUERIES)


def passes_discovery(title, location_blob, employer_name):
    """Filter for the aggregator discovery path (VC portfolios + YC + Wellfound).

    Drops the company allowlist — the point of discovery is to surface new
    companies. Role-keyword check is unnecessary because the aggregator
    search already filtered by query.

    Note: non-US check is title-only. A location string like "SF, NY, or
    Remote within US/Canada" mentions "canada" but is still a US-friendly
    role — the location allowlist below already requires a US metro or
    remote anyway.
    """
    if is_excluded_seniority(title):
        return False
    if is_non_us(title):
        return False
    if not is_allowed_location(location_blob, title):
        return False
    return True


def passes_watchlist(title, location_blob, employer_name):
    """Filter for the per-company watchlist path (Greenhouse, Lever, etc.).

    Skips the company allowlist (the scraper is already pinned to an
    allowlisted company by virtue of which board it hit) but adds a
    title-side role-keyword check, since these boards return all jobs.
    """
    if not is_role_match(title):
        return False
    if is_excluded_seniority(title):
        return False
    if is_non_us(title):
        return False
    if not is_allowed_location(location_blob, title):
        return False
    return True
