import os

# Email settings
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

# RapidAPI settings
RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]

# Job search settings
SEARCH_QUERIES = [
    "sales miami startup",
    "account executive miami startup",
    "business development miami startup",
    "SDR miami startup",
    "sales development representative miami",
    "sales remote startup",
    "account executive remote startup",
    "business development remote startup",
    "SDR remote startup",
    "sales miami tech",
    "account executive remote SaaS",
    "sales remote venture backed",
]

# Location filter — jobs must match one of these (case-insensitive)
ALLOWED_LOCATIONS = ["miami", "remote", "anywhere", "distributed", "florida", "fl"]

# VC / startup keyword filter — at least one must appear in the description or employer name
STARTUP_KEYWORDS = [
    # Funding signals
    "startup", "start-up", "series a", "series b", "series c", "series d",
    "seed stage", "seed round", "pre-seed", "venture", "vc-backed", "vc backed",
    "venture-backed", "venture backed", "funded", "raised", "funding round",
    "backed by", "investors include", "growth stage", "early stage", "early-stage",
    # Sector tags common to VC-backed cos
    "saas", "fintech", "healthtech", "health tech", "edtech", "proptech",
    "insurtech", "martech", "adtech", "cleantech", "biotech", "medtech",
    "ai-powered", "ai powered", "machine learning", "artificial intelligence",
    "cloud-based", "cloud based", "platform", "marketplace",
    # Hypergrowth / startup culture signals
    "hypergrowth", "hyper-growth", "high-growth", "high growth",
    "fast-paced", "fast paced", "rapidly growing", "scaling",
    "disrupt", "innovative", "mission-driven", "mission driven",
    "equity", "stock options", "employee stock",
    # Well-known VC firms (partial list — broad net)
    "a16z", "andreessen", "sequoia", "accel", "greylock", "benchmark",
    "lightspeed", "index ventures", "founders fund", "khosla",
    "general catalyst", "bessemer", "insight partners", "tiger global",
    "softbank", "y combinator", "yc ", "techstars",
]