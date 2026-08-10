-- Phase 4: attached research evidence (separate from frozen origin_evidence)
-- Run in Supabase SQL editor after 005_living_thesis.sql

create table if not exists public.thesis_evidence (
  id uuid primary key default gen_random_uuid(),
  thesis_id uuid not null references public.theses(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  evidence_id text not null,
  evidence_type text not null
    check (evidence_type in ('event_study', 'backtest')),
  evidence jsonb not null,
  attached_at timestamptz not null default now(),
  unique (thesis_id, evidence_id)
);

create index if not exists idx_thesis_evidence_thesis on public.thesis_evidence(thesis_id);
create index if not exists idx_thesis_evidence_user on public.thesis_evidence(user_id);

alter table public.thesis_evidence enable row level security;

create policy "Users select own thesis_evidence"
  on public.thesis_evidence for select
  using (auth.uid() = user_id);

create policy "Users insert own thesis_evidence"
  on public.thesis_evidence for insert
  with check (auth.uid() = user_id);

create policy "Users delete own thesis_evidence"
  on public.thesis_evidence for delete
  using (auth.uid() = user_id);

grant select, insert, delete on table public.thesis_evidence to authenticated;
grant all on table public.thesis_evidence to service_role;
