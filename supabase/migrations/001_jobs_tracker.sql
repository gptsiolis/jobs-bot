create extension if not exists pgcrypto;

create table if not exists public.jobs (
  job_id text primary key,
  title text not null default '',
  company text not null default '',
  location_text text not null default '',
  apply_url text not null default '',
  source text not null default '',
  ats text not null default '',
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  fit_bucket text not null default 'unknown',
  fit_reasons text[] not null default '{}',
  sponsor_tier text not null default 'unknown_no_ban',
  sponsor_reasons text[] not null default '{}',
  quality_tier text not null default 'acceptable',
  sector text not null default 'unknown',
  applicability_score integer not null default 0,
  status text not null default 'new',
  description_excerpt text not null default '',
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint jobs_status_check check (
    status in ('new', 'saved', 'applied', 'dismissed', 'archived')
  )
);

create table if not exists public.job_runs (
  id uuid primary key default gen_random_uuid(),
  mode text not null,
  status text not null default 'running',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  total_found integer not null default 0,
  total_written integer not null default 0,
  total_new integer not null default 0,
  counts_by_source jsonb not null default '{}'::jsonb,
  failures jsonb not null default '[]'::jsonb,
  error text,
  created_at timestamptz not null default now()
);

create table if not exists public.job_events (
  id uuid primary key default gen_random_uuid(),
  job_id text not null references public.jobs(job_id) on delete cascade,
  event_type text not null,
  old_status text,
  new_status text,
  actor uuid default auth.uid(),
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists jobs_status_score_idx
  on public.jobs(status, applicability_score desc, last_seen_at desc);
create index if not exists jobs_company_idx on public.jobs(company);
create index if not exists jobs_source_idx on public.jobs(source);
create index if not exists jobs_fit_bucket_idx on public.jobs(fit_bucket);
create index if not exists jobs_sponsor_tier_idx on public.jobs(sponsor_tier);
create index if not exists jobs_quality_tier_idx on public.jobs(quality_tier);
create index if not exists job_runs_started_idx on public.job_runs(started_at desc);
create index if not exists job_events_job_created_idx
  on public.job_events(job_id, created_at desc);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists touch_jobs_updated_at on public.jobs;
create trigger touch_jobs_updated_at
before update on public.jobs
for each row execute function public.touch_updated_at();

create or replace function public.log_job_status_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if old.status is distinct from new.status then
    insert into public.job_events(job_id, event_type, old_status, new_status)
    values (new.job_id, new.status, old.status, new.status);
  end if;
  return new;
end;
$$;

drop trigger if exists log_jobs_status_change on public.jobs;
create trigger log_jobs_status_change
after update of status on public.jobs
for each row execute function public.log_job_status_change();

create or replace function public.upsert_jobs(payload jsonb)
returns table(job_id text, inserted boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
  item jsonb;
  was_inserted boolean;
  returned_job_id text;
begin
  for item in select * from jsonb_array_elements(payload)
  loop
    insert into public.jobs (
      job_id,
      title,
      company,
      location_text,
      apply_url,
      source,
      ats,
      first_seen_at,
      last_seen_at,
      fit_bucket,
      fit_reasons,
      sponsor_tier,
      sponsor_reasons,
      quality_tier,
      sector,
      applicability_score,
      status,
      description_excerpt,
      raw_payload
    )
    values (
      item->>'job_id',
      coalesce(item->>'title', ''),
      coalesce(item->>'company', ''),
      coalesce(item->>'location_text', ''),
      coalesce(item->>'apply_url', ''),
      coalesce(item->>'source', ''),
      coalesce(item->>'ats', ''),
      coalesce((item->>'first_seen_at')::timestamptz, now()),
      coalesce((item->>'last_seen_at')::timestamptz, now()),
      coalesce(item->>'fit_bucket', 'unknown'),
      coalesce(array(select jsonb_array_elements_text(item->'fit_reasons')), '{}'),
      coalesce(item->>'sponsor_tier', 'unknown_no_ban'),
      coalesce(array(select jsonb_array_elements_text(item->'sponsor_reasons')), '{}'),
      coalesce(item->>'quality_tier', 'acceptable'),
      coalesce(item->>'sector', 'unknown'),
      coalesce((item->>'applicability_score')::integer, 0),
      coalesce(item->>'status', 'new'),
      coalesce(item->>'description_excerpt', ''),
      coalesce(item->'raw_payload', '{}'::jsonb)
    )
    on conflict on constraint jobs_pkey do update set
      title = excluded.title,
      company = excluded.company,
      location_text = excluded.location_text,
      apply_url = excluded.apply_url,
      source = excluded.source,
      ats = excluded.ats,
      last_seen_at = excluded.last_seen_at,
      fit_bucket = excluded.fit_bucket,
      fit_reasons = excluded.fit_reasons,
      sponsor_tier = excluded.sponsor_tier,
      sponsor_reasons = excluded.sponsor_reasons,
      quality_tier = excluded.quality_tier,
      sector = excluded.sector,
      applicability_score = excluded.applicability_score,
      description_excerpt = excluded.description_excerpt,
      raw_payload = excluded.raw_payload
    returning (xmax = 0), public.jobs.job_id into was_inserted, returned_job_id;

    job_id := returned_job_id;
    inserted := was_inserted;
    return next;
  end loop;
end;
$$;

revoke all on function public.upsert_jobs(jsonb) from public, anon, authenticated;
grant execute on function public.upsert_jobs(jsonb) to service_role;

alter table public.jobs enable row level security;
alter table public.job_runs enable row level security;
alter table public.job_events enable row level security;

drop policy if exists "Authenticated users can read jobs" on public.jobs;
create policy "Authenticated users can read jobs"
on public.jobs for select
to authenticated
using (true);

drop policy if exists "Authenticated users can update job status" on public.jobs;
create policy "Authenticated users can update job status"
on public.jobs for update
to authenticated
using (true)
with check (true);

drop policy if exists "Authenticated users can read job runs" on public.job_runs;
create policy "Authenticated users can read job runs"
on public.job_runs for select
to authenticated
using (true);

drop policy if exists "Authenticated users can read job events" on public.job_events;
create policy "Authenticated users can read job events"
on public.job_events for select
to authenticated
using (true);
