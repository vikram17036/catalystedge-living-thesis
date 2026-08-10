-- Phase 4 fix: grants + idempotent RLS for thesis_evidence
-- Run in Supabase SQL editor if ATTACH_TO_THESIS succeeds but ATTACHED_EXPERIMENTS stays empty

grant select, insert, delete on table public.thesis_evidence to authenticated;
grant all on table public.thesis_evidence to service_role;

alter table public.thesis_evidence enable row level security;

drop policy if exists "Users select own thesis_evidence" on public.thesis_evidence;
drop policy if exists "Users insert own thesis_evidence" on public.thesis_evidence;
drop policy if exists "Users delete own thesis_evidence" on public.thesis_evidence;

create policy "Users select own thesis_evidence"
  on public.thesis_evidence for select
  using (auth.uid() = user_id);

create policy "Users insert own thesis_evidence"
  on public.thesis_evidence for insert
  with check (auth.uid() = user_id);

create policy "Users delete own thesis_evidence"
  on public.thesis_evidence for delete
  using (auth.uid() = user_id);
