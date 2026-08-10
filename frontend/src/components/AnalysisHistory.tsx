import { RefreshCw, Trash2, Clock, History, ArrowRight } from 'lucide-react';
import { ListSkeleton } from './ui/skeleton';
import { useCachedTickers, useDeleteAnalysis } from '../api/hooks';
import type { CachedTickerItem } from '../types/api';
import { cn } from '../utils/cn';

interface AnalysisHistoryProps {
  onSelectHistory: (ticker: string) => void;
  variant?: 'rail' | 'page';
}

function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return '—';
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '—';
  }
}

function formatFullDateTime(timestamp: string | null): string {
  if (!timestamp) return '';
  try {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return '';
  }
}

const AnalysisHistory = ({
  onSelectHistory,
  variant = 'rail',
}: AnalysisHistoryProps) => {
  const { data, isLoading, refetch } = useCachedTickers();
  const deleteMutation = useDeleteAnalysis();
  const isPage = variant === 'page';

  const rawTickers = data?.tickers || [];
  const tickers: CachedTickerItem[] = rawTickers.map((item: string | CachedTickerItem) => {
    if (typeof item === 'string') {
      return { symbol: item, timestamp: null };
    }
    return item;
  });

  const handleDelete = (e: React.MouseEvent, symbol: string) => {
    e.stopPropagation();
    deleteMutation.mutate(symbol, {
      onSuccess: () => refetch(),
    });
  };

  return (
    <div
      className={cn(
        'ui-panel flex flex-col overflow-hidden',
        isPage ? 'min-h-[280px]' : 'h-full'
      )}
    >
      <div className="flex items-center justify-between border-b border-border-base px-3 py-2.5">
        <div className="flex items-center gap-2">
          <History className="h-3.5 w-3.5 text-txt-muted" strokeWidth={1.5} />
          <span className="ui-label">{isPage ? 'Cached analyses' : 'Recent'}</span>
        </div>
        <button
          type="button"
          className="cursor-pointer rounded-md p-1.5 text-txt-muted outline-none transition-colors hover:bg-surface-2 hover:text-txt-secondary"
          onClick={() => refetch()}
          title="Refresh"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="no-scrollbar flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            <ListSkeleton items={4} />
          </div>
        ) : tickers.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center py-12 text-center">
            <Clock className="mb-3 h-4 w-4 text-txt-muted" strokeWidth={1.5} />
            <p className="text-sm text-txt-tertiary">No cached analyses</p>
            <p className="mt-1 max-w-[14rem] text-micro text-txt-muted">
              Results appear here as shortcuts after you run a scan.
            </p>
          </div>
        ) : (
          <div className={cn('flex flex-col', isPage ? 'gap-2' : 'gap-1')}>
            {tickers.map((item) =>
              isPage ? (
                <div
                  key={item.symbol}
                  role="button"
                  tabIndex={0}
                  className="group flex w-full cursor-pointer items-center justify-between rounded-md border border-border-base bg-surface-1 px-4 py-3.5 text-left transition-colors hover:border-accent/35 hover:bg-surface-2"
                  onClick={() => onSelectHistory(item.symbol)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectHistory(item.symbol);
                    }
                  }}
                >
                  <div className="min-w-0">
                    <p className="font-mono text-base font-semibold tracking-wide text-txt-primary">
                      {item.symbol}
                    </p>
                    <p className="mt-1 text-sm text-txt-secondary">
                      {formatFullDateTime(item.timestamp) || 'Cached analysis'}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="hidden items-center gap-1 text-sm text-accent sm:flex">
                      Open analysis
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-txt-muted transition-colors hover:bg-bear/15 hover:text-bear"
                      onClick={(e) => handleDelete(e, item.symbol)}
                      disabled={deleteMutation.isPending}
                      title="Remove"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  key={item.symbol}
                  role="button"
                  tabIndex={0}
                  className="group flex w-full cursor-pointer items-center justify-between rounded-md border border-transparent px-2.5 py-2 text-left transition-colors hover:border-border-base hover:bg-surface-2"
                  onClick={() => onSelectHistory(item.symbol)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectHistory(item.symbol);
                    }
                  }}
                  title={formatFullDateTime(item.timestamp)}
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span className="font-mono text-sm font-medium tracking-wide text-txt-primary group-hover:text-accent">
                      {item.symbol}
                    </span>
                    <span className="text-micro text-txt-muted">
                      {formatRelativeTime(item.timestamp)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="cursor-pointer rounded-md p-1 text-txt-muted opacity-0 transition-all hover:bg-bear/15 hover:text-bear group-hover:opacity-100"
                    onClick={(e) => handleDelete(e, item.symbol)}
                    disabled={deleteMutation.isPending}
                    title="Remove"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisHistory;
