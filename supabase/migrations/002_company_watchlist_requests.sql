create table if not exists public.company_watchlist_requests (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  normalized_name text not null,
  status text not null default 'pending',
  ats_config jsonb,
  sector text not null default 'user_added',
  quality_tier text not null default 'acceptable',
  sponsor_tier text not null default 'unknown_no_ban',
  source_notes text not null default 'Added from dashboard',
  last_checked_at timestamptz,
  last_error text,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint company_watchlist_requests_status_check check (
    status in ('pending', 'resolved', 'unresolved', 'disabled')
  )
);

create unique index if not exists company_watchlist_requests_normalized_idx
  on public.company_watchlist_requests(normalized_name);
create index if not exists company_watchlist_requests_status_idx
  on public.company_watchlist_requests(status, updated_at desc);

drop trigger if exists touch_company_watchlist_requests_updated_at
  on public.company_watchlist_requests;
create trigger touch_company_watchlist_requests_updated_at
before update on public.company_watchlist_requests
for each row execute function public.touch_updated_at();

alter table public.company_watchlist_requests enable row level security;

drop policy if exists "Authenticated users can read company watchlist requests"
  on public.company_watchlist_requests;
create policy "Authenticated users can read company watchlist requests"
on public.company_watchlist_requests for select
to authenticated
using (true);

drop policy if exists "Authenticated users can insert company watchlist requests"
  on public.company_watchlist_requests;
create policy "Authenticated users can insert company watchlist requests"
on public.company_watchlist_requests for insert
to authenticated
with check (created_by = auth.uid());

drop policy if exists "Authenticated users can update company watchlist requests"
  on public.company_watchlist_requests;
create policy "Authenticated users can update company watchlist requests"
on public.company_watchlist_requests for update
to authenticated
using (true)
with check (true);
