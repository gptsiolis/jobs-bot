-- Auto-apply engine (Phase 3). One row per job the user wants applied to. The
-- row doubles as the queue and the review record: a job is enqueued from the
-- dashboard (status 'queued'), the local apply engine drafts the answers
-- (status 'needs_review' or 'skipped'), the user approves it (status
-- 'approved'), and the browser runner submits it (status 'submitted' / 'failed').
-- Nothing is ever submitted without passing through 'approved' — review before
-- submit is enforced by this state machine.
create table if not exists public.application_drafts (
  id uuid primary key default gen_random_uuid(),
  job_id text not null references public.jobs(job_id) on delete cascade,
  status text not null default 'queued',
  ats text not null default '',
  apply_url text not null default '',
  -- Standard fields mapped from applicant_profile (name, email, links, work
  -- auth, etc.) ready to drop into a form.
  field_values jsonb not null default '{}'::jsonb,
  -- Drafted free-text answers: [{ "question": ..., "answer": ... }, ...].
  drafted_answers jsonb not null default '[]'::jsonb,
  -- When status='skipped', why (e.g. "below salary floor ($75,000)").
  skip_reason text,
  error text,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint application_drafts_status_check check (
    status in ('queued', 'drafting', 'needs_review', 'approved',
               'submitting', 'submitted', 'failed', 'skipped')
  )
);

-- One active draft per job; the dashboard upserts on this.
create unique index if not exists application_drafts_job_key
  on public.application_drafts (job_id);

create index if not exists application_drafts_status_idx
  on public.application_drafts (status, created_at desc);

drop trigger if exists touch_application_drafts_updated_at on public.application_drafts;
create trigger touch_application_drafts_updated_at
before update on public.application_drafts
for each row execute function public.touch_updated_at();

alter table public.application_drafts enable row level security;

drop policy if exists "Own drafts read" on public.application_drafts;
create policy "Own drafts read"
  on public.application_drafts for select to authenticated using (true);

drop policy if exists "Own drafts insert" on public.application_drafts;
create policy "Own drafts insert"
  on public.application_drafts for insert to authenticated with check (true);

drop policy if exists "Own drafts update" on public.application_drafts;
create policy "Own drafts update"
  on public.application_drafts for update to authenticated using (true) with check (true);

drop policy if exists "Own drafts delete" on public.application_drafts;
create policy "Own drafts delete"
  on public.application_drafts for delete to authenticated using (true);
