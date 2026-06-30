-- Extra profile fields surfaced by feedback while filling out the intake:
--  * github_url  — several applications ask for it directly.
--  * minimum_salary — a hard floor that the auto-apply engine uses to SKIP
--    jobs paying below it. Distinct from salary_expectation (what we write on a
--    form when asked); this one decides whether we apply at all.
alter table public.applicant_profile
  add column if not exists github_url text not null default '';

alter table public.applicant_profile
  add column if not exists minimum_salary integer;
