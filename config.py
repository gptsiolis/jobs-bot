import os
from dotenv import load_dotenv

load_dotenv()

# ── Email settings ──────────────────────────────────────────────
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")

# ── Getro-powered VC portfolio job boards ──────────────────────
# Public Next.js boards with embedded JSON — simple HTTP scraping.
GETRO_BOARDS = {
    # Tier 1
    "General Catalyst": "https://jobs.generalcatalyst.com",
    "Accel": "https://jobs.accel.com",
    "Khosla Ventures": "https://jobs.khoslaventures.com",
    "Thrive Capital": "https://jobs.thrivecap.com",
    "Craft Ventures": "https://jobs.craftventures.com",
    "Insight Partners": "https://jobs.insightpartners.com",
    # Tier 2
    "Redpoint Ventures": "https://careers.redpoint.com",
    "Menlo Ventures": "https://jobs.menlovc.com",
    "Emergence Capital": "https://talent.emcap.com",
    "Sapphire Ventures": "https://jobs.sapphireventures.com",
    "Canaan Partners": "https://careers.canaan.com",
    "Notable Capital": "https://jobs.notablecap.com",
    "Wing Venture Capital": "https://careers.wing.vc",
    "8VC": "https://jobs.8vc.com",
    "Lux Capital": "https://jobs.luxcapital.com",
    "Foundry Group": "https://jobs.foundry.vc",
    "True Ventures": "https://jobs.trueventures.com",
    "Scale Venture Partners": "https://jobs.scalevp.com",
    "Madrona Ventures": "https://jobs.madrona.com",
    "SignalFire": "https://jobs.signalfire.com",
    # Added from the catalogued-but-unwired set. URLs follow the standard
    # Getro jobs.<domain> pattern and are unverified — a wrong host just
    # yields zero jobs (scrape_board skips dead boards), no run failure.
    "Ribbit Capital": "https://jobs.ribbitcap.com",
    "Tiger Global": "https://jobs.tigerglobal.com",
    "Coatue": "https://jobs.coatue.com",
    "Altimeter Capital": "https://jobs.altimeter.com",
    "Greenoaks": "https://jobs.greenoaks.com",
    "Spark Capital": "https://jobs.sparkcapital.com",
    "Flybridge": "https://jobs.flybridge.com",
    "Boldstart Ventures": "https://jobs.boldstart.vc",
    "Work-Bench": "https://jobs.work-bench.com",
    "Addition": "https://jobs.addition.com",
}

# ── Consider-powered VC portfolio job boards ───────────────────
# Client-side rendered — requires Playwright headless browser.
CONSIDER_BOARDS = {
    # Tier 1
    "Sequoia Capital": "https://jobs.sequoiacap.com",
    "a16z": "https://jobs.a16z.com",
    "Bessemer": "https://jobs.bvp.com",
    "Greylock": "https://jobs.greylock.com",
    "First Round Capital": "https://jobs.firstround.com",
    "Lightspeed": "https://jobs.lsvp.com",
    "Kleiner Perkins": "https://jobs.kleinerperkins.com",
    "Union Square Ventures": "https://jobs.usv.com",
    # Tier 2
    "Battery Ventures": "https://jobs.battery.com",
    "NEA": "https://careers.nea.com",
    "Norwest": "https://careers.nvp.com",
    "Felicis Ventures": "https://jobs.felicis.com",
    "Forerunner Ventures": "https://jobs.forerunnerventures.com",
    "Bain Capital Ventures": "https://jobs.baincapitalventures.com",
    "Initialized Capital": "https://jobs.initialized.com",
    "IVP": "https://careers.ivp.com",
    "Amplify Partners": "https://talent.amplifypartners.com",
    "QED Investors": "https://careers.qedinvestors.com",
    "Costanoa Ventures": "https://jobs.costanoa.vc",
    "GV": "https://jobs.gv.com",
    # Added from the catalogued-but-unwired set. Unverified URLs (standard
    # Consider pattern); scrape_board catches a failed page load and skips.
    "ICONIQ Growth": "https://jobs.iconiqcapital.com",
    "Founders Fund": "https://jobs.foundersfund.com",
    "Atlas Venture": "https://jobs.atlasventure.com",
    "Bowery Capital": "https://jobs.bowerycap.com",
    "Primary Venture Partners": "https://jobs.primary.vc",
    "Homebrew": "https://jobs.homebrew.co",
}

# ── Role tiers ──────────────────────────────────────────────────
# A job's title must match a keyword in one of these tiers or it is
# excluded entirely. Tier number drives digest grouping/priority
# (1 = highest). Precedence is top-down: tier 1 keywords are checked
# first, so e.g. "New Grad Business Operations" matches tier 1.
_DEFAULT_ROLE_TIERS = {
    1: [  # PRIORITY — operations / strategy / chief of staff (generalist startup roles)
        "chief of staff",
        "founder's associate",
        "founders associate",
        "founder associate",
        "business operations",
        "business operations associate",
        "business operations analyst",
        "business operations coordinator",
        "operations associate",
        "operations analyst",
        "operations coordinator",
        "strategy and operations",
        "strategy & operations",
        "strategy operations",
        "strategy associate",
        "strategy analyst",
        "revenue operations",
        "revenue operations associate",
        "revenue operations analyst",
        "special projects associate",
        "special projects",
        "program associate",
        "program coordinator",
        "operations",
        "strategy",
    ],
    2: [  # Early career / new grad signals (function-agnostic)
        "new grad",
        "new graduate",
        "recent graduate",
        "early career",
        "entry level",
        "entry-level",
        "rotational",
        "graduate program",
        "analyst program",
        "associate program",
    ],
    3: [  # Business development / partnerships / growth / sales / investment
        "business development associate",
        "business development analyst",
        "business development representative",
        "sales development representative",
        "account executive",
        "sales associate",
        "sales representative",
        "customer success associate",
        "partnerships associate",
        "partnerships analyst",
        "partner development associate",
        "growth associate",
        "growth analyst",
        "investment analyst",
        "investment associate",
        "acquisitions analyst",
        "acquisitions associate",
        "acquisitions - analyst",
        "asset management analyst",
        "asset management associate",
        "business development",
        "partnerships",
        "growth",
    ],
}

def _load_role_tiers_from_db():
    """Load role keywords from Supabase when running scrapers.

    Gated behind LOAD_ROLE_PREFS=1 (set in the scraper workflow) so local dev
    and tests stay on the static defaults. Falls back to the defaults on any
    error or if the table doesn't cover all three tiers, so a bad edit can't
    silently break a run.
    """
    if os.environ.get("LOAD_ROLE_PREFS") != "1":
        return None
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    family_to_tier = {
        "operations_strategy": 1,
        "early_career": 2,
        "business_development": 3,
    }
    try:
        import requests

        resp = requests.get(
            url + "/rest/v1/role_preferences?select=keyword,family",
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:  # network/parse error -> use defaults
        print(f"[config] Could not load role preferences ({exc}); using defaults.")
        return None

    tiers = {1: [], 2: [], 3: []}
    for row in rows or []:
        tier = family_to_tier.get(row.get("family"))
        keyword = (row.get("keyword") or "").strip().lower()
        if tier and keyword:
            tiers[tier].append(keyword)
    if all(tiers[t] for t in (1, 2, 3)):
        print(f"[config] Loaded {sum(len(v) for v in tiers.values())} role keywords from Supabase.")
        return tiers
    return None


# Editable role keywords live in the Supabase role_preferences table; fall back
# to the static defaults above for local dev/tests or if the table is empty.
ROLE_TIERS = _load_role_tiers_from_db() or _DEFAULT_ROLE_TIERS

# Flat list of all role keywords. Used verbatim as discovery search
# queries (aggregators / Workday) and for title-side matching. Derived
# from ROLE_TIERS.
ROLE_QUERIES = [kw for kws in ROLE_TIERS.values() for kw in kws]

# ── Seniority filter ─────────────────────────────────────────
# Skip roles with these keywords in the title. "lead" is excluded per
# request (no Lead-titled roles), alongside the senior/exec bands.
SKIP_SENIORITY = [
    "senior", "sr.", "staff", "principal", "director",
    "vp", "vice president", "head of", "lead", "manager", "mgr",
]

# ── Hard exclusions ─────────────────────────────────────────
# Any of these substrings in the title drops the job outright, even if
# it also matched a role tier (e.g. "Engineering Operations", "Sales
# Engineer"). Keeps engineering/technical/specialist functions out.
EXCLUDE_KEYWORDS = [
    "engineer", "engineering", "developer", "software",
    "devops", "site reliability", "data scientist",
    "machine learning", "designer", "architect",
    "scientist", "qa ", "sdet", "warehouse", "fulfillment",
    "logistics", "supply chain", "inventory", "distribution",
    "fleet", "driver", "facilities", "manufacturing",
    "coordinator", "people", "human resources", "hr ",
    "talent", "recruiter", "recruiting",
]

# Full-time search only. These title terms are excluded even if a posting
# otherwise has an early-career signal.
INTERNSHIP_KEYWORDS = [
    "intern", "internship", "co-op", "coop", "summer analyst",
    "campus ambassador",
]

# ── Location allowlist ──────────────────────────────────────
# Job must mention a token from one of these metros (or be remote, if
# ALLOW_REMOTE = True). Add aliases liberally — matching is substring-based
# on the lowercased location/title blob.
LOCATION_ALLOW = {
    # NOTE: bare state abbreviations ("la,", "ny,") are intentionally NOT used —
    # they false-match other cities in those states (Lake Charles, LA; Buffalo,
    # NY). Real LA/NYC postings are caught by the city/neighborhood tokens below.
    "Los Angeles": [
        "los angeles", "la, ca", "santa monica", "venice ca",
        "culver city", "west hollywood",
    ],
    "New York": [
        "new york", "nyc", "manhattan", "brooklyn",
    ],
    "San Francisco": [
        "san francisco", "sf,", " sf ", "sf bay", "bay area", "oakland",
        "palo alto", "mountain view", "menlo park",
    ],
    "Miami": [
        "miami", "miami beach", "coral gables",
    ],
    "Austin": [
        "austin",
    ],
    "Washington DC": [
        "washington, dc", "washington, d.c.", "washington dc",
        "arlington, va", "alexandria, va",
    ],
    "Chicago": [
        "chicago",
    ],
    "Toronto": [
        "toronto", "toronto, on", "toronto, ontario", "greater toronto",
    ],
}

# If True, remote roles pass the location filter regardless of metro.
ALLOW_REMOTE = True

# ── Company allowlist & per-company ATS boards ──────────────────
# Both are sourced from the curated registry in data/company_registry.json
# (see company_registry.py). COMPANY_ALLOWLIST is {sector: [names]};
# COMPANY_BOARDS is {name: ats config} for enabled companies that have a
# verified, sponsor-friendly ATS slug. Edit the registry JSON, not this file,
# to change which companies are tracked.
#
# ATS endpoints used to verify slugs:
#   - Greenhouse: https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
#   - Lever:      https://api.lever.co/v0/postings/<slug>?mode=json
#   - Ashby:      https://api.ashbyhq.com/posting-api/job-board/<slug>
#
# Companies on gated/JS-rendered platforms (June 2026 investigation). These have
# no clean public JSON API, so they need the headless-browser path.
#   - Circle, eBay: Phenom People -> COVERED via scrapers/phenom.py (browser).
#     The phenom adapter captures the page's own job API responses; it's the
#     reusable "browser robot" — Gem/SuccessFactors below can follow the same
#     pattern (load page, snoop the jobs XHR, normalize).
#   - Function Health: Gem (jobs.gem.com/function-health) — JS SPA, API 403.
#   - Paramount: SuccessFactors — OData, tenant-gated.
#   - Klarna: Deel — no documented public board API.
#   - Coinbase: Cloudflare-protected custom careers page.
#   - Kajabi: JS-rendered, ATS not identified.
#   - Republic: custom careers (republic.com/careers), ATS not exposed.
#   - InsideTracker: email-only applications (no ATS).
# Low-priority (LatAm, little/no US early-career presence — US-only filter would
# drop nearly everything): Stori (Greenhouse, regional slugs), Kushki (Workable,
# slug "kushki"), Pomelo (ATS unconfirmed). Wire on request.
# Covered this round: Arrived — Breezy HR adapter (scrapers/breezy.py).
from company_registry import company_allowlist, company_boards

COMPANY_ALLOWLIST = company_allowlist()
COMPANY_BOARDS = company_boards()
