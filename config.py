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
    "Los Angeles": [
        "los angeles", "la,", " la ", "la (", "santa monica", "venice ca",
        "culver city", "west hollywood", "hollywood",
    ],
    "New York": [
        "new york", "nyc", "ny,", " ny ", "manhattan", "brooklyn",
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
        "washington, dc", "washington, d.c.", "washington dc", " d.c.",
        " dc,", " dc ", "arlington, va", "alexandria, va",
    ],
    "Chicago": [
        "chicago",
    ],
}

# If True, remote roles pass the location filter regardless of metro.
ALLOW_REMOTE = True

# ── Company allowlist (manifest only) ───────────────────────
# Note: this list is NOT actively used by the current filters. It's a
# manifest of companies we care about — useful for our own reference and
# for figuring out what to wire up in COMPANY_BOARDS below. The actual
# watchlist scrape is driven by COMPANY_BOARDS, which only contains
# companies whose ATS slug we've verified.
#
# If we later want to filter discovery-mode aggregator results to only
# these names, filters.is_allowed_company is ready — just wire it in.
COMPANY_ALLOWLIST = {
    "media_entertainment": [
        "A24",
        "Agentio",
        "Christie's",
        "Discord",
        "Disney",
        "Disney+",
        "DraftKings",
        "Epic Games",
        "Fanatics",
        "FanDuel",
        "Kajabi",
        "NBCUniversal",
        "Peacock",
        "Netflix",
        "Paramount",
        "Passes",
        "Patreon",
        "Pinterest",
        "Reddit",
        "Roblox",
        "Sotheby's",
        "Spotify",
        "Spotter",
        "Substack",
        "Warner Bros. Discovery",
        "Whatnot",
    ],
    # Renamed from "stablecoins" — your list spans crypto, neobanks, brokerages,
    # corp cards, BNPL, and payments infra. Reorganize freely.
    "fintech_crypto": [
        "Affirm",
        "Alpaca",
        "Anchorage",
        "Arrived",
        "Betterment",
        "Block",
        "Square",
        "Cash App",
        "Blockchain.com",
        "Cadre",
        "Carta",
        "Chime",
        "Circle",
        "Coinbase",
        "Flex",
        "Gemini",
        "iCapital",
        "Jeeves",
        "Klarna",
        "Kraken",
        "Kushki",
        "Magic Eden",
        "Mercury",
        "MoonPay",
        "Novo",
        "OpenSea",
        "Pacaso",
        "Plaid",
        "Pomelo",
        "Public.com",
        "Ramp",
        "Republic",
        "Rho",
        "Robinhood",
        "Sardine",
        "SoFi",
        "Stori",
        "Stripe",
        "Wealthfront",
    ],
    "consumer_health": [
        "Alma",
        "Blueprint",
        "Carrot Fertility",
        "Eight Sleep",
        "Function Health",
        "Hims & Hers",
        "InsideTracker",
        "Levels Health",
        "Lifeforce",
        "Maven Clinic",
        "Midi Health",
        "Modern Health",
        "Neko Health",
        "Nudge",
        "Oura",
        "Papa",
        "Ro",
        "Roman",
        "Superpower",
        "Superpower Health",
        "Viome",
        "Whoop",
    ],
    # Doesn't cleanly fit the three above — mostly commerce/marketplaces
    # and real estate. Re-bucket as you see fit.
    "other": [
        "eBay",
        "Etsy",
        "Faire",
        "Flow",
        "StockX",
        "Pattern",
    ],
}

# ── Per-company ATS boards (watchlist mode) ─────────────────────
# For each allowlisted company we know the ATS slug for, hit their board
# directly. Slugs were verified once via _verify_*.py against:
#   - Greenhouse: https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
#   - Lever:      https://api.lever.co/v0/postings/<slug>?mode=json
#   - Ashby:      https://api.ashbyhq.com/posting-api/job-board/<slug>
#
# Companies absent from this map either don't expose an aggregator API
# (Workday/custom — needs per-company scraper) or used a slug we didn't try.
COMPANY_BOARDS = {
    # ── Greenhouse ──
    "Stripe":           {"ats": "greenhouse", "slug": "stripe"},
    "Discord":          {"ats": "greenhouse", "slug": "discord"},
    "Reddit":           {"ats": "greenhouse", "slug": "reddit"},
    "Pinterest":        {"ats": "greenhouse", "slug": "pinterest"},
    "Mercury":          {"ats": "greenhouse", "slug": "mercury"},
    "Carta":            {"ats": "greenhouse", "slug": "carta"},
    "Robinhood":        {"ats": "greenhouse", "slug": "robinhood"},
    "Affirm":           {"ats": "greenhouse", "slug": "affirm"},
    "Faire":            {"ats": "greenhouse", "slug": "faire"},
    "Roblox":           {"ats": "greenhouse", "slug": "roblox"},
    "Modern Health":    {"ats": "greenhouse", "slug": "modernhealth"},
    "Pacaso":           {"ats": "greenhouse", "slug": "pacaso"},
    "SoFi":             {"ats": "greenhouse", "slug": "sofi"},
    "Betterment":       {"ats": "greenhouse", "slug": "betterment"},
    "Alpaca":           {"ats": "greenhouse", "slug": "alpaca"},
    "Alma":             {"ats": "greenhouse", "slug": "alma"},
    "Oura":             {"ats": "greenhouse", "slug": "oura"},
    "Papa":             {"ats": "greenhouse", "slug": "papa"},
    "Maven Clinic":     {"ats": "greenhouse", "slug": "maven"},
    "Midi Health":      {"ats": "greenhouse", "slug": "midihealth"},
    "Carrot Fertility": {"ats": "greenhouse", "slug": "carrotfertility"},
    "iCapital":         {"ats": "greenhouse", "slug": "icapitalnetwork"},
    "Public.com":       {"ats": "greenhouse", "slug": "public"},
    "Chime":            {"ats": "greenhouse", "slug": "chime"},
    "Flex":             {"ats": "greenhouse", "slug": "flex"},
    "Spotter":          {"ats": "greenhouse", "slug": "spotter"},
    "FanDuel":          {"ats": "greenhouse", "slug": "fanduel"},
    "Fanatics":         {"ats": "greenhouse", "slug": "fanaticsinc"},
    "Blockchain.com":   {"ats": "greenhouse", "slug": "blockchain"},
    "Gemini":           {"ats": "greenhouse", "slug": "gemini"},
    "A24":              {"ats": "greenhouse", "slug": "a24"},
    "Epic Games":       {"ats": "greenhouse", "slug": "epicgames"},
    "Sotheby's":        {"ats": "greenhouse", "slug": "sothebys"},
    "StockX":           {"ats": "greenhouse", "slug": "stockx"},
    # Block / Cash App / Square all share the same Greenhouse board.
    # bu_filter narrows each entry to its Business Unit so the digest
    # attributes jobs correctly.
    "Block":            {"ats": "greenhouse", "slug": "block", "bu_filter": "Centralized Block"},
    "Cash App":         {"ats": "greenhouse", "slug": "block", "bu_filter": "Cash"},
    "Square":           {"ats": "greenhouse", "slug": "block", "bu_filter": "Square"},

    # ── Workday ──
    "Warner Bros. Discovery": {"ats": "workday", "tenant": "warnerbros", "wd": "wd5", "site": "global"},
    "Disney":                 {"ats": "workday", "tenant": "disney",     "wd": "wd5", "site": "disneycareer"},
    "Etsy":                   {"ats": "workday", "tenant": "etsy",       "wd": "wd5", "site": "Etsy_Careers"},
    "DraftKings":             {"ats": "workday", "tenant": "draftkings", "wd": "wd1", "site": "DraftKings"},
    "Christie's":             {"ats": "workday", "tenant": "christies",  "wd": "wd3", "site": "Christies_Careers"},

    # ── Workable ──
    "Blueprint":              {"ats": "workable", "slug": "blueprint-bryanjohnson"},

    # ── SmartRecruiters ──
    # NBCUniversal's board (~420 postings) already includes Peacock roles
    # under Business Segment / Brands; no separate Peacock entry to avoid
    # double-counting. If we ever want to split, add a second entry with
    # brand_filter or segment_filter set to "Peacock".
    "NBCUniversal":           {"ats": "smartrecruiters", "slug": "NBCUniversal3"},

    # ── Lever ──
    "Plaid":            {"ats": "lever", "slug": "plaid"},
    "Whoop":            {"ats": "lever", "slug": "whoop"},
    "MoonPay":          {"ats": "lever", "slug": "moonpay"},
    "Anchorage":        {"ats": "lever", "slug": "anchorage"},
    "Ro":               {"ats": "lever", "slug": "ro"},
    "Kraken":           {"ats": "lever", "slug": "kraken"},
    "Jeeves":           {"ats": "lever", "slug": "tryjeeves"},
    "Wealthfront":      {"ats": "lever", "slug": "wealthfront"},
    "Lifeforce":        {"ats": "lever", "slug": "lifeforce"},
    "Viome":            {"ats": "lever", "slug": "viome"},
    "Neko Health":      {"ats": "lever", "slug": "nekohealth"},
    "Spotify":          {"ats": "lever", "slug": "spotify"},
    "Flow":             {"ats": "lever", "slug": "flowlife"},
    "Pattern":          {"ats": "lever", "slug": "pattern"},
    "Netflix":          {"ats": "lever", "slug": "netflix"},

    # ── Ashby ──
    "Ramp":             {"ats": "ashby", "slug": "ramp"},
    "Patreon":          {"ats": "ashby", "slug": "patreon"},
    "Substack":         {"ats": "ashby", "slug": "substack"},
    "Magic Eden":       {"ats": "ashby", "slug": "magiceden"},
    "OpenSea":          {"ats": "ashby", "slug": "opensea"},
    "Sardine":          {"ats": "ashby", "slug": "sardine"},
    "Levels Health":    {"ats": "ashby", "slug": "levels"},
    "Eight Sleep":      {"ats": "ashby", "slug": "eightsleep"},
    "Cadre":            {"ats": "ashby", "slug": "cadre"},
    "Rho":              {"ats": "ashby", "slug": "rho"},
    "Novo":             {"ats": "ashby", "slug": "novo"},
    "Whatnot":          {"ats": "ashby", "slug": "whatnot"},
    "Passes":           {"ats": "ashby", "slug": "passes"},
    "Agentio":          {"ats": "ashby", "slug": "agentio"},
    "Nudge":            {"ats": "ashby", "slug": "nudge"},
    "Superpower":       {"ats": "ashby", "slug": "superpower"},
    # Note: this Ashby board is Hims & Hers' pharmacy/fulfillment arm only
    # (compounding/facilities roles in OH & AZ). Their corporate strategy/
    # ops roles live elsewhere — effectively still uncovered for our digest.
    "Hims & Hers":      {"ats": "ashby", "slug": "hims-and-hers"},

    # ── Not yet covered ──
    # Either on an ATS we don't have an adapter for, or behind Cloudflare.
    #   - Paramount: SuccessFactors (separate adapter, no clean public API)
    #   - Klarna: migrating off Workday to Deel (separate adapter)
    #   - eBay: Phenom People (separate adapter, no clean public endpoint)
    #   - Coinbase: Cloudflare-protected, custom careers page (no Greenhouse/Lever slug)
    #   - Kajabi: JS-rendered, ATS not yet identified
    #   - Function Health: custom careers page (Gem-powered)
    #   - Circle: PhenomPeople hint, would need Phenom adapter
    #   - Arrived: Breezy HR (separate adapter)
    #   - InsideTracker, Republic, Stori, Kushki, Pomelo (fintech): TBD
    #   - Cash App, Square: route through Block's Greenhouse (already wired via bu_filter)
}

# Registry-backed company selection. The legacy literals above document the
# original seed list; these generated values are what the bot actually uses.
from company_registry import company_allowlist, company_boards

COMPANY_ALLOWLIST = company_allowlist()
COMPANY_BOARDS = company_boards()
