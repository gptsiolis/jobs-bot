-- People you've reached out to on LinkedIn, tracked per company. A single
-- application/messaging flow can involve several people at the same company:
-- if the first contact never replies, you message someone else and keep a
-- record of everyone already tried. Each row is one person at one company.
create table if not exists public.company_contacts (
  id uuid primary key default gen_random_uuid(),
  company text not null,
  contact_name text,
  linkedin_url text not null,
  responded boolean not null default false,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now()
);

-- Don't let the same person be added twice for a company.
create unique index if not exists company_contacts_company_url_key
  on public.company_contacts (company, linkedin_url);

-- Lookups are always "give me everyone at this company".
create index if not exists company_contacts_company_idx
  on public.company_contacts (company);

alter table public.company_contacts enable row level security;

drop policy if exists "Authenticated read company contacts" on public.company_contacts;
create policy "Authenticated read company contacts"
  on public.company_contacts for select to authenticated using (true);

drop policy if exists "Authenticated insert company contacts" on public.company_contacts;
create policy "Authenticated insert company contacts"
  on public.company_contacts for insert to authenticated with check (true);

drop policy if exists "Authenticated update company contacts" on public.company_contacts;
create policy "Authenticated update company contacts"
  on public.company_contacts for update to authenticated using (true) with check (true);

drop policy if exists "Authenticated delete company contacts" on public.company_contacts;
create policy "Authenticated delete company contacts"
  on public.company_contacts for delete to authenticated using (true);
