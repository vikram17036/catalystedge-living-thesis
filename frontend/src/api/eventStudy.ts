/**
 * Event Study / Research API client
 */

import axios from 'axios';
import { supabase } from '../utils/supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function getAuthHeader(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

export interface EventStudySpec {
  ticker: string;
  event_source: string;
  event_filter: string;
  pre_window: number;
  post_window: number;
  metric: string;
  calendar_id: string;
  as_of?: string | null;
}

export interface WindowStats {
  mean: number | null;
  median: number | null;
  positive_rate: number | null;
  n: number;
}

export interface EventObservation {
  event_date: string;
  classification: string;
  pre_return: number;
  event_return: number;
  post_return: number;
  cumulative_window_return: number;
}

export interface EventStudyResult {
  spec: EventStudySpec;
  calendar_events: number;
  eligible_events: number;
  events_analyzed: number;
  excluded_events: number;
  exclusions: { date: string; reason: string }[];
  pre_stats: WindowStats;
  event_stats: WindowStats;
  post_stats: WindowStats;
  observations: EventObservation[];
  reproducibility: {
    calendar_id: string;
    engine_version: string;
    price_source: string;
    price_mode: string;
    price_start?: string | null;
    price_end?: string | null;
    price_data_hash: string;
    as_of?: string | null;
  };
}

export interface EventStudyResponse {
  prior_spec: EventStudySpec | null;
  spec: EventStudySpec;
  spec_diff: Record<string, unknown>;
  result: EventStudyResult;
  interpretation: {
    mode: string;
    summary: string;
    observations: { text: string; evidence_id: string; metrics: string[] }[];
    caveats: string[];
  };
  evidence_ledger: Record<string, unknown>[];
}

export async function runEventStudy(
  question: string,
  priorSpec: EventStudySpec | null = null,
  useLlm = true
): Promise<EventStudyResponse> {
  const headers = await getAuthHeader();
  if (!headers.Authorization) {
    throw new Error('Sign in required to run event studies.');
  }
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json', ...headers },
    timeout: 180000,
  });
  const { data } = await client.post<EventStudyResponse>('/api/event-study', {
    question,
    prior_spec: priorSpec,
    use_llm: useLlm,
  });
  return data;
}
