import { redirect } from "next/navigation";
import { signOut } from "./actions";
import { CompanyWatchlistMenu } from "@/components/company-watchlist-menu";
import { JobsDashboard } from "@/components/jobs-dashboard";
import { ScraperMenu } from "@/components/scraper-menu";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { CompanyWatchlistRequest, JobRow, JobRun } from "@/lib/types";

export default async function HomePage() {
  const supabase = await createSupabaseServerClient();
  const { data: auth } = await supabase.auth.getUser();

  if (!auth.user) {
    redirect("/login");
  }

  const [
    { data: jobs, error: jobsError },
    { data: runs },
    { data: companyRequests }
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
      .limit(8)
  ]);

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
          <ScraperMenu initialRun={latestRun} />
          <CompanyWatchlistMenu
            companyRequests={(companyRequests || []) as CompanyWatchlistRequest[]}
          />
          <form action={signOut}>
            <button className="text-button" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </header>
      <main className="main">
        <JobsDashboard jobs={(jobs || []) as JobRow[]} />
      </main>
    </div>
  );
}
