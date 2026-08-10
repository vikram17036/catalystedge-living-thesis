/**
 * Research Agent API client (Phase 7/8)
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

export interface ResearchTrace {
  trace_version?: string;
  run_id?: string;
  thread_id?: string;
  latency_ms_total?: number;
  intent?: string;
  write_intent?: boolean;
  ticker?: string | null;
  thesis_id?: string | null;
  research_tools_selected?: string[];
  support_tools_used?: string[];
  write_tools_used?: string[];
  not_selected?: string[];
  tools_selected?: string[];
  scenario_shock?: number | null;
  memory?: { available?: boolean; records?: number; error?: string | null };
  tool_errors?: { tool?: string; error_code?: string; message?: string }[];
  engine_repro?: {
    tool?: string;
    engine_version?: string;
    criteria_hash?: string;
    price_data_hash?: string;
  }[];
  citations_validated?: number;
  citations_total?: number;
  writes?: number;
  pending_attach?: unknown;
  nodes?: { name?: string; ok?: boolean; latency_ms?: number; note?: string }[];
}

export interface ResearchAgentResponse {
  run_id?: string;
  thread_id: string;
  answer: string;
  ticker?: string | null;
  thesis_id?: string | null;
  research_plan?: {
    tools?: string[];
    research_tools_selected?: string[];
    support_tools_used?: string[];
    write_tools_used?: string[];
    not_selected?: string[];
    scenario_shock?: number | null;
  };
  trace?: ResearchTrace;
  citations?: {
    id?: string;
    source_type?: string;
    source_id?: string;
    hypothetical?: boolean;
    validated?: boolean;
  }[];
  memory_available?: boolean;
  memory_error?: string | null;
  writes?: number;
  pending_attach?: unknown;
  tool_results?: Record<string, unknown>;
  prior_specs?: Record<string, unknown>;
}

export interface ReindexResponse {
  sources_indexed?: number;
  chunks_indexed?: number;
  indexed_vectors?: number;
  theses?: number;
  errors?: string[];
  ok?: boolean;
}

export async function runResearchAgent(
  message: string,
  opts?: { thread_id?: string | null; ticker?: string | null; thesis_id?: string | null }
): Promise<ResearchAgentResponse> {
  const headers = await authHeaders();
  const { data } = await axios.post(
    `${API_BASE_URL}/api/research-agent`,
    {
      message,
      thread_id: opts?.thread_id || undefined,
      ticker: opts?.ticker || undefined,
      thesis_id: opts?.thesis_id || undefined,
    },
    { headers }
  );
  return data;
}

export async function reindexResearchMemory(
  ticker?: string
): Promise<ReindexResponse> {
  const headers = await authHeaders();
  const { data } = await axios.post(
    `${API_BASE_URL}/api/research-memory/reindex`,
    null,
    { headers, params: ticker ? { ticker } : undefined }
  );
  return data;
}
