"""Curated company registry and sponsor metadata helpers."""

import json
import os
import re


BASE_DIR = os.path.dirname(__file__)
REGISTRY_FILE = os.path.join(BASE_DIR, "data", "company_registry.json")
SPONSOR_SCORES_FILE = os.path.join(BASE_DIR, "data", "sponsor_scores.json")

QUALITY_TIERS = ("excellent", "strong", "acceptable")
SPONSOR_TIERS = ("strong_history", "some_history", "unknown_no_ban", "explicit_no")

QUALITY_RANK = {tier: idx for idx, tier in enumerate(QUALITY_TIERS)}
SPONSOR_RANK = {tier: idx for idx, tier in enumerate(SPONSOR_TIERS)}

SPONSOR_LABELS = {
    "strong_history": "strong history",
    "some_history": "some history",
    "unknown_no_ban": "unknown/no ban",
    "explicit_no": "explicit no",
}


def normalize_company_name(name):
    text = (name or "").lower()
    text = re.sub(r"[\.,&']", " ", text)
    text = re.sub(r"\b(inc|llc|corp|corporation|co|ltd|the)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sponsor_tier_from_score(score):
    recent_lca_count = int(score.get("recent_lca_count") or 0)
    if recent_lca_count >= 25:
        return "strong_history"
    if recent_lca_count >= 3:
        return "some_history"
    return None


def load_registry():
    """Load curated companies, overlaying generated sponsor scores when present."""
    raw = _load_json(REGISTRY_FILE, {"companies": []})
    scores = _load_json(SPONSOR_SCORES_FILE, {})
    companies = []
    for company in raw.get("companies", []):
        enriched = dict(company)
        score = scores.get(enriched.get("name", "")) or scores.get(
            normalize_company_name(enriched.get("name", ""))
        )
        if score:
            enriched["sponsor_score"] = score
            score_tier = _sponsor_tier_from_score(score)
            if score_tier and enriched.get("sponsor_tier") != "explicit_no":
                enriched["sponsor_tier"] = score_tier
        companies.append(enriched)
    return companies


def validate_registry(companies=None):
    """Return validation errors for registry entries."""
    companies = load_registry() if companies is None else companies
    errors = []
    seen = set()
    for company in companies:
        name = company.get("name", "")
        key = normalize_company_name(name)
        if not name:
            errors.append("company missing name")
            continue
        if key in seen:
            errors.append(f"duplicate company: {name}")
        seen.add(key)

        quality = company.get("quality_tier")
        sponsor = company.get("sponsor_tier")
        if quality not in QUALITY_TIERS:
            errors.append(f"{name}: invalid quality_tier {quality!r}")
        if sponsor not in SPONSOR_TIERS:
            errors.append(f"{name}: invalid sponsor_tier {sponsor!r}")

        ats = company.get("ats") or {}
        enabled = company.get("enabled", bool(ats))
        if enabled and sponsor == "explicit_no":
            errors.append(f"{name}: enabled company has explicit_no sponsor_tier")
        if enabled and not ats:
            errors.append(f"{name}: enabled company missing ats config")
        if ats and not ats.get("type"):
            errors.append(f"{name}: ats config missing type")
    return errors


def company_allowlist():
    """Return {sector: [company names]} from the curated registry."""
    grouped = {}
    for company in load_registry():
        if company.get("exclude_reasons"):
            continue
        grouped.setdefault(company.get("sector", "other"), []).append(company["name"])
    return {sector: sorted(names) for sector, names in sorted(grouped.items())}


def company_boards():
    """Return scraper config for enabled companies with verified ATS details."""
    boards = {}
    for company in load_registry():
        ats = company.get("ats") or {}
        if not company.get("enabled", bool(ats)):
            continue
        if not ats or company.get("sponsor_tier") == "explicit_no":
            continue
        cfg = dict(ats)
        cfg["ats"] = cfg.pop("type")
        cfg["sector"] = company.get("sector", "other")
        cfg["quality_tier"] = company.get("quality_tier", "acceptable")
        cfg["sponsor_tier"] = company.get("sponsor_tier", "unknown_no_ban")
        cfg["source_notes"] = company.get("source_notes", "")
        boards[company["name"]] = cfg
    return boards


def metadata_for_company(name):
    """Return registry metadata for display/sorting, or conservative defaults."""
    target = normalize_company_name(name)
    for company in load_registry():
        if normalize_company_name(company.get("name")) == target:
            return {
                "sector": company.get("sector", "other"),
                "quality_tier": company.get("quality_tier", "acceptable"),
                "sponsor_tier": company.get("sponsor_tier", "unknown_no_ban"),
                "source_notes": company.get("source_notes", ""),
            }
    return {
        "sector": "unknown",
        "quality_tier": "acceptable",
        "sponsor_tier": "unknown_no_ban",
        "source_notes": "",
    }


def sponsor_label(tier):
    return SPONSOR_LABELS.get(tier, tier or "unknown/no ban")
