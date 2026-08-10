/**
 * Thesis dependency graph API (dedicated routes)
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

export interface GraphNode {
  id: string;
  ticker: string;
  thesis_summary: string;
  status?: string;
}

export interface GraphEdge {
  id: string;
  from_thesis_id: string;
  to_thesis_id: string;
  link_type: string;
}

export async function fetchThesisGraph(ticker?: string) {
  const headers = await authHeaders();
  const { data } = await axios.get<{
    nodes: GraphNode[];
    edges: GraphEdge[];
  }>(`${API_BASE_URL}/api/thesis-graph`, {
    headers,
    params: ticker ? { ticker } : {},
  });
  return data;
}

export async function createDependency(body: {
  from_thesis_id: string;
  to_thesis_id: string;
  link_type: string;
}) {
  const headers = await authHeaders();
  const { data } = await axios.post(`${API_BASE_URL}/api/thesis-dependencies`, body, {
    headers,
  });
  return data;
}

export async function deleteDependency(id: string) {
  const headers = await authHeaders();
  await axios.delete(`${API_BASE_URL}/api/thesis-dependencies/${id}`, { headers });
}
