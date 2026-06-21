export type JobStatus =
  | "new"
  | "saved"
  | "applied"
  | "applied_messaged"
  | "next_round"
  | "rejected"
  | "dismissed"
  | "archived";

export type JobRow = {
  job_id: string;
  title: string;
  company: string;
  location_text: string;
  apply_url: string;
  source: string;
  ats: string;
  first_seen_at: string;
  last_seen_at: string;
  fit_bucket: string;
  fit_reasons: string[];
  sponsor_tier: string;
  sponsor_reasons: string[];
  quality_tier: string;
  sector: string;
  applicability_score: number;
  status: JobStatus;
  applied_at: string | null;
  contact_responded: boolean;
  manual_rank: number | null;
  visibility: string;
  role_family: string;
  seniority_level: string;
  compensation_min: number | null;
  compensation_max: number | null;
  ai_fit_score: number | null;
  ai_company_score: number | null;
  ai_summary: string;
  ai_reject_reasons: string[];
  ai_labels: string[];
  description_excerpt: string;
};

export type JobRun = {
  id: string;
  mode: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  total_found: number;
  total_written: number;
  total_new: number;
  counts_by_source?: Record<string, number> | null;
  failures: unknown[];
  error?: string | null;
};
export type RolePreference = {
  id: string;
  keyword: string;
  family: "operations_strategy" | "business_development" | "early_career";
};

export type CompanyContact = {
  id: string;
  company: string;
  contact_name: string | null;
  linkedin_url: string;
  responded: boolean;
  created_at: string;
};

export type CompanyWatchlistRequest = {
  id: string;
  company_name: string;
  normalized_name: string;
  status: "pending" | "resolved" | "unresolved" | "disabled";
  ats_config: Record<string, unknown> | null;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
};