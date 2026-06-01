export type JobStatus = "new" | "saved" | "applied" | "dismissed" | "archived";

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
  failures: unknown[];
};
