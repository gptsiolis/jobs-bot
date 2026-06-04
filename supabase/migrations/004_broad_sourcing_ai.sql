alter table public.jobs add column if not exists visibility text not null default 'default';
alter table public.jobs add column if not exists role_family text not null default '';
alter table public.jobs add column if not exists seniority_level text not null default '';
alter table public.jobs add column if not exists compensation_min integer;
alter table public.jobs add column if not exists compensation_max integer;
alter table public.jobs add column if not exists ai_fit_score integer;
alter table public.jobs add column if not exists ai_company_score integer;
alter table public.jobs add column if not exists ai_summary text not null default '';
alter table public.jobs add column if not exists ai_reject_reasons text[] not null default '{}';
alter table public.jobs add column if not exists ai_labels text[] not null default '{}';
alter table public.jobs add column if not exists ranking_version text not null default 'deterministic-v1';

alter table public.jobs drop constraint if exists jobs_visibility_check;
alter table public.jobs add constraint jobs_visibility_check check (
  visibility in ('default', 'hidden', 'needs_review')
);

create index if not exists jobs_visibility_score_idx
  on public.jobs(visibility, applicability_score desc, last_seen_at desc);
create index if not exists jobs_role_family_idx on public.jobs(role_family);

create table if not exists public.company_leads (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  normalized_name text not null,
  first_source text not null default '',
  example_job_ids text[] not null default '{}',
  lead_score integer not null default 0,
  status text not null default 'new',
  resolver_result jsonb,
  last_seen_at timestamptz not null default now(),
  last_checked_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint company_leads_status_check check (
    status in ('new', 'promoted', 'resolved', 'unresolved', 'dismissed')
  )
);

create unique index if not exists company_leads_normalized_idx
  on public.company_leads(normalized_name);
create index if not exists company_leads_status_score_idx
  on public.company_leads(status, lead_score desc, last_seen_at desc);

drop trigger if exists touch_company_leads_updated_at on public.company_leads;
create trigger touch_company_leads_updated_at
before update on public.company_leads
for each row execute function public.touch_updated_at();

alter table public.company_leads enable row level security;

drop policy if exists "Authenticated users can read company leads" on public.company_leads;
create policy "Authenticated users can read company leads"
on public.company_leads for select
to authenticated
using (true);

drop policy if exists "Authenticated users can update company leads" on public.company_leads;
create policy "Authenticated users can update company leads"
on public.company_leads for update
to authenticated
using (true)
with check (true);

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
      job_id, title, company, location_text, apply_url, source, ats,
      first_seen_at, last_seen_at, fit_bucket, fit_reasons, sponsor_tier,
      sponsor_reasons, quality_tier, sector, applicability_score, status,
      visibility, role_family, seniority_level, compensation_min,
      compensation_max, ai_fit_score, ai_company_score, ai_summary,
      ai_reject_reasons, ai_labels, ranking_version, description_excerpt,
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
      coalesce(item->>'visibility', 'default'),
      coalesce(item->>'role_family', ''),
      coalesce(item->>'seniority_level', ''),
      nullif(item->>'compensation_min', '')::integer,
      nullif(item->>'compensation_max', '')::integer,
      nullif(item->>'ai_fit_score', '')::integer,
      nullif(item->>'ai_company_score', '')::integer,
      coalesce(item->>'ai_summary', ''),
      coalesce(array(select jsonb_array_elements_text(item->'ai_reject_reasons')), '{}'),
      coalesce(array(select jsonb_array_elements_text(item->'ai_labels')), '{}'),
      coalesce(item->>'ranking_version', 'deterministic-v2'),
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
      visibility = excluded.visibility,
      role_family = excluded.role_family,
      seniority_level = excluded.seniority_level,
      compensation_min = excluded.compensation_min,
      compensation_max = excluded.compensation_max,
      ai_fit_score = excluded.ai_fit_score,
      ai_company_score = excluded.ai_company_score,
      ai_summary = excluded.ai_summary,
      ai_reject_reasons = excluded.ai_reject_reasons,
      ai_labels = excluded.ai_labels,
      ranking_version = excluded.ranking_version,
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
