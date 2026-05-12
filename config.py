import os
from dotenv import load_dotenv

load_dotenv()

# ── Email settings ──────────────────────────────────────────────
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

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
}

# ── Role search queries ────────────────────────────────────────
# Each query triggers a separate search on every board; keep this list tight.
ROLE_QUERIES = [
    "chief of staff",
    "operations",
    "business operations",
    "strategy",
    "strategic finance",
    "special projects",
]

# ── Seniority filter ─────────────────────────────────────────
# Skip roles with these keywords in the title. "manager" and "lead" used
# to be here but were dropped — ops/strategy/CoS roles routinely carry
# those titles at the 1-3yr level we're targeting.
SKIP_SENIORITY = [
    "senior", "sr.", "staff", "principal", "director",
    "vp", "vice president", "head of",
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
        "Beehiiv",
        "Christie's",
        "Disney",
        "Disney+",
        "DraftKings",
        "Epic Games",
        "Fanatics",
        "FanDuel",
        "Fourthwall",
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
        "Pipe",
        "Plaid",
        "Pomelo",
        "Public.com",
        "Ramp",
        "Rarible",
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
        "Nue Life Health",
        "Oura",
        "Papa",
        "Ro",
        "Roman",
        "Spring Health",
        "Sunday Health",
        "Superpower",
        "Superpower Health",
        "Tally Health",
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
        "OpenStore",
        "REEF Technology",
        "StockX",
        "Thrasio",
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
    "Block":            {"ats": "greenhouse", "slug": "block"},

    # ── Workday ──
    "Warner Bros. Discovery": {"ats": "workday", "tenant": "warnerbros", "wd": "wd5", "site": "global"},
    "Disney":                 {"ats": "workday", "tenant": "disney",     "wd": "wd5", "site": "disneycareer"},
    "Etsy":                   {"ats": "workday", "tenant": "etsy",       "wd": "wd5", "site": "Etsy_Careers"},
    "DraftKings":             {"ats": "workday", "tenant": "draftkings", "wd": "wd1", "site": "DraftKings"},

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

    # ── Not yet covered ──
    # Either on a Workday tenant we couldn't locate, on a different ATS we
    # don't have an adapter for, or behind Cloudflare. Add as we build out.
    #   - Paramount, NBCUniversal, Klarna: Workday tenants exist but our
    #     payload gets 422 — site name needs investigation
    #   - eBay: Phenom People (separate adapter)
    #   - Beehiiv: BambooHR (separate adapter)
    #   - Blueprint: Workable (separate adapter)
    #   - Kajabi: Greenhouse (slug not found in our attempts)
    #   - Coinbase, Hims & Hers: Cloudflare-protected, custom careers pages
    #   - Function Health, Spring Health: custom careers pages
    #   - Cash App: routes through Block's main careers page
    #   - Pipe, Rarible, Arrived, Tally Health, InsideTracker, Republic,
    #     Fourthwall, Pomelo, Stori, Kushki, Sunday Health, Nue Life Health,
    #     Thrasio, OpenStore, REEF Technology, Square: TBD
}
