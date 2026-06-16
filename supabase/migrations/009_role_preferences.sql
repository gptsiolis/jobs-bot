-- Editable role title/keyword preferences, so "what I'm looking for" can be
-- managed from the site instead of config.py. Each row is one keyword in one
-- family; family maps to a priority tier in config.py:
--   operations_strategy -> tier 1 (priority)
--   early_career        -> tier 2
--   business_development -> tier 3
create table if not exists public.role_preferences (
  id uuid primary key default gen_random_uuid(),
  keyword text not null,
  family text not null,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  constraint role_preferences_family_check check (
    family in ('operations_strategy', 'business_development', 'early_career')
  )
);

create unique index if not exists role_preferences_keyword_key
  on public.role_preferences (lower(keyword));

alter table public.role_preferences enable row level security;

drop policy if exists "Authenticated read role preferences" on public.role_preferences;
create policy "Authenticated read role preferences"
  on public.role_preferences for select to authenticated using (true);

drop policy if exists "Authenticated insert role preferences" on public.role_preferences;
create policy "Authenticated insert role preferences"
  on public.role_preferences for insert to authenticated with check (true);

drop policy if exists "Authenticated delete role preferences" on public.role_preferences;
create policy "Authenticated delete role preferences"
  on public.role_preferences for delete to authenticated using (true);

-- Seed from the current config.py ROLE_TIERS so the UI starts populated.
insert into public.role_preferences (keyword, family) values
  ('chief of staff', 'operations_strategy'),
  ('founder''s associate', 'operations_strategy'),
  ('founders associate', 'operations_strategy'),
  ('founder associate', 'operations_strategy'),
  ('business operations', 'operations_strategy'),
  ('business operations associate', 'operations_strategy'),
  ('business operations analyst', 'operations_strategy'),
  ('business operations coordinator', 'operations_strategy'),
  ('operations associate', 'operations_strategy'),
  ('operations analyst', 'operations_strategy'),
  ('operations coordinator', 'operations_strategy'),
  ('strategy and operations', 'operations_strategy'),
  ('strategy & operations', 'operations_strategy'),
  ('strategy operations', 'operations_strategy'),
  ('strategy associate', 'operations_strategy'),
  ('strategy analyst', 'operations_strategy'),
  ('revenue operations', 'operations_strategy'),
  ('revenue operations associate', 'operations_strategy'),
  ('revenue operations analyst', 'operations_strategy'),
  ('special projects associate', 'operations_strategy'),
  ('special projects', 'operations_strategy'),
  ('program associate', 'operations_strategy'),
  ('program coordinator', 'operations_strategy'),
  ('operations', 'operations_strategy'),
  ('strategy', 'operations_strategy'),
  ('new grad', 'early_career'),
  ('new graduate', 'early_career'),
  ('recent graduate', 'early_career'),
  ('early career', 'early_career'),
  ('entry level', 'early_career'),
  ('entry-level', 'early_career'),
  ('rotational', 'early_career'),
  ('graduate program', 'early_career'),
  ('analyst program', 'early_career'),
  ('associate program', 'early_career'),
  ('business development associate', 'business_development'),
  ('business development analyst', 'business_development'),
  ('business development representative', 'business_development'),
  ('sales development representative', 'business_development'),
  ('account executive', 'business_development'),
  ('sales associate', 'business_development'),
  ('sales representative', 'business_development'),
  ('customer success associate', 'business_development'),
  ('partnerships associate', 'business_development'),
  ('partnerships analyst', 'business_development'),
  ('partner development associate', 'business_development'),
  ('growth associate', 'business_development'),
  ('growth analyst', 'business_development'),
  ('investment analyst', 'business_development'),
  ('investment associate', 'business_development'),
  ('acquisitions analyst', 'business_development'),
  ('acquisitions associate', 'business_development'),
  ('acquisitions - analyst', 'business_development'),
  ('asset management analyst', 'business_development'),
  ('asset management associate', 'business_development'),
  ('business development', 'business_development'),
  ('partnerships', 'business_development'),
  ('growth', 'business_development')
on conflict (lower(keyword)) do nothing;
