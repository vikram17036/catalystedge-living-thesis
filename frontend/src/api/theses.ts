/**
 * Thesis API client and React Query hooks
 * Stage 3: User Belief System
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import type { 
  Thesis, 
  ThesesResponse, 
  CreateThesisRequest, 
  UpdateThesisRequest,
  ThesisHistoryResponse,
  ThesisComparison,
  AnalysisSnapshot,
} from '../types/thesis';
import { supabase } from '../utils/supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * Get authorization header with current session token
 */
async function getAuthHeader(): Promise<{ Authorization: string } | {}> {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

/**
 * Create axios instance for thesis API
 */
const createThesisClient = async () => {
  const headers = await getAuthHeader();
  return axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  });
};

// Query keys
export const thesisKeys = {
  all: ['theses'] as const,
  byTicker: (ticker: string) => ['theses', ticker.toUpperCase()] as const,
  history: (thesisId: string) => ['thesis-history', thesisId] as const,
};

/**
 * Hook to fetch all user theses
 */
export function useTheses(ticker?: string) {
  return useQuery({
    queryKey: ticker ? thesisKeys.byTicker(ticker) : thesisKeys.all,
    queryFn: async () => {
      const client = await createThesisClient();
      const params = ticker ? { ticker: ticker.toUpperCase() } : {};
      const { data } = await client.get<ThesesResponse>('/api/theses', { params });
      return data;
    },
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
}

/**
 * Hook to check if user has thesis for a specific ticker
 */
export function useThesisForTicker(ticker: string | null) {
  return useQuery({
    queryKey: thesisKeys.byTicker(ticker || ''),
    queryFn: async () => {
      if (!ticker) return { theses: [], count: 0 };
      const client = await createThesisClient();
      const { data } = await client.get<ThesesResponse>('/api/theses', { 
        params: { ticker: ticker.toUpperCase() } 
      });
      return data;
    },
    enabled: !!ticker,
    staleTime: 1000 * 60 * 2,
  });
}

/**
 * Hook to create a new thesis
 */
export function useCreateThesis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (thesis: CreateThesisRequest) => {
      const client = await createThesisClient();
      const { data } = await client.post<Thesis>('/api/theses', thesis);
      return data;
    },
    onSuccess: (data) => {
      // Invalidate queries to refetch
      queryClient.invalidateQueries({ queryKey: thesisKeys.all });
      queryClient.invalidateQueries({ queryKey: thesisKeys.byTicker(data.ticker) });
    },
  });
}

/**
 * Hook to update a thesis
 */
export function useUpdateThesis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ thesisId, updates }: { thesisId: string; updates: UpdateThesisRequest }) => {
      const client = await createThesisClient();
      const { data } = await client.patch<Thesis>(`/api/theses/${thesisId}`, updates);
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: thesisKeys.all });
      queryClient.invalidateQueries({ queryKey: thesisKeys.byTicker(data.ticker) });
    },
  });
}

/**
 * Hook to get thesis history
 */
export function useThesisHistory(thesisId: string | null) {
  return useQuery({
    queryKey: thesisKeys.history(thesisId || ''),
    queryFn: async () => {
      if (!thesisId) return { history: [], count: 0 };
      const client = await createThesisClient();
      const { data } = await client.get<ThesisHistoryResponse>(`/api/theses/${thesisId}/history`);
      return data;
    },
    enabled: !!thesisId,
  });
}

/**
 * Hook to compare thesis with current analysis (Stage 4 / Phase 1)
 */
export function useThesisComparison(thesisId: string | null) {
  return useQuery({
    queryKey: ['thesis-comparison', thesisId],
    queryFn: async () => {
      if (!thesisId) return null;
      const client = await createThesisClient();
      const { data } = await client.get<ThesisComparison>(`/api/theses/${thesisId}/compare`);
      return data;
    },
    enabled: !!thesisId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Hook to replay an adverse (or labeled) scenario against a thesis
 */
export function useReplayThesis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      thesisId,
      label = 'adverse_shock',
      createAlert = true,
    }: {
      thesisId: string;
      label?: string;
      createAlert?: boolean;
    }) => {
      const client = await createThesisClient();
      const { data } = await client.post<ThesisComparison>(
        `/api/theses/${thesisId}/replay`,
        { label, create_alert: createAlert }
      );
      return data;
    },
    onSuccess: (data) => {
      if (data?.thesis_id) {
        queryClient.invalidateQueries({ queryKey: ['thesis-comparison', data.thesis_id] });
        queryClient.invalidateQueries({ queryKey: ['kill-alerts'] });
      }
    },
  });
}

export interface ThesisProposal {
  ticker: string;
  thesis_summary: string;
  conviction_level: 'low' | 'medium' | 'high';
  kill_criteria: string[];
  structured_kill_criteria?: Record<string, unknown>[];
  origin_analysis_snapshot?: AnalysisSnapshot;
  origin_evidence?: Record<string, unknown>[];
  origin_analysis_id?: number;
  assumptions?: Record<string, unknown>[];
}

/**
 * Propose thesis structure from analysis (not persisted)
 */
export function useProposeThesisFromAnalysis() {
  return useMutation({
    mutationFn: async (payload: {
      ticker: string;
      analysis?: Record<string, unknown>;
    }) => {
      const client = await createThesisClient();
      const { data } = await client.post<{ proposal: ThesisProposal; persisted: boolean }>(
        '/api/theses/from-analysis',
        {
          ticker: payload.ticker,
          analysis: payload.analysis,
          use_cache: !payload.analysis,
        }
      );
      return data.proposal;
    },
  });
}

export function useEvaluateThesis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      thesisId,
      createAlert = true,
    }: {
      thesisId: string;
      createAlert?: boolean;
    }) => {
      const client = await createThesisClient();
      const { data } = await client.post<ThesisComparison>(
        `/api/theses/${thesisId}/evaluate`,
        { create_alert: createAlert }
      );
      return data;
    },
    onSuccess: (data) => {
      if (data?.thesis_id) {
        queryClient.invalidateQueries({ queryKey: ['thesis-comparison', data.thesis_id] });
        queryClient.invalidateQueries({ queryKey: ['kill-alerts'] });
      }
    },
  });
}

