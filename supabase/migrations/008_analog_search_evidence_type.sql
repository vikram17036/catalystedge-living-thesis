-- Phase 5: allow analog_search on thesis_evidence.evidence_type
-- Required for DBs that already applied 006 (CREATE TABLE IF NOT EXISTS will not alter CHECK)

alter table public.thesis_evidence
  drop constraint if exists thesis_evidence_evidence_type_check;

alter table public.thesis_evidence
  add constraint thesis_evidence_evidence_type_check
  check (evidence_type in ('event_study', 'backtest', 'analog_search'));
