/**
 * Strategy Lab / backtest API client
 */
import axios from 'axios';
import { supabase } from '../utils/supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function authHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

export interface StrategySpec {
  ticker: string;
  kind: string;
  strategy: { fast_window: number; slow_window: number };
  start: string;
  end?: string | null;
  commission_bps: number;
  slippage_bps: number;
  initial_cash: number;
  price_mode: string;
}

export interface BacktestResult {
  spec: StrategySpec;
  trades: Record<string, unknown>[];
  equity_curve: { date: string; equity: number; in_position: boolean; cash: number }[];
  metrics: {
    total_return: number;
    gross_return: number;
    commission_only_return: number;
    commission_impact: number;
    slippage_impact: number;
    max_drawdown: number;
    hit_rate: number | null;
    n_trades: number;
  };
  reproducibility: {
    engine_version: string;
    price_data_hash: string;
    price_mode: string;
  };
}

export interface BacktestResponse {
  prior_spec: StrategySpec | null;
  spec: StrategySpec;
  spec_diff: Record<string, unknown>;
  mode: string;
  result: BacktestResult;
  interpretation: {
    mode: string;
    summary: string;
    caveats: string[];
  };
  evidence_ledger: Record<string, unknown>[];
}

export async function runBacktest(
  question: string,
  priorSpec: StrategySpec | null = null,
  priorResult: BacktestResult | null = null
): Promise<BacktestResponse> {
  const headers = await authHeaders();
  if (!headers.Authorization) throw new Error('Sign in required for Strategy Lab.');
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json', ...headers },
    timeout: 180000,
  });
  const { data } = await client.post<BacktestResponse>('/api/backtest', {
    question,
    prior_spec: priorSpec,
    prior_result: priorResult,
  });
  return data;
}
