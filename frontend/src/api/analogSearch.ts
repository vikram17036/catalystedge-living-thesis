/**
 * Historical Analog Search API client (Phase 5)
 */

import axios from 'axios';
import { API_BASE_URL } from '../config/env';
import { supabase } from '../utils/supabase';

async function getAuthHeader(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) {
    throw new Error('Sign in required');
  }
  return { Authorization: `Bearer ${session.access_token}` };
}

export interface AnalogSpec {
  ticker: string;
  lookback: number;
  post_window: number;
  top_k: number;
  as_of?: string | null;
}

export interface AnalogMatch {
  endpoint: string;
  lookback_start: string;
  lookback_end: string;
  distance: number;
  forward_return: number;
}

export interface AnalogResult {
  spec: AnalogSpec;
  candidate_windows: number;
  eligible_windows: number;
  matches_returned: number;
  excluded_overlap: number;
  excluded_future_coverage: number;
  excluded_lookahead: number;
  forward_mean: number | null;
  forward_median: number | null;
  positive_hit_rate: number | null;
  matches: AnalogMatch[];
  reproducibility: {
    engine_version: string;
    price_data_hash: string;
    target_end: string;
    as_of?: string | null;
    lookback: number;
    post_window: number;
    top_k: number;
  };
}

export interface AnalogSearchResponse {
  prior_spec: AnalogSpec | null;
  spec: AnalogSpec;
  spec_diff: Record<string, unknown>;
  result: AnalogResult;
  interpretation: {
    mode: string;
    summary: string;
    caveats?: string[];
  };
  evidence_ledger: Record<string, unknown>[];
}

export async function runAnalogSearch(
  question: string,
  priorSpec: AnalogSpec | null = null
): Promise<AnalogSearchResponse> {
  const headers = await getAuthHeader();
  const { data } = await axios.post<AnalogSearchResponse>(
    `${API_BASE_URL}/api/analog-search`,
    { question, prior_spec: priorSpec },
    { headers, timeout: 120_000 }
  );
  return data;
}
