-- Phase 6: allow scenario on thesis_evidence.evidence_type

alter table public.thesis_evidence
  drop constraint if exists thesis_evidence_evidence_type_check;

alter table public.thesis_evidence
  add constraint thesis_evidence_evidence_type_check
  check (evidence_type in ('event_study', 'backtest', 'analog_search', 'scenario'));
