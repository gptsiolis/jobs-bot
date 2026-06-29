-- Email-driven status updates. A scheduled agent reads the inbox, matches
-- recruiter/ATS emails to jobs already in flight, and classifies them as a
-- rejection or an advancement. High-confidence calls flip the job's status
-- directly (audited in job_events); anything less sure lands in
-- status_suggestions for one-click human review on the dashboard.

-- Every email message the agent has already looked at, so a thread is never
-- classified twice across runs. Written only by the service-role agent.
create table if not exists public.processed_emails (
  message_id text primary key,
  thread_id text,
  job_id text references public.jobs(job_id) on delete set null,
  decision text,
  confidence numeric,
  processed_at timestamptz not null default now()
);

create index if not exists processed_emails_thread_idx
  on public.processed_emails (thread_id);

-- The human review queue: actionable status changes the agent surfaced but did
-- not auto-apply (or auto-applied ones kept for audit). One row per email that
-- proposes a change to one job.
create table if not exists public.status_suggestions (
  id uuid primary key default gen_random_uuid(),
  job_id text not null references public.jobs(job_id) on delete cascade,
  suggested_status text not null,
  current_status text,
  decision text not null,
  confidence numeric not null default 0,
  evidence text,
  email_subject text,
  email_from text,
  email_date timestamptz,
  gmail_thread_id text,
  gmail_message_id text,
  auto_applied boolean not null default false,
  resolved boolean not null default false,
  resolution text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  constraint status_suggestions_suggested_status_check check (
    suggested_status in ('next_round', 'rejected')
  )
);

-- Don't surface the same email against the same job twice.
create unique index if not exists status_suggestions_message_job_key
  on public.status_suggestions (gmail_message_id, job_id);

create index if not exists status_suggestions_pending_idx
  on public.status_suggestions (resolved, created_at desc);

alter table public.processed_emails enable row level security;
alter table public.status_suggestions enable row level security;

-- processed_emails is agent-only (service role bypasses RLS); no authenticated
-- policies needed. The dashboard reads/resolves status_suggestions.
drop policy if exists "Authenticated read status suggestions" on public.status_suggestions;
create policy "Authenticated read status suggestions"
  on public.status_suggestions for select to authenticated using (true);

drop policy if exists "Authenticated update status suggestions" on public.status_suggestions;
create policy "Authenticated update status suggestions"
  on public.status_suggestions for update to authenticated using (true) with check (true);
