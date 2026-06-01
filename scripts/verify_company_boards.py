"""Probe likely ATS board slugs for disabled registry candidates.

This script only prints candidates. It does not edit config or registry files.
Use the output to promote a company by adding its verified ATS config in
data/company_registry.json.
"""

import argparse
import os
import re
import sys
from itertools import product

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from company_registry import load_registry


HEADERS = {"User-Agent": "Mozilla/5.0"}

ALIASES = {
    "1password": ["onepassword"],
    "anduril": ["andurilindustries"],
    "bill-com": ["billcom", "bill"],
    "hims-hers": ["hims-and-hers"],
    "public-com": ["public"],
    "squarespace": ["square-space"],
    "square-space": ["squarespace"],
    "the-browser-company": ["browsercompany", "thebrowsercompany"],
    "wealthsimple": ["wealthsimple-technologies-inc"],
}

WORKDAY_SITES = [
    "careers",
    "Careers",
    "External",
    "External_Careers",
    "Jobs",
    "job",
    "jobs",
    "default",
]

WORKDAY_HOSTS = ("wd1", "wd3", "wd5")


def slug_candidates(name):
    base = re.sub(r"[^a-z0-9]+", "", name.lower())
    dashed = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    compact_words = re.sub(r"\b(the|inc|labs|technologies|technology)\b", "", dashed)
    compact_words = re.sub(r"-+", "-", compact_words).strip("-")
    variants = [base, dashed, compact_words, compact_words.replace("-", "")]
    variants.extend(ALIASES.get(dashed, []))
    variants.extend(ALIASES.get(base, []))
    return list(dict.fromkeys(v for v in variants if v))


def _check_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
    except requests.RequestException:
        return False
    return resp.ok and isinstance(resp.json().get("jobs"), list)


def _check_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        return isinstance(resp.json(), list)
    except ValueError:
        return False


def _check_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    return isinstance(data.get("jobs") or data.get("jobPostings"), list)


def _check_workable(slug):
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    return isinstance(data.get("jobs"), list) and len(data.get("jobs")) > 0


def _check_smartrecruiters(slug):
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    try:
        resp = requests.get(
            url,
            params={"limit": 1, "offset": 0},
            headers=HEADERS,
            timeout=12,
        )
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    return isinstance(data.get("content"), list) and int(data.get("totalFound") or 0) > 0


def _check_workday(candidate):
    tenant, wd, site = candidate
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    payload = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=12)
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    return isinstance(data.get("jobPostings"), list)


CHECKS = {
    "greenhouse": _check_greenhouse,
    "lever": _check_lever,
    "ashby": _check_ashby,
    "workable": _check_workable,
    "smartrecruiters": _check_smartrecruiters,
}


def workday_candidates(name):
    slugs = slug_candidates(name)
    sites = list(dict.fromkeys(WORKDAY_SITES + slugs + [f"{slug}_Careers" for slug in slugs]))
    return product(slugs, WORKDAY_HOSTS, sites)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", help="Only probe one company name")
    parser.add_argument("--include-enabled", action="store_true")
    parser.add_argument(
        "--ats",
        choices=sorted(list(CHECKS) + ["workday"]),
        help="Only check one ATS type",
    )
    args = parser.parse_args()

    companies = load_registry()
    for company in companies:
        name = company["name"]
        if args.company and args.company.lower() not in name.lower():
            continue
        if not args.include_enabled and company.get("enabled", bool(company.get("ats"))):
            continue
        for slug in slug_candidates(name):
            for ats_name, check in CHECKS.items():
                if args.ats and args.ats != ats_name:
                    continue
                if check(slug):
                    print(f"{name}: {{\"type\": \"{ats_name}\", \"slug\": \"{slug}\"}}")
        if not args.ats or args.ats == "workday":
            for tenant, wd, site in workday_candidates(name):
                if _check_workday((tenant, wd, site)):
                    print(
                        f"{name}: {{\"type\": \"workday\", \"tenant\": \"{tenant}\", "
                        f"\"wd\": \"{wd}\", \"site\": \"{site}\"}}"
                    )


if __name__ == "__main__":
    main()
