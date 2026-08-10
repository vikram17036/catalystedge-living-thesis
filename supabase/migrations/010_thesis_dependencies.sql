-- Phase 6: thesis dependency graph (supporting infra)

create table if not exists public.thesis_dependencies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  from_thesis_id uuid not null references public.theses(id) on delete cascade,
  to_thesis_id uuid not null references public.theses(id) on delete cascade,
  link_type text not null
    check (link_type in ('depends_on', 'related_ticker', 'shared_kill_metric')),
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (from_thesis_id, to_thesis_id, link_type),
  check (from_thesis_id <> to_thesis_id)
);

create index if not exists idx_thesis_deps_user on public.thesis_dependencies(user_id);
create index if not exists idx_thesis_deps_from on public.thesis_dependencies(from_thesis_id);
create index if not exists idx_thesis_deps_to on public.thesis_dependencies(to_thesis_id);

alter table public.thesis_dependencies enable row level security;

drop policy if exists "Users select own thesis_dependencies" on public.thesis_dependencies;
drop policy if exists "Users insert own thesis_dependencies" on public.thesis_dependencies;
drop policy if exists "Users delete own thesis_dependencies" on public.thesis_dependencies;

create policy "Users select own thesis_dependencies"
  on public.thesis_dependencies for select
  using (auth.uid() = user_id);

create policy "Users insert own thesis_dependencies"
  on public.thesis_dependencies for insert
  with check (auth.uid() = user_id);

create policy "Users delete own thesis_dependencies"
  on public.thesis_dependencies for delete
  using (auth.uid() = user_id);

grant select, insert, delete on table public.thesis_dependencies to authenticated;
grant all on table public.thesis_dependencies to service_role;
