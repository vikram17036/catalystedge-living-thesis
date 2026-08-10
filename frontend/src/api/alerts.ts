/**
 * Alerts API client — prefers backend /api/kill-alerts (thesis_alerts).
 */

import axios from 'axios';
import { supabase } from '../utils/supabase';
import type { KillAlert } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

export async function fetchKillAlerts(
  ticker?: string,
  status: string = 'pending'
): Promise<KillAlert[]> {
  const headers = await authHeaders();
  if (!('Authorization' in headers)) return [];

  const { data } = await axios.get<{ alerts: KillAlert[] }>(`${API_BASE_URL}/api/kill-alerts`, {
    headers,
    params: {
      ...(ticker ? { ticker: ticker.toUpperCase() } : {}),
      status,
    },
  });
  return data.alerts || [];
}

export async function updateKillAlertStatus(
  alertId: string,
  status: string
): Promise<void> {
  const headers = await authHeaders();
  await axios.patch(
    `${API_BASE_URL}/api/kill-alerts/${alertId}`,
    { status },
    { headers }
  );
}
