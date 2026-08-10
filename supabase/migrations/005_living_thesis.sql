-- Living Thesis Phase 0: single alerts model + replay support
-- Run in YOUR Supabase SQL editor after base schema + migrations 001-004

-- Unified alerts table (API, scheduler, replay, dashboard)
create table if not exists public.thesis_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  thesis_id uuid not null references public.theses(id) on delete cascade,
  ticker text not null,
  severity text not null default 'warning'
    check (severity in ('info', 'warning', 'critical')),
  status text not null default 'unread'
    check (status in ('unread', 'read', 'acknowledged', 'dismissed')),
  title text not null,
  message text not null,
  triggered_criteria jsonb not null default '[]'::jsonb,
  diff jsonb,
  evidence_ids jsonb not null default '[]'::jsonb,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_thesis_alerts_user on public.thesis_alerts(user_id);
create index if not exists idx_thesis_alerts_thesis on public.thesis_alerts(thesis_id);
create index if not exists idx_thesis_alerts_status on public.thesis_alerts(user_id, status);

alter table public.thesis_alerts enable row level security;

create policy "Users select own thesis_alerts"
  on public.thesis_alerts for select
  using (auth.uid() = user_id);

create policy "Users update own thesis_alerts"
  on public.thesis_alerts for update
  using (auth.uid() = user_id);

create policy "Users delete own thesis_alerts"
  on public.thesis_alerts for delete
  using (auth.uid() = user_id);

-- Service role inserts alerts from scheduler / replay (bypasses RLS)

-- Structured origin snapshot + version on theses (idempotent)
alter table public.theses
  add column if not exists origin_evidence jsonb default '[]'::jsonb;

alter table public.theses
  add column if not exists structured_kill_criteria jsonb default '[]'::jsonb;

alter table public.theses
  add column if not exists thesis_version int default 1;

-- Replay fixtures (demo + tests) — not user-facing RLS required for service role
create table if not exists public.replay_snapshots (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  label text not null,
  as_of timestamptz not null,
  evidence jsonb not null default '[]'::jsonb,
  analysis_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_replay_snapshots_ticker on public.replay_snapshots(ticker);
