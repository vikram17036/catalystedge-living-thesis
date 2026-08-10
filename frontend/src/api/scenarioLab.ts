/**
 * Scenario Lab API client (Phase 6)
 */

import axios from 'axios';
import { API_BASE_URL } from '../config/env';
import { supabase } from '../utils/supabase';

async function authHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) throw new Error('Sign in required');
  return { Authorization: `Bearer ${session.access_token}` };
}

export interface ScenarioSpec {
  ticker: string;
  kind: string;
  shock_value: number;
  shock_metric: string;
  thesis_id?: string | null;
}

export interface ScenarioCriterionOutcome {
  id: string;
  label: string;
  kind: string;
  metric?: string | null;
  detail?: string | null;
}

export interface ScenarioResult {
  spec: ScenarioSpec;
  triggered_criteria: ScenarioCriterionOutcome[];
  not_triggered_criteria: ScenarioCriterionOutcome[];
  skipped_unaffected_metric: ScenarioCriterionOutcome[];
  skipped_qualitative: ScenarioCriterionOutcome[];
  material: boolean;
  criteria_evaluated: number;
  criteria_triggered: number;
  criteria_skipped_unaffected: number;
  criteria_skipped_qualitative: number;
  reproducibility: {
    engine_version: string;
    thesis_id: string;
    thesis_version: number;
    criteria_hash: string;
    shock_metric: string;
    shock_value: number;
  };
}

export interface ScenarioResponse {
  spec: ScenarioSpec;
  spec_diff: Record<string, unknown>;
  result: ScenarioResult;
  interpretation: { summary: string; caveats?: string[] };
  evidence_ledger: Record<string, unknown>[];
  disclaimer: string;
}

export async function runScenario(
  question: string,
  priorSpec: ScenarioSpec | null = null
): Promise<ScenarioResponse> {
  const headers = await authHeaders();
  const { data } = await axios.post<ScenarioResponse>(
    `${API_BASE_URL}/api/scenario`,
    { question, prior_spec: priorSpec },
    { headers, timeout: 60_000 }
  );
  return data;
}
