/**
 * KillAlertBanner — triggered kill criteria (product copy, not schema dump)
 */

import { useState } from 'react';
import { X, ShieldAlert, ChevronDown, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import type { KillAlert } from '../types/api';
import {
  formatKillCriterionHuman,
  formatTriggeringSignalHuman,
} from '../utils/formatKillAlert';

interface KillAlertBannerProps {
  alerts: KillAlert[];
  onDismiss?: (alertId: string) => void;
  onAcknowledge?: (alertId: string) => void;
  onViewThesis?: (thesisId: string) => void;
}

export default function KillAlertBanner({
  alerts,
  onDismiss,
  onAcknowledge,
  onViewThesis,
}: KillAlertBannerProps) {
  const [openRaw, setOpenRaw] = useState<Record<string, boolean>>({});

  if (!alerts || alerts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <AnimatePresence>
        {alerts.map((alert, index) => {
          const human = formatKillCriterionHuman(
            alert.triggered_criteria,
            alert.ticker
          );
          const signal = formatTriggeringSignalHuman(alert.triggering_signal);
          const showRaw = openRaw[alert.id];

          return (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
              className="flex w-full flex-col overflow-hidden rounded-md border border-y-border-base border-l-4 border-r-border-base border-l-kill border-y border-r bg-kill-dim"
            >
              <div className="flex items-center justify-between border-b border-kill/20 bg-kill/5 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center rounded-md border border-kill/30 bg-kill/10 p-1">
                    <ShieldAlert className="h-4 w-4 text-kill" />
                  </div>
                  <div className="flex flex-col">
                    <h4 className="font-mono text-micro font-semibold uppercase tracking-wider text-kill">
                      Kill criterion triggered
                    </h4>
                    <span className="mt-0.5 text-micro text-txt-muted">
                      High priority · living thesis
                    </span>
                  </div>
                </div>

                {onDismiss && (
                  <button
                    type="button"
                    onClick={() => onDismiss(alert.id)}
                    className="rounded-md p-1.5 text-txt-muted transition-colors hover:bg-kill/10 hover:text-kill"
                    title="Dismiss alert"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              <div className="flex flex-col gap-4 bg-canvas/50 p-4">
                <div>
                  <p className="text-sm font-medium leading-relaxed text-txt-primary">
                    {human.headline}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-txt-secondary">
                    {signal}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setOpenRaw((s) => ({ ...s, [alert.id]: !s[alert.id] }))
                  }
                  className="flex items-center gap-1 self-start text-micro text-txt-muted hover:text-txt-secondary"
                >
                  {showRaw ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  Why / raw criterion
                </button>
                {showRaw ? (
                  <pre className="overflow-x-auto rounded-md border border-border-base bg-surface-1 p-3 font-mono text-micro text-txt-muted">
                    {human.raw}
                    {alert.triggering_signal
                      ? `\n${alert.triggering_signal}`
                      : ''}
                  </pre>
                ) : null}

                <div className="flex justify-end gap-2 pt-1">
                  {onViewThesis && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onViewThesis(alert.thesis_id)}
                      className="h-8 rounded-md px-3"
                    >
                      View thesis
                    </Button>
                  )}
                  {onAcknowledge && (
                    <Button
                      size="sm"
                      onClick={() => onAcknowledge(alert.id)}
                      className="h-8 rounded-md border border-kill/40 bg-kill/15 px-3 text-kill hover:bg-kill/25"
                    >
                      Acknowledge
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
