/**
 * StreamingAnalysisProgress — live analysis sequence with clear WAITING / RUNNING / DONE
 */

import { X, TrendingUp, Newspaper, Brain, Search, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { cn } from '../utils/cn';
import type { StreamEvent } from '../hooks/useStreamingAnalysis';

interface StreamingAnalysisProgressProps {
  ticker: string;
  isStreaming: boolean;
  progress: number;
  currentTool: string | null;
  events: StreamEvent[];
  partialData: Partial<{
    headlines: string[];
    price_data: unknown[];
    overall_sentiment: string;
    overall_confidence: number;
    skeptic_sentiment: string;
  }>;
  error: string | null;
  onCancel?: () => void;
}

const TOOLS_CONFIG = [
  { name: 'fetch_news_headlines', label: 'Fetch news', icon: Newspaper },
  { name: 'fetch_price_data', label: 'Fetch price', icon: TrendingUp },
  { name: 'analyze_sentiment', label: 'AI sentiment', icon: Brain },
  { name: 'generate_skeptic_critique', label: 'Skeptic review', icon: Search },
];

const STATUS_LABEL: Record<'pending' | 'active' | 'completed' | 'failed', string> = {
  pending: 'Waiting',
  active: 'Running',
  completed: 'Done',
  failed: 'Failed',
};

export default function StreamingAnalysisProgress({
  ticker,
  isStreaming,
  progress,
  currentTool,
  events,
  partialData,
  error,
  onCancel,
}: StreamingAnalysisProgressProps) {
  const completedTools = new Set(
    events.filter((e) => e.type === 'tool_completed').map((e) => e.tool)
  );

  const getToolStatus = (
    toolName: string
  ): 'pending' | 'active' | 'completed' | 'failed' => {
    if (error && currentTool === toolName) return 'failed';
    if (completedTools.has(toolName)) return 'completed';
    if (currentTool === toolName) return 'active';
    return 'pending';
  };

  const getToolMessage = (toolName: string): string => {
    const event = events.find(
      (e) => e.type === 'tool_completed' && e.tool === toolName
    );
    return event?.message || '';
  };

  const headlinesCount = partialData.headlines?.length || 0;
  const priceDataPoints = Array.isArray(partialData.price_data)
    ? partialData.price_data.length
    : 0;
  const sentiment = partialData.overall_sentiment;
  const pct = Math.max(0, Math.min(100, Math.round(progress * 100)));

  return (
    <div className="relative mx-auto w-full max-w-2xl overflow-hidden rounded-md border border-border-base bg-surface-1 font-mono">
      <div className="relative z-10 flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border-base bg-surface-2 px-4 py-3">
          <div className="flex items-center gap-3 text-txt-primary">
            <Terminal
              className={cn('h-4 w-4 text-accent', isStreaming && 'animate-pulse')}
            />
            <h2 className="text-sm font-semibold tracking-wide">
              {ticker}
              <span className="ml-2 font-normal text-txt-muted">
                · Analysis sequence
              </span>
            </h2>
          </div>
          <span className="flex items-center gap-2 font-mono text-micro uppercase tracking-wider text-txt-muted">
            {isStreaming ? (
              <>
                Active
                <span className="h-3 w-1.5 animate-pulse bg-accent" />
              </>
            ) : error ? (
              'Halted'
            ) : (
              'Complete'
            )}
          </span>
        </div>

        <div className="border-b border-border-base/50 bg-canvas px-4 py-4">
          <div className="mb-2 flex items-center justify-between text-micro font-semibold tracking-wider">
            <span className="uppercase text-txt-secondary">Progress</span>
            <span className="text-accent">{pct}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
            <motion.div
              className="h-full rounded-full bg-accent"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ ease: 'linear', duration: 0.3 }}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1 bg-canvas p-3">
          {TOOLS_CONFIG.map((tool, index) => {
            const status = getToolStatus(tool.name);
            const message = getToolMessage(tool.name);

            return (
              <motion.div
                key={tool.name}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05, duration: 0.2 }}
                className={cn(
                  'flex items-center gap-4 rounded-md border px-3 py-2.5 transition-colors duration-100',
                  status === 'active' &&
                    'border-accent/45 bg-accent/10 shadow-[inset_2px_0_0_0_var(--accent)]',
                  status === 'completed' && 'border-border-base/50 bg-surface-1',
                  status === 'pending' && 'border-border-base/40 bg-surface-1/60',
                  status === 'failed' && 'border-bear/40 bg-bear/10'
                )}
              >
                <div className="flex h-5 w-5 shrink-0 items-center justify-center text-micro font-bold">
                  {status === 'completed' ? (
                    <span className="text-bull">✓</span>
                  ) : status === 'active' ? (
                    <span className="animate-pulse text-sm text-accent">→</span>
                  ) : status === 'failed' ? (
                    <span className="text-bear">✕</span>
                  ) : (
                    <span className="text-txt-muted/40">○</span>
                  )}
                </div>

                <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                  <div className="flex min-w-0 flex-col">
                    <span
                      className={cn(
                        'text-micro font-semibold tracking-wide',
                        status === 'active' && 'text-accent',
                        status === 'completed' && 'text-txt-secondary',
                        status === 'pending' && 'text-txt-muted',
                        status === 'failed' && 'text-bear'
                      )}
                    >
                      {tool.label}
                    </span>

                    <AnimatePresence mode="wait">
                      {message && status === 'completed' && (
                        <motion.span
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-0.5 truncate text-micro tracking-wide text-txt-muted"
                        >
                          {message}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </div>

                  <span
                    className={cn(
                      'w-16 text-right text-micro font-semibold uppercase tracking-wider',
                      status === 'completed' && 'text-bull',
                      status === 'active' && 'animate-pulse text-accent',
                      status === 'pending' && 'text-txt-muted/45',
                      status === 'failed' && 'text-bear'
                    )}
                  >
                    {STATUS_LABEL[status]}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {(headlinesCount > 0 || priceDataPoints > 0 || sentiment) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border-base/50 bg-surface-2/30 p-4"
          >
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1.5 w-1.5 animate-pulse rounded-sm bg-accent" />
              <div className="text-micro font-semibold uppercase tracking-wider text-txt-secondary">
                Live feed
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-left">
              {headlinesCount > 0 && (
                <div className="rounded-md border border-border-base/50 border-l-2 border-l-border-strong bg-surface-1 p-2">
                  <div className="mb-1 text-micro font-semibold uppercase tracking-wider text-txt-muted">
                    Headlines
                  </div>
                  <div className="text-micro font-bold text-txt-primary">
                    {headlinesCount}
                  </div>
                </div>
              )}
              {priceDataPoints > 0 && (
                <div className="rounded-md border border-border-base/50 border-l-2 border-l-border-strong bg-surface-1 p-2">
                  <div className="mb-1 text-micro font-semibold uppercase tracking-wider text-txt-muted">
                    Datapoints
                  </div>
                  <div className="text-micro font-bold text-txt-primary">
                    {priceDataPoints}
                  </div>
                </div>
              )}
              {sentiment && (
                <div className="rounded-md border border-border-base/50 border-l-2 border-l-border-strong bg-surface-1 p-2">
                  <div className="mb-1 text-micro font-semibold uppercase tracking-wider text-txt-muted">
                    Sentiment
                  </div>
                  <div
                    className={cn(
                      'text-micro font-bold tracking-wide',
                      sentiment === 'Bullish' && 'text-bull',
                      sentiment === 'Bearish' && 'text-bear',
                      sentiment !== 'Bullish' &&
                        sentiment !== 'Bearish' &&
                        'text-txt-secondary'
                    )}
                  >
                    {sentiment}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="border-t border-bear bg-bear/10 p-3 text-micro font-semibold tracking-wide text-bear"
          >
            {error}
          </motion.div>
        )}

        {isStreaming && onCancel && (
          <div className="flex justify-end border-t border-border-base bg-canvas p-3">
            <Button
              variant="ghost"
              onClick={onCancel}
              className="h-8 gap-2 rounded-md border border-transparent text-micro text-txt-muted hover:border-kill/30 hover:bg-kill-dim hover:text-kill"
            >
              <X className="h-3 w-3" />
              Cancel analysis
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
