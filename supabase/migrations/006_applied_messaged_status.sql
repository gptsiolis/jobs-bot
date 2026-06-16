-- Adds the "applied_messaged" status: jobs the user has BOTH applied to and
-- reached out to a contact at the company about. It sits between "applied" and
-- "next_round" in the funnel and gets its own dashboard bucket.

alter table public.jobs drop constraint if exists jobs_status_check;
alter table public.jobs add constraint jobs_status_check check (
  status in (
    'new', 'saved', 'applied', 'applied_messaged',
    'next_round', 'rejected', 'dismissed', 'archived'
  )
);

-- Keep dedup precedence consistent: a messaged application outranks a plain
-- application, but next_round still wins.
create or replace function public.job_status_rank(status text)
returns integer
language sql
immutable
as $$
  select case status
    when 'next_round' then 0
    when 'applied_messaged' then 1
    when 'applied' then 2
    when 'saved' then 3
    when 'new' then 4
    when 'dismissed' then 5
    when 'rejected' then 6
    when 'archived' then 7
    else 9
  end;
$$;
