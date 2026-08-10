-- Keep the inbox review queue to one visible suggestion per Gmail thread/job.
-- Older duplicates are closed, and a partial unique index prevents new open
-- duplicates even if two messages from the same thread are processed.
with ranked as (
  select
    id,
    row_number() over (
      partition by gmail_thread_id, job_id
      order by created_at desc, id desc
    ) as rn
  from public.status_suggestions
  where gmail_thread_id is not null
    and resolved = false
)
update public.status_suggestions s
set
  resolved = true,
  resolution = coalesce(s.resolution, 'duplicate_thread'),
  resolved_at = coalesce(s.resolved_at, now())
from ranked r
where s.id = r.id
  and r.rn > 1;

create unique index if not exists status_suggestions_open_thread_job_key
  on public.status_suggestions (gmail_thread_id, job_id)
  where gmail_thread_id is not null and resolved = false;
