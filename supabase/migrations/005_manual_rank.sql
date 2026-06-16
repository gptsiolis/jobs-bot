-- Manual ordering for the Saved and Applied buckets.
-- manual_rank is a sparse float so jobs can be reordered by drag-and-drop in
-- the dashboard. It is intentionally NOT written by upsert_jobs(), so scraper
-- re-runs never clobber a user's hand-picked priority order.

alter table public.jobs add column if not exists manual_rank double precision;

create index if not exists jobs_manual_rank_idx
  on public.jobs(status, manual_rank asc nulls last);

-- Bulk-assign manual_rank for a list of jobs. Runs as security definer so the
-- authenticated dashboard user can persist an ordering without an INSERT policy
-- (the jobs table only grants SELECT/UPDATE to authenticated).
create or replace function public.reorder_jobs(payload jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  item jsonb;
begin
  for item in select * from jsonb_array_elements(payload)
  loop
    update public.jobs
      set manual_rank = nullif(item->>'manual_rank', '')::double precision
    where job_id = item->>'job_id';
  end loop;
end;
$$;

revoke all on function public.reorder_jobs(jsonb) from public, anon;
grant execute on function public.reorder_jobs(jsonb) to authenticated, service_role;
