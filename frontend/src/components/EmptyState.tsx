import { Search, Command } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '../utils/cn';

interface EmptyStateProps {
  type: 'welcome' | 'no-chart' | 'no-news' | 'no-history' | 'no-data';
  onAction?: () => void;
  onNavigate?: (view: 'dashboard' | 'research' | 'scenarios' | 'agent') => void;
  onFocusSearch?: () => void;
}

const emptyStateConfig = {
  welcome: {
    title: 'CatalystEdge',
    description:
      'Enter a ticker to run living-thesis research — analysis, kill criteria, and evidence.',
    actionLabel: null as string | null,
  },
  'no-chart': {
    title: 'No price data',
    description: 'Price data is unavailable for this asset right now.',
    actionLabel: 'Retry',
  },
  'no-news': {
    title: 'No recent coverage',
    description: 'No significant publications found for this ticker.',
    actionLabel: null,
  },
  'no-history': {
    title: 'No recent analyses',
    description: 'Run a scan to populate your local cache.',
    actionLabel: null,
  },
  'no-data': {
    title: 'Fundamentals unavailable',
    description: 'Core financial data is not available for this ticker.',
    actionLabel: null,
  },
};

const CAPS: {
  label: string;
  view: 'dashboard' | 'research' | 'scenarios' | 'agent';
}[] = [
  { label: 'Analysis', view: 'dashboard' },
  { label: 'Event study', view: 'research' },
  { label: 'Scenarios', view: 'scenarios' },
  { label: 'Agent', view: 'agent' },
];

const isMac =
  typeof navigator !== 'undefined' &&
  navigator.platform.toUpperCase().indexOf('MAC') >= 0;

const EmptyState = ({ type, onAction, onNavigate, onFocusSearch }: EmptyStateProps) => {
  const config = emptyStateConfig[type];

  const handleCap = (view: (typeof CAPS)[number]['view']) => {
    if (view === 'dashboard') {
      onFocusSearch?.();
      return;
    }
    onNavigate?.(view);
  };

  return (
    <div
      className={cn(
        'ui-panel relative flex min-h-[380px] flex-col items-center justify-center p-10 text-center',
        type !== 'welcome' && 'border-dashed opacity-90'
      )}
    >
      <div className="relative z-10 flex max-w-md flex-col items-center">
        <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-md border border-border-base bg-surface-2 text-txt-tertiary">
          <Search className="h-4 w-4" strokeWidth={1.75} />
        </div>

        <h3 className="mb-2 font-mono text-sm font-semibold tracking-wide text-txt-primary">
          {config.title}
        </h3>

        <p className="mb-6 max-w-sm text-sm leading-relaxed text-txt-secondary">
          {config.description}
        </p>

        {type === 'welcome' && (
          <div className="flex flex-wrap items-center justify-center gap-2">
            {CAPS.map((cap) => (
              <button
                key={cap.label}
                type="button"
                onClick={() => handleCap(cap.view)}
                className="cursor-pointer rounded-md border border-border-base bg-surface-2 px-2.5 py-1.5 font-mono text-micro tracking-wide text-txt-secondary transition-colors hover:border-accent/50 hover:bg-surface-3 hover:text-txt-primary"
              >
                {cap.label}
              </button>
            ))}
          </div>
        )}

        {type === 'welcome' && (
          <p className="mt-8 flex items-center gap-2 font-mono text-micro tracking-wider text-txt-muted">
            <span>Press</span>
            <kbd className="inline-flex items-center gap-1 rounded border border-border-base bg-surface-2 px-1.5 py-0.5 text-txt-tertiary">
              {isMac ? (
                <>
                  <Command className="h-3 w-3" />K
                </>
              ) : (
                'Ctrl+K'
              )}
            </kbd>
            <span>to focus search</span>
          </p>
        )}

        {config.actionLabel && onAction && (
          <Button variant="outline" className="mt-6" onClick={onAction}>
            {config.actionLabel}
          </Button>
        )}
      </div>
    </div>
  );
};

export default EmptyState;
