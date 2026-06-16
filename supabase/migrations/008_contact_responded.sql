-- Whether the contact reached out to (for an applied_messaged job) has replied.
alter table public.jobs
  add column if not exists contact_responded boolean not null default false;
