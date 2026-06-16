-- Track when a job was first moved into the applied funnel (applied or
-- applied_messaged), so the dashboard can show a "date applied" per job.

alter table public.jobs add column if not exists applied_at timestamptz;

-- Backfill from the status-change log: earliest transition into the funnel.
update public.jobs j
set applied_at = sub.first_applied
from (
  select job_id, min(created_at) as first_applied
  from public.job_events
  where new_status in ('applied', 'applied_messaged')
  group by job_id
) sub
where sub.job_id = j.job_id and j.applied_at is null;

-- Any currently-applied job with no event history falls back to updated_at.
update public.jobs
set applied_at = coalesce(updated_at, now())
where status in ('applied', 'applied_messaged') and applied_at is null;

-- Stamp applied_at automatically the first time a job enters the applied
-- funnel. Only sets it when null, so the original date survives later moves
-- (applied -> applied_messaged -> next_round -> back to applied).
create or replace function public.set_applied_at()
returns trigger
language plpgsql
as $$
begin
  if new.status in ('applied', 'applied_messaged') and new.applied_at is null then
    new.applied_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists set_jobs_applied_at on public.jobs;
create trigger set_jobs_applied_at
before update of status on public.jobs
for each row execute function public.set_applied_at();
