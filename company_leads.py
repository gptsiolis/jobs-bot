"""Company lead recording and promotion from broad job search."""

from urllib.parse import quote

from company_registry import normalize_company_name
from storage import calculate_applicability_score, utc_now_iso


def record_company_leads(store, jobs, min_score=55):
    leads = {}
    now = utc_now_iso()
    for job in jobs:
        source = job.get("source", "")
        if not source.startswith("serpapi:"):
            continue
        company = job.get("employer_name") or job.get("company") or ""
        normalized = normalize_company_name(company)
        if not normalized or company.lower() == "unknown":
            continue
        score = int(job.get("applicability_score") or calculate_applicability_score(job))
        if score < min_score:
            continue
        payload = {
            "company_name": company,
            "normalized_name": normalized,
            "first_source": source,
            "example_job_ids": [job["job_id"]] if job.get("job_id") else [],
            "lead_score": score,
            "status": "new",
            "last_seen_at": now,
        }
        existing = leads.get(normalized)
        if not existing or score > existing["lead_score"]:
            leads[normalized] = payload
    if not leads:
        return 0
    store._request(
        "POST",
        "/rest/v1/company_leads?on_conflict=normalized_name",
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        json=list(leads.values()),
    )
    return len(leads)


def promote_company_leads(store, min_score=65, limit=25):
    leads = store._request(
        "GET",
        "/rest/v1/company_leads"
        f"?select=id,company_name,normalized_name,lead_score,status"
        f"&status=eq.new&lead_score=gte.{min_score}&order=lead_score.desc&limit={limit}",
    ) or []
    promoted = 0
    for lead in leads:
        normalized = quote(lead["normalized_name"], safe="")
        existing = store._request(
            "GET",
            "/rest/v1/company_watchlist_requests"
            f"?select=id&normalized_name=eq.{normalized}&limit=1",
        ) or []
        if not existing:
            store._request(
                "POST",
                "/rest/v1/company_watchlist_requests",
                headers={"Prefer": "return=minimal"},
                json={
                    "company_name": lead["company_name"],
                    "normalized_name": lead["normalized_name"],
                    "status": "pending",
                    "source_notes": "Promoted from broad job search",
                },
            )
            promoted += 1
        store._request(
            "PATCH",
            f"/rest/v1/company_leads?id=eq.{quote(str(lead['id']), safe='')}",
            headers={"Prefer": "return=minimal"},
            json={"status": "promoted"},
        )
    return promoted
