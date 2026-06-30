-- The applicant's own details + standard screening answers, reused to fill out
-- job applications. One row per signed-in user. The resume file itself lives in
-- a private Storage bucket; this table keeps the pointer plus (later) its parsed
-- text. This is the prerequisite for the auto-apply engine (Phase 3).
create table if not exists public.applicant_profile (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null default auth.uid(),
  full_name text not null default '',
  email text not null default '',
  phone text not null default '',
  location text not null default '',
  linkedin_url text not null default '',
  portfolio_url text not null default '',
  years_experience text not null default '',
  -- Work authorization: the two questions almost every US application asks.
  work_authorized boolean,
  requires_sponsorship boolean,
  willing_to_relocate boolean,
  earliest_start text not null default '',
  salary_expectation text not null default '',
  -- Free-form bucket for other recurring questions (pronouns, veteran status,
  -- "how did you hear about us", custom per-company answers, etc.).
  standard_answers jsonb not null default '{}'::jsonb,
  resume_path text,
  resume_filename text,
  resume_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One profile per user; lets the app upsert on created_by.
create unique index if not exists applicant_profile_user_key
  on public.applicant_profile (created_by);

drop trigger if exists touch_applicant_profile_updated_at on public.applicant_profile;
create trigger touch_applicant_profile_updated_at
before update on public.applicant_profile
for each row execute function public.touch_updated_at();

alter table public.applicant_profile enable row level security;

-- A user only ever sees and edits their own profile row.
drop policy if exists "Own profile read" on public.applicant_profile;
create policy "Own profile read"
  on public.applicant_profile for select to authenticated
  using (created_by = auth.uid());

drop policy if exists "Own profile insert" on public.applicant_profile;
create policy "Own profile insert"
  on public.applicant_profile for insert to authenticated
  with check (created_by = auth.uid());

drop policy if exists "Own profile update" on public.applicant_profile;
create policy "Own profile update"
  on public.applicant_profile for update to authenticated
  using (created_by = auth.uid()) with check (created_by = auth.uid());

-- Private bucket for resume files. Not public — served via signed URLs / the
-- service role only.
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

-- Users manage only their own files. Uploads are pathed under the user id
-- (e.g. "<uid>/resume.pdf"), so scope policies to that prefix.
drop policy if exists "Own resume read" on storage.objects;
create policy "Own resume read"
  on storage.objects for select to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "Own resume insert" on storage.objects;
create policy "Own resume insert"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "Own resume update" on storage.objects;
create policy "Own resume update"
  on storage.objects for update to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "Own resume delete" on storage.objects;
create policy "Own resume delete"
  on storage.objects for delete to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
