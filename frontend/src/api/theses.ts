/**
 * Thesis API client and React Query hooks
 * Stage 3: User Belief System
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios, { AxiosError } from 'axios';
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

/** Surface FastAPI `detail` when present. */
export function thesisApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<{ detail?: unknown }>;
    const detail = ax.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
      const parts = detail.map((d) => {
        if (!d || typeof d !== 'object') return String(d);
        const item = d as { loc?: unknown[]; msg?: string; message?: string };
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((x) => x !== 'body').join('.')
          : '';
        const msg = item.msg || item.message || JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      });
      return parts.join('; ');
    }
    if (detail && typeof detail === 'object') {
      try {
        return JSON.stringify(detail);
      } catch {
        /* ignore */
      }
    }
    if (ax.code === 'ECONNABORTED') return 'Request timed out — try again';
    if (ax.message) return ax.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

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
    timeout: 45_000,
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
 * Close active theses for ticker and create a replacement.
 * Uses sequential PATCH exit + POST create as the primary path so each step
 * surfaces a clear error. Tries /start-new first only as a fast path.
 */
export function useStartNewThesis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      thesis: CreateThesisRequest & { change_reason?: string }
    ) => {
      const client = await createThesisClient();
      const slimEvidence = Array.isArray(thesis.origin_evidence)
        ? thesis.origin_evidence.slice(0, 25)
        : undefined;
      const originId =
        typeof thesis.origin_analysis_id === 'number' &&
        Number.isFinite(thesis.origin_analysis_id)
          ? Math.trunc(thesis.origin_analysis_id)
          : undefined;
      const body: CreateThesisRequest & { change_reason?: string } = {
        ...thesis,
        origin_analysis_id: originId,
        origin_evidence: slimEvidence,
      };
      const reason =
        body.change_reason ||
        'Closed to start a new active thesis from the latest analysis';

      // Prefer sequential exit+create — reliable across deploys and easier to debug.
      const list = await client.get<ThesesResponse>('/api/theses', {
        params: { ticker: body.ticker.toUpperCase() },
      });
      const actives = (list.data.theses || []).filter((t) => {
        const s = (t.status || 'active').toLowerCase();
        return s === 'active' || s === 'validated';
      });
      for (const t of actives) {
        await client.patch(`/api/theses/${t.id}`, {
          status: 'exited',
          change_reason: reason,
        });
      }
      const { change_reason: _cr, ...createBody } = body;
      const { data } = await client.post<Thesis>('/api/theses', createBody);
      if (!data?.id) {
        throw new Error('Create returned empty thesis');
      }
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        thesisKeys.byTicker(data.ticker),
        (prev: ThesesResponse | undefined) => {
          const prior = prev?.theses ?? [];
          const exited = prior.map((t) =>
            t.id !== data.id &&
            ((t.status || 'active') === 'active' || t.status === 'validated')
              ? { ...t, status: 'exited' as const }
              : t
          );
          const withoutDup = exited.filter((t) => t.id !== data.id);
          return {
            theses: [data, ...withoutDup],
            count: withoutDup.length + 1,
          };
        }
      );
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

export interface AttachEvidenceResult {
  attached: boolean;
  already_attached: boolean;
  thesis: Thesis;
  row?: Record<string, unknown>;
}

/** Attach Event Study / Backtest evidence to active thesis for ticker. */
export async function attachEvidenceByTicker(
  ticker: string,
  evidence: Record<string, unknown>
): Promise<AttachEvidenceResult> {
  const client = await createThesisClient();
  const { data } = await client.post<AttachEvidenceResult>(
    '/api/theses/attach-by-ticker',
    { ticker, evidence }
  );
  return data;
}

export function useAttachEvidenceByTicker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      ticker,
      evidence,
    }: {
      ticker: string;
      evidence: Record<string, unknown>;
    }) => attachEvidenceByTicker(ticker, evidence),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['theses'] });
      queryClient.invalidateQueries({ queryKey: ['theses', vars.ticker] });
    },
  });
}

