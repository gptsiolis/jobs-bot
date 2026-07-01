-- Postal / ZIP code — a required field on many applications (e.g. Greenhouse).
-- Kept as its own column so the apply agent can fill it truthfully instead of
-- flagging the job.
alter table public.applicant_profile
  add column if not exists postal_code text not null default '';
