-- Preserve enrichment across re-scrapes.
--
-- WHY: enrich.py fetches a real job description and writes AI summary/scores to
-- existing job rows (Getro/Consider scrapes carry NO description and NO AI data).
-- The previous upsert_jobs (migration 004) did `description_excerpt =
-- excluded.description_excerpt` and `ai_* = excluded.ai_*` on conflict — so the
-- very next nightly scrape of that job (which supplies EMPTY values) wiped the
-- enrichment. This migration rewrites upsert_jobs so the enrichment-owned fields
-- update ONLY when the incoming scrape actually provides a value; otherwise the
-- existing (enriched) value is kept.
--
-- This is a faithful copy of the migration-004 upsert_jobs with ONLY the
-- conflict-update lines for the protected fields changed (see the CASE lines
-- marked "preserve enrichment" below). If you change the insert/columns in a
-- future migration, re-copy from the latest upsert_jobs and re-apply these CASE
-- guards. Protected fields: description_excerpt, ai_summary, ai_fit_score,
-- ai_company_score, ai_reject_reasons, ai_labels, seniority_level.
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
      -- preserve enrichment: keep AI-derived seniority unless the scrape supplies one
      seniority_level = case when coalesce(excluded.seniority_level, '') <> ''
        then excluded.seniority_level else public.jobs.seniority_level end,
      compensation_min = excluded.compensation_min,
      compensation_max = excluded.compensation_max,
      -- preserve enrichment: keep AI scores unless the scrape actually supplies them
      ai_fit_score = case when excluded.ai_fit_score is not null
        then excluded.ai_fit_score else public.jobs.ai_fit_score end,
      ai_company_score = case when excluded.ai_company_score is not null
        then excluded.ai_company_score else public.jobs.ai_company_score end,
      ai_summary = case when coalesce(excluded.ai_summary, '') <> ''
        then excluded.ai_summary else public.jobs.ai_summary end,
      ai_reject_reasons = case when coalesce(array_length(excluded.ai_reject_reasons, 1), 0) > 0
        then excluded.ai_reject_reasons else public.jobs.ai_reject_reasons end,
      ai_labels = case when coalesce(array_length(excluded.ai_labels, 1), 0) > 0
        then excluded.ai_labels else public.jobs.ai_labels end,
      ranking_version = excluded.ranking_version,
      -- preserve enrichment: keep a fetched description unless the scrape has one
      description_excerpt = case when coalesce(excluded.description_excerpt, '') <> ''
        then excluded.description_excerpt else public.jobs.description_excerpt end,
      raw_payload = excluded.raw_payload
    returning (xmax = 0), public.jobs.job_id into was_inserted, returned_job_id;

    job_id := returned_job_id;
    inserted := was_inserted;
    return next;
  end loop;
end;
$$;
