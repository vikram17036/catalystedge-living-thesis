/**
 * ThesisDiffView — strengthened / weakened / invalidated / triggered / new risks
 */

import { useState } from 'react';
import { TrendingUp, TrendingDown, ShieldAlert, HelpCircle } from 'lucide-react';
import type { ThesisComparison } from '../types/thesis';
import { cn } from '../utils/cn';

interface EvidenceItem {
  id?: string;
  metric?: string;
  value?: unknown;
  type?: string;
  source?: string;
}

interface ThesisDiffViewProps {
  comparison: ThesisComparison | null;
  originEvidence?: EvidenceItem[];
  replayEvidence?: EvidenceItem[];
}

export default function ThesisDiffView({
  comparison,
  originEvidence = [],
  replayEvidence = [],
}: ThesisDiffViewProps) {
  const [showWhy, setShowWhy] = useState(false);

  if (!comparison?.has_comparison) {
    return null;
  }

  const diff = comparison.thesis_diff;
  const sections: {
    key: string;
    label: string;
    items: { text: string; evidence_ids?: string[] }[];
    tone: string;
    icon: typeof TrendingUp;
  }[] = [
    {
      key: 'strengthened',
      label: 'STRENGTHENED',
      items: diff?.strengthened || [],
      tone: 'text-bull',
      icon: TrendingUp,
    },
    {
      key: 'weakened',
      label: 'WEAKENED',
      items: diff?.weakened || [],
      tone: 'text-bear',
      icon: TrendingDown,
    },
    {
      key: 'invalidated',
      label: 'INVALIDATED',
      items: diff?.invalidated || [],
      tone: 'text-bear',
      icon: TrendingDown,
    },
    {
      key: 'triggered',
      label: 'KILL',
      items: diff?.triggered_criteria || [],
      tone: 'text-accent',
      icon: ShieldAlert,
    },
    {
      key: 'risks',
      label: 'NEW_RISKS',
      items: diff?.new_risks || [],
      tone: 'text-txt-secondary',
      icon: HelpCircle,
    },
  ];

  const hasRows = sections.some((s) => s.items.length > 0);
  if (!hasRows && !(comparison.changes && comparison.changes.length)) {
    return null;
  }

  const ledger = [...originEvidence, ...replayEvidence];

  return (
    <div className="border border-accent/30 bg-accent/5 rounded-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-accent/20 bg-accent/5">
        <h4 className="text-micro font-mono font-bold uppercase tracking-widest text-txt-primary">
          THESIS_DIFF
          {comparison.replay_label ? ` // ${comparison.replay_label}` : ''}
        </h4>
        <button
          type="button"
          onClick={() => setShowWhy((v) => !v)}
          className="flex items-center gap-1 text-micro font-mono uppercase tracking-widest text-txt-muted hover:text-accent"
        >
          <HelpCircle className="h-3.5 w-3.5" />
          {showWhy ? 'HIDE_EVIDENCE' : 'WHY'}
        </button>
      </div>

      <div className="p-3 space-y-2 bg-canvas">
        {sections.map((section) =>
          section.items.map((item, i) => {
            const Icon = section.icon;
            return (
              <div
                key={`${section.key}-${i}`}
                className="flex items-start gap-2 text-micro font-mono uppercase tracking-wider"
              >
                <Icon className={cn('h-3.5 w-3.5 shrink-0 mt-0.5', section.tone)} />
                <span className="text-txt-muted">{section.label}:</span>
                <span className={cn('font-bold', section.tone)}>{item.text}</span>
              </div>
            );
          })
        )}

        {!diff &&
          comparison.changes?.map((change, index) => (
            <div
              key={index}
              className="flex items-center gap-2 text-micro font-mono uppercase tracking-wider"
            >
              <span className="text-txt-muted">{change.field}:</span>
              <span className="text-txt-secondary">{String(change.from)}</span>
              <span className="text-txt-muted">→</span>
              <span className="text-accent font-bold">{String(change.to)}</span>
            </div>
          ))}
      </div>

      {comparison.change_summary && (
        <p className="text-micro font-mono text-txt-muted uppercase tracking-wider px-4 py-2 border-t border-border-base/50 bg-surface-1">
          {comparison.change_summary}
        </p>
      )}

      {showWhy && (
        <div className="border-t border-border-base bg-surface-1 p-3 space-y-2 max-h-48 overflow-y-auto">
          <p className="text-micro font-mono font-bold text-txt-primary uppercase tracking-widest">
            EVIDENCE_LEDGER
          </p>
          {ledger.length === 0 && (
            <p className="text-micro font-mono text-txt-muted uppercase">No evidence rows attached</p>
          )}
          {ledger.map((e, i) => (
            <div key={e.id || i} className="text-micro font-mono text-txt-secondary tracking-wide">
              <span className="text-accent">{e.id || `row_${i}`}</span>
              {' // '}
              {e.type || 'ev'} · {e.metric || '—'} = {String(e.value ?? '—')}
              {e.source ? ` · ${e.source}` : ''}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
