import { useState, useEffect, useCallback } from 'react';
import { Bell, CheckSquare, Clock, ShieldAlert } from 'lucide-react';
import { Button } from './ui/button';
import { fetchKillAlerts, updateKillAlertStatus } from '../api/alerts';
import { useAuth } from '../context/AuthContext';
import { cn } from '../utils/cn';
import type { KillAlert } from '../types/api';

interface DisplayAlert {
  id: string;
  thesis_id: string;
  ticker: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export default function AlertsCenter() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<DisplayAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unread'>('unread');

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    if (!user) {
      setAlerts([]);
      setLoading(false);
      return;
    }

    try {
      const raw = await fetchKillAlerts(undefined, filter === 'unread' ? 'pending' : 'all');
      const list = (raw || []).map((a: KillAlert & { message?: string }) => ({
        id: a.id,
        thesis_id: a.thesis_id,
        ticker: a.ticker,
        message: a.message || a.triggered_criteria || a.triggering_signal || 'Thesis alert',
        is_read: a.status !== 'pending' && a.status !== 'unread',
        created_at: a.created_at,
      }));
      setAlerts(list);
    } catch {
      setAlerts([]);
    }
    setLoading(false);
  }, [user, filter]);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const markAsRead = async (id: string) => {
    try {
      await updateKillAlertStatus(id, 'acknowledged');
    } catch {
      /* ignore */
    }
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
    if (filter === 'unread') {
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    }
  };

  const markAllRead = async () => {
    await Promise.all(alerts.filter((a) => !a.is_read).map((a) => markAsRead(a.id)));
    fetchAlerts();
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between border-b border-border-base pb-4 gap-4">
        <div>
          <h2 className="text-2xl font-mono font-bold tracking-tight text-txt-primary">SYS_ALERTS</h2>
          <p className="text-micro font-mono text-txt-muted uppercase tracking-widest mt-1">
            Living thesis monitor signals
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex bg-surface-1 border border-border-base p-0.5 rounded-sm">
            <button
              onClick={() => setFilter('unread')}
              className={cn(
                'px-4 py-1.5 text-micro font-mono uppercase tracking-widest transition-colors rounded-sm',
                filter === 'unread'
                  ? 'bg-surface-3 text-txt-primary'
                  : 'text-txt-muted hover:text-txt-secondary hover:bg-surface-2'
              )}
            >
              UNREAD
            </button>
            <button
              onClick={() => setFilter('all')}
              className={cn(
                'px-4 py-1.5 text-micro font-mono uppercase tracking-widest transition-colors rounded-sm',
                filter === 'all'
                  ? 'bg-surface-3 text-txt-primary'
                  : 'text-txt-muted hover:text-txt-secondary hover:bg-surface-2'
              )}
            >
              ALL_LOGS
            </button>
          </div>
          {alerts.length > 0 && filter === 'unread' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={markAllRead}
              className="font-mono text-micro uppercase tracking-widest gap-2 rounded-sm"
            >
              <CheckSquare className="h-3.5 w-3.5" />
              ACK_ALL
            </Button>
          )}
        </div>
      </div>

      {!user && (
        <p className="text-micro font-mono text-txt-muted uppercase tracking-widest">
          Sign in to view thesis alerts.
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-micro font-mono text-txt-muted uppercase">
          <Clock className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : alerts.length === 0 ? (
        <div className="border border-border-base bg-surface-1 p-8 text-center rounded-sm">
          <Bell className="h-8 w-8 text-txt-muted mx-auto mb-3" />
          <p className="font-mono text-micro uppercase tracking-widest text-txt-muted">
            NO_ACTIVE_ALERTS
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={cn(
                'border border-border-base bg-surface-1 p-4 rounded-sm flex gap-3',
                !alert.is_read && 'border-accent/40'
              )}
            >
              <ShieldAlert className="h-4 w-4 text-accent shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-sm font-bold text-txt-primary">{alert.ticker}</span>
                  <span className="text-micro font-mono text-txt-muted uppercase">
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="font-mono text-micro text-txt-secondary uppercase tracking-wide">
                  {alert.message}
                </p>
              </div>
              {!alert.is_read && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => markAsRead(alert.id)}
                  className="font-mono text-micro uppercase tracking-widest rounded-sm shrink-0"
                >
                  ACK
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
