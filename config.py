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
# Skip roles with these keywords in the title.
# Note: "manager" excludes "Operations Manager" — remove from list if you
# want manager-level ops roles included.
SKIP_SENIORITY = [
    "senior", "sr.", "staff", "principal", "director",
    "vp", "vice president", "head of", "manager", "lead",
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

# ── Company allowlist ───────────────────────────────────────
# A role only emails through if its employer matches one of these companies.
# Matching is normalized (case-insensitive, punctuation/suffix stripped).
# Add aliases as separate entries if a company shows up under multiple names.
# Edit weekly: add/remove freely.
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
    # These companies are either on Workday or use a custom careers portal
    # we don't have an adapter for. Phase 4 work. The watchlist mode just
    # won't pull from them until then:
    #   Coinbase, Function Health, Spring Health, Hims & Hers, Klarna,
    #   Pipe, Rarible, eBay, Etsy, Arrived, Tally Health, InsideTracker,
    #   Republic, Beehiiv, Fourthwall, Kajabi, DraftKings, Pomelo, Stori,
    #   Kushki, Blueprint, Sunday Health, Nue Life Health, Cash App,
    #   Square, Thrasio, OpenStore, REEF Technology, Paramount,
    #   Disney, NBCUniversal, Warner Bros. Discovery, Christie's, Sotheby's
}
