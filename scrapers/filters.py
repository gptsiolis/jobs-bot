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

MIN_ANNUAL_SALARY = 70000
MIN_HOURLY_RATE = MIN_ANNUAL_SALARY / 2080

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

# Non-US countries/regions/cities for matching against a LOCATION string.
# Matched with word boundaries so "uk" can't hit "Milwaukee" and "india"
# can't hit "Indiana". Deliberately excludes US-ambiguous names (e.g.
# Georgia the country vs the US state).
NON_US_LOCATION_TOKENS = [
    "uk", "united kingdom", "england", "scotland", "wales", "ireland",
    "emea", "apac", "latam", "europe", "latin america", "middle east",
    "germany", "france", "spain", "portugal", "italy", "netherlands",
    "belgium", "sweden", "norway", "denmark", "finland", "switzerland",
    "austria", "poland", "czechia", "romania", "greece", "turkey",
    "russia", "ukraine", "india", "china", "japan", "south korea", "korea",
    "singapore", "taiwan", "hong kong", "thailand", "vietnam", "philippines",
    "indonesia", "malaysia", "australia", "new zealand", "canada", "mexico",
    "brazil", "argentina", "colombia", "chile", "peru", "israel",
    "united arab emirates", "uae", "saudi arabia", "qatar", "egypt",
    "nigeria", "kenya", "south africa", "morocco",
    "london", "manchester", "dublin", "berlin", "munich", "paris", "madrid",
    "barcelona", "lisbon", "rome", "milan", "amsterdam", "stockholm", "oslo",
    "copenhagen", "helsinki", "zurich", "geneva", "vienna", "warsaw", "prague",
    "athens", "istanbul", "dubai", "abu dhabi", "tel aviv", "bangalore",
    "bengaluru", "mumbai", "new delhi", "delhi", "hyderabad", "pune", "chennai",
    "gurgaon", "beijing", "shanghai", "shenzhen", "tokyo", "osaka", "seoul",
    "taipei", "bangkok", "jakarta", "manila", "kuala lumpur", "ho chi minh",
    "hanoi", "sydney", "melbourne", "brisbane", "perth", "auckland", "toronto",
    "vancouver", "montreal", "ottawa", "calgary", "mexico city", "sao paulo",
    "rio de janeiro", "buenos aires", "bogota", "santiago", "lima", "lagos",
    "nairobi", "cairo", "johannesburg", "cape town",
]
_NON_US_LOCATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in NON_US_LOCATION_TOKENS) + r")\b"
)


def is_non_us_location(location):
    """True if a LOCATION string names a non-US country/region/city."""
    return bool(_NON_US_LOCATION_RE.search((location or "").lower()))


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

# 5+ years is out of range for an entry-level search. Matched separately from
# the 2+ "stretch" signal so these get rejected, not just down-ranked.
SENIOR_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:minimum of |at least |requires? )?([5-9]|[1-9][0-9])\+?\s+"
    r"(?:year|years|yr|yrs)\b"
)
SENIOR_EXPERIENCE_TEXT = [
    "senior-level", "director-level", "vp-level", "executive-level",
    "5+ years", "6+ years", "7+ years", "8+ years", "10+ years",
    # spelled-out forms the digit pattern misses
    "five years", "six years", "seven years", "eight years", "nine years",
    "ten years", "twelve years", "fifteen years",
    "five+ years", "five or more years", "minimum of five",
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

LOGISTICS_OPERATIONS_TEXT = [
    "warehouse",
    "fulfillment center",
    "distribution center",
    "logistics",
    "supply chain",
    "inventory control",
    "fleet operations",
    "delivery operations",
    "driver operations",
    "facilities operations",
    "manufacturing operations",
    "production operations",
    "food operations",
]

ENTRY_LEVEL_TITLE_TEXT = [
    "associate",
    "analyst",
    "coordinator",
    "new grad",
    "entry level",
    "entry-level",
    "early career",
    "representative",
]

INVESTMENT_ROLE_TEXT = [
    "investment analyst",
    "investment associate",
    "acquisitions analyst",
    "acquisitions associate",
    "asset management analyst",
    "asset management associate",
    "portfolio analyst",
    "capital markets analyst",
]

ALLOWED_INVESTMENT_DOMAIN_TEXT = [
    "art",
    "auction",
    "auction house",
    "gallery",
    "collectible",
    "collectibles",
    "trading card",
    "sports card",
    "memorabilia",
    "sotheby",
    "christie",
    "crypto",
    "cryptocurrency",
    "digital asset",
    "digital assets",
    "blockchain",
    "web3",
    "defi",
    "token",
    "tokens",
    "nft",
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
    """True if location matches an allowed metro, or is remote (when allowed).

    A location that names a non-US country/region is rejected even when the
    posting is remote, so "Remote - Ireland" or "Sydney, Australia" don't slip
    through on the remote bypass.
    """
    location = (location_blob or "").lower()
    blob = location + " " + (title or "").lower()
    # An explicit allowed US metro anywhere wins, even if other (incl. non-US)
    # locations are also listed — "SF, NY, or Remote" is fine.
    if any(tok in blob for tok in _ALLOWED_LOCATION_TOKENS):
        return True
    # Otherwise allow remote only when it isn't pinned to a non-US locale.
    if ALLOW_REMOTE and "remote" in blob and not is_non_us_location(location):
        return True
    return False


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


def is_logistics_operations(title, description=""):
    blob = f"{title or ''} {description or ''}".lower()
    return any(phrase in blob for phrase in LOGISTICS_OPERATIONS_TEXT)

def is_disallowed_investment_role(title, description="", employer_name=""):
    blob = ((title or "") + " " + (description or "") + " " + (employer_name or "")).lower()
    if not any(phrase in blob for phrase in INVESTMENT_ROLE_TEXT):
        return False
    return not any(phrase in blob for phrase in ALLOWED_INVESTMENT_DOMAIN_TEXT)


def _normalize_text(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _money_to_number(raw, suffix=""):
    value = float((raw or "0").replace(",", ""))
    if suffix and suffix.lower() == "k":
        value *= 1000
    return value


def _range_max(first, first_suffix, second, second_suffix):
    first_value = _money_to_number(first, first_suffix)
    if not second:
        return first_value
    return max(first_value, _money_to_number(second, second_suffix or first_suffix))


def compensation_below_floor(text):
    """True when the posting explicitly advertises comp below our floor.

    Missing compensation is not a rejection signal. Low hourly/annual posted
    comp is.
    """
    normalized = _normalize_text(text).lower()
    hourly_pattern = re.compile(
        r"\$?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:-|to|–|—)?\s*"
        r"\$?\s*(\d{1,3}(?:\.\d{1,2})?)?\s*"
        r"(?:/ ?hour|/hr|per hour|hourly|an hour|hr\b)"
    )
    hourly_maxes = [
        _range_max(match.group(1), "", match.group(2), "")
        for match in hourly_pattern.finditer(normalized)
    ]
    if hourly_maxes and max(hourly_maxes) < MIN_HOURLY_RATE:
        return True

    annual_pattern = re.compile(
        r"\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3})\s*(k)?\s*"
        r"(?:-|to|–|—)?\s*\$?\s*"
        r"(\d{2,3}(?:,\d{3})+|\d{2,3})?\s*(k)?\s*"
        r"(?:per year|annually|annual|base salary|salary|/year|/yr)"
    )
    annual_maxes = [
        _range_max(match.group(1), match.group(2), match.group(3), match.group(4))
        for match in annual_pattern.finditer(normalized)
    ]
    if annual_maxes and max(annual_maxes) < MIN_ANNUAL_SALARY:
        return True
    return False


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


def _has_senior_experience(text):
    """True when the posting clearly requires 5+ years — out of range for an
    entry-level search, so rejected rather than just down-ranked."""
    t = (text or "").lower()
    if any(phrase in t for phrase in SENIOR_EXPERIENCE_TEXT):
        return True
    return any(int(match.group(1)) >= 5 for match in SENIOR_EXPERIENCE_PATTERN.finditer(t))


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


# Maps a matched role tier to a coarse role family. Used for prioritized
# ranking/visibility downstream (operations/strategy/chief-of-staff is the
# user's top target and is surfaced first).
ROLE_FAMILY_BY_TIER = {
    1: "operations_strategy",
    2: "early_career",
    3: "business_development",
}


def role_family(title):
    """Coarse role family for a title (or '' if it matches no tier)."""
    return ROLE_FAMILY_BY_TIER.get(role_tier(title), "")


def fit_metadata(title, description=""):
    """Return permissive fit scoring metadata for a title + optional body text."""
    tier = role_tier(title)
    family = ROLE_FAMILY_BY_TIER.get(tier, "")
    text = _normalize_text(description)
    positive_desc = _has_positive_experience(text)
    negative_desc = _has_negative_experience(text)
    entry_level_title = any(phrase in (title or "").lower() for phrase in ENTRY_LEVEL_TITLE_TEXT)

    reasons = []
    if tier == 1:
        reasons.append("operations/strategy/chief-of-staff title")
    elif tier == 2:
        reasons.append("early-career title")
    elif tier == 3:
        reasons.append("business development/sales title")

    if positive_desc:
        reasons.append("0-1 years mentioned")
    if negative_desc:
        reasons.append("2+ years mentioned")
    if compensation_below_floor(text):
        reasons.append("compensation below floor")

    def _meta(bucket, extra=None):
        return {
            "fit_bucket": bucket,
            "fit_reasons": (reasons + (extra or [])) or ["experience too senior"],
            "job_description": text,
            "role_family": family,
        }

    if is_logistics_operations(title, text):
        return _meta("reject", ["warehouse/logistics operations"])
    if compensation_below_floor(text):
        return _meta("reject")
    if _has_senior_experience(text) and not positive_desc:
        return _meta("reject", ["requires 5+ years"])

    # An explicit entry-level title word (associate/analyst/coordinator/
    # representative) counts as early-career even on a tier-3 (BD/sales) role,
    # so those stay surfaced rather than being rejected/buried.
    early_title = tier in (1, 2) or entry_level_title
    broad_title = tier == 3
    if broad_title and not positive_desc and not entry_level_title:
        return _meta("reject", ["broad title without entry-level signal"])
    if negative_desc and not early_title and not positive_desc:
        return _meta("reject")
    if negative_desc and early_title:
        return _meta("possible")
    if tier in (1, 2) or positive_desc:
        return _meta("strong")
    if entry_level_title:
        return _meta("possible")
    return _meta("unknown", ["experience unknown"])


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
    if is_logistics_operations(title, description):
        return False
    if is_disallowed_investment_role(title, description, employer_name):
        return False
    if compensation_below_floor(description):
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


def match_jobs(normalized_jobs, passes):
    """Filter already-normalized job dicts and attach fit metadata to keepers.

    Shared by the per-company watchlist scrapers (and discovery scrapers),
    which all ran the identical normalize -> filter -> add_fit_metadata loop.
    `passes` is one of passes_watchlist / passes_discovery.
    """
    matched = []
    for normalized in normalized_jobs:
        location_blob = " ".join(normalized.get("locations") or [])
        description = normalized.get("job_description", "")
        if not passes(
            normalized.get("job_title", ""),
            location_blob,
            normalized.get("employer_name", ""),
            description,
        ):
            continue
        add_fit_metadata(normalized, description)
        matched.append(normalized)
    return matched


def match_watchlist_jobs(normalized_jobs):
    """match_jobs bound to the watchlist filter."""
    return match_jobs(normalized_jobs, passes_watchlist)


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
    if is_logistics_operations(title, description):
        return False
    if is_disallowed_investment_role(title, description, employer_name):
        return False
    if compensation_below_floor(description):
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
