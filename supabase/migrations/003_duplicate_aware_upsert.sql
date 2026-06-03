create or replace function public.normalize_job_identity(value text)
returns text
language sql
immutable
as $$
  select nullif(btrim(regexp_replace(lower(coalesce(value, '')), '[^a-z0-9]+', ' ', 'g')), '');
$$;

create or replace function public.job_identity_key(company text, title text)
returns text
language sql
immutable
as $$
  select case
    when public.normalize_job_identity(company) is null
      or public.normalize_job_identity(title) is null
    then null
    else public.normalize_job_identity(company) || '|' || public.normalize_job_identity(title)
  end;
$$;

create or replace function public.job_external_ref(apply_url text)
returns text
language sql
immutable
as $$
  select case
    when lower(coalesce(apply_url, '')) ~ 'greenhouse\.io/.*/jobs/[0-9]+'
      then 'greenhouse:' || substring(lower(apply_url) from 'greenhouse\.io/.*/jobs/([0-9]+)')
    when lower(coalesce(apply_url, '')) ~ 'linkedin\.com/jobs/view/[^0-9]*[0-9]+'
      then 'linkedin:' || substring(lower(apply_url) from 'linkedin\.com/jobs/view/[^0-9]*([0-9]+)')
    when lower(coalesce(apply_url, '')) ~ 'lever\.co/.*/[0-9a-f-]{16,}'
      then 'lever:' || substring(lower(apply_url) from 'lever\.co/.*/([0-9a-f-]{16,})')
    when lower(coalesce(apply_url, '')) ~ 'workable\.com/.*/j/[a-z0-9]+'
      then 'workable:' || substring(lower(apply_url) from 'workable\.com/.*/j/([a-z0-9]+)')
    else null
  end;
$$;

create or replace function public.job_status_rank(status text)
returns integer
language sql
immutable
as $$
  select case status
    when 'next_round' then 0
    when 'applied' then 1
    when 'saved' then 2
    when 'new' then 3
    when 'dismissed' then 4
    when 'rejected' then 5
    when 'archived' then 6
    else 9
  end;
$$;

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
  item_job_id text;
  duplicate_job_id text;
  incoming_external_ref text;
  incoming_identity_key text;
begin
  for item in select * from jsonb_array_elements(payload)
  loop
    item_job_id := item->>'job_id';
    duplicate_job_id := null;
    incoming_external_ref := public.job_external_ref(item->>'apply_url');
    incoming_identity_key := public.job_identity_key(item->>'company', item->>'title');

    select j.job_id
      into duplicate_job_id
    from public.jobs j
    where j.job_id <> item_job_id
      and (
        (
          incoming_external_ref is not null
          and public.job_external_ref(j.apply_url) = incoming_external_ref
        )
        or (
          incoming_identity_key is not null
          and public.job_identity_key(j.company, j.title) = incoming_identity_key
        )
      )
    order by
      public.job_status_rank(j.status),
      case when j.source like 'getro:%' or j.source like 'consider:%' then 1 else 0 end,
      j.first_seen_at asc
    limit 1;

    if duplicate_job_id is not null then
      update public.jobs j
      set
        last_seen_at = greatest(
          j.last_seen_at,
          coalesce((item->>'last_seen_at')::timestamptz, now())
        ),
        applicability_score = greatest(
          j.applicability_score,
          coalesce((item->>'applicability_score')::integer, 0)
        ),
        raw_payload = jsonb_set(
          coalesce(j.raw_payload, '{}'::jsonb),
          '{duplicate_payloads}',
          coalesce(j.raw_payload->'duplicate_payloads', '[]'::jsonb)
            || jsonb_build_array(
              jsonb_build_object(
                'job_id', item_job_id,
                'source', item->>'source',
                'apply_url', item->>'apply_url',
                'seen_at', now()
              )
            ),
          true
        )
      where j.job_id = duplicate_job_id
      returning j.job_id into returned_job_id;

      job_id := returned_job_id;
      inserted := false;
      return next;
      continue;
    end if;

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
      item_job_id,
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

with ranked as (
  select
    j.job_id,
    first_value(j.job_id) over (
      partition by public.job_identity_key(j.company, j.title)
      order by
        public.job_status_rank(j.status),
        case when j.source like 'getro:%' or j.source like 'consider:%' then 1 else 0 end,
        j.first_seen_at asc
    ) as canonical_job_id,
    count(*) over (partition by public.job_identity_key(j.company, j.title)) as duplicate_count
  from public.jobs j
  where public.job_identity_key(j.company, j.title) is not null
)
update public.jobs j
set
  status = 'archived',
  raw_payload = jsonb_set(
    coalesce(j.raw_payload, '{}'::jsonb),
    '{archived_as_duplicate_of}',
    to_jsonb(r.canonical_job_id),
    true
  )
from ranked r
where j.job_id = r.job_id
  and r.duplicate_count > 1
  and r.job_id <> r.canonical_job_id
  and j.status <> 'archived';
