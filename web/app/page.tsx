import Link from "next/link";
import { redirect } from "next/navigation";
import { signOut } from "./actions";
import { CompanyWatchlistMenu } from "@/components/company-watchlist-menu";
import { JobsDashboard } from "@/components/jobs-dashboard";
import { RolePreferencesMenu } from "@/components/role-preferences-menu";
import { ScraperMenu } from "@/components/scraper-menu";
import { StatusSuggestions } from "@/components/status-suggestions";
import { ApplicationReview } from "@/components/application-review";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type {
  ApplicationDraft,
  CompanyContact,
  CompanyWatchlistRequest,
  JobRow,
  JobRun,
  RolePreference,
  StatusSuggestion
} from "@/lib/types";

export default async function HomePage() {
  const supabase = await createSupabaseServerClient();
  const { data: auth } = await supabase.auth.getUser();

  if (!auth.user) {
    redirect("/login");
  }

  const [
    { data: jobs, error: jobsError },
    { data: runs },
    { data: companyRequests },
    { data: rolePreferences },
    { count: appliedTotal },
    { data: companyContacts },
    { data: statusSuggestions },
    { data: applicationDrafts }
  ] = await Promise.all([
    supabase
      .from("jobs")
      .select(
        "job_id,title,company,location_text,apply_url,source,ats,first_seen_at,last_seen_at,fit_bucket,fit_reasons,sponsor_tier,sponsor_reasons,quality_tier,sector,applicability_score,status,applied_at,contact_responded,manual_rank,visibility,role_family,seniority_level,compensation_min,compensation_max,ai_fit_score,ai_company_score,ai_summary,ai_reject_reasons,ai_labels,description_excerpt"
      )
      .order("applicability_score", { ascending: false })
      .order("last_seen_at", { ascending: false })
      .limit(1000),
    supabase
      .from("job_runs")
      .select("id,mode,status,started_at,finished_at,total_found,total_written,total_new,counts_by_source,failures,error")
      .order("started_at", { ascending: false })
      .limit(5),
    supabase
      .from("company_watchlist_requests")
      .select("id,company_name,normalized_name,status,ats_config,last_checked_at,last_error,created_at")
      .in("status", ["pending", "resolved", "unresolved"])
      .order("created_at", { ascending: false })
      .limit(8),
    supabase
      .from("role_preferences")
      .select("id,keyword,family")
      .order("keyword", { ascending: true }),
    // Total jobs ever applied to - applied_at is stamped on entry to the applied
    // funnel and survives later moves (messaged, next round, rejected).
    supabase
      .from("jobs")
      .select("job_id", { count: "exact", head: true })
      .not("applied_at", "is", null),
    supabase
      .from("company_contacts")
      .select("id,company,contact_name,linkedin_url,responded,created_at")
      .order("created_at", { ascending: true }),
    supabase
      .from("status_suggestions")
      .select(
        "id,job_id,suggested_status,current_status,decision,confidence,evidence,email_subject,email_from,created_at,jobs(title,company)"
      )
      .eq("resolved", false)
      .order("created_at", { ascending: false }),
    supabase
      .from("application_drafts")
      .select(
        "id,job_id,status,ats,apply_url,field_values,drafted_answers,skip_reason,flag_reason,error,confirmation_path,submitted_at,jobs(title,company)"
      )
      .order("created_at", { ascending: false })
  ]);

  // Sign the agent's confirmation/flag screenshots so the dashboard can show them.
  const draftRows = (applicationDrafts || []) as unknown as ApplicationDraft[];
  const shotPaths = draftRows.map((d) => d.confirmation_path).filter(Boolean) as string[];
  let signedShots: Record<string, string> = {};
  if (shotPaths.length) {
    const { data: signed } = await supabase.storage
      .from("applications")
      .createSignedUrls(shotPaths, 3600);
    signedShots = Object.fromEntries(
      (signed || [])
        .filter((s): s is { path: string; signedUrl: string; error: null } =>
          Boolean(s.signedUrl && s.path))
        .map((s) => [s.path, s.signedUrl])
    );
  }
  const draftsWithShots = draftRows.map((d) => ({
    ...d,
    screenshot_url: d.confirmation_path ? signedShots[d.confirmation_path] ?? null : null
  }));

  if (jobsError) {
    throw new Error(jobsError.message);
  }

  const latestRun = ((runs || []) as JobRun[])[0];

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <h1>Jobs Bot</h1>
          <span>{auth.user.email}</span>
        </div>
        <div className="topbar-actions">
          <div className="stat-chip" title="Total jobs you've ever applied to, including messaged, next round, and rejected">
            <strong>{appliedTotal ?? 0}</strong>
            <span className="muted">applied</span>
          </div>
          <ScraperMenu initialRun={latestRun} />
          <RolePreferencesMenu preferences={(rolePreferences || []) as RolePreference[]} />
          <CompanyWatchlistMenu
            companyRequests={(companyRequests || []) as CompanyWatchlistRequest[]}
          />
          <Link className="text-button" href="/profile">
            Profile
          </Link>
          <form action={signOut}>
            <button className="text-button" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </header>
      <main className="main">
        <StatusSuggestions
          suggestions={(statusSuggestions || []) as unknown as StatusSuggestion[]}
        />
        <ApplicationReview drafts={draftsWithShots} />
        <JobsDashboard
          jobs={(jobs || []) as JobRow[]}
          contacts={(companyContacts || []) as CompanyContact[]}
        />
      </main>
    </div>
  );
}
