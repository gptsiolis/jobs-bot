-- Autonomous apply agent: track the outcome of an automated submission and keep
-- a confirmation screenshot for audit. Extends the existing application_drafts
-- state machine (… → submitting → submitted | failed | needs_review(flagged)).
alter table public.application_drafts
  add column if not exists submitted_at timestamptz;

alter table public.application_drafts
  add column if not exists confirmation_path text;

-- Why a draft was flagged instead of auto-submitted (captcha, login wall,
-- missing required field, non-auto-submit ATS, etc.).
alter table public.application_drafts
  add column if not exists flag_reason text;

-- Private bucket for confirmation / flagged-state screenshots the agent captures.
insert into storage.buckets (id, name, public)
values ('applications', 'applications', false)
on conflict (id) do nothing;

-- Files are pathed under the user id ("<uid>/<draft>.png"); scope to that prefix.
drop policy if exists "Own application shots read" on storage.objects;
create policy "Own application shots read"
  on storage.objects for select to authenticated
  using (bucket_id = 'applications' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "Own application shots write" on storage.objects;
create policy "Own application shots write"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'applications' and (storage.foldername(name))[1] = auth.uid()::text);
