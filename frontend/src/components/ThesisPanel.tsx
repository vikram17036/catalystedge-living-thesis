/**
 * ThesisPanel — Propose/Create thesis + Replay + Diff + Evidence Why
 * Phase 1 Living Thesis DoD
 */

import { useMemo, useState } from 'react';
import { BookMarked, Play, Loader2, AlertTriangle, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../context/AuthContext';
import {
  useCreateThesis,
  useThesisForTicker,
  useThesisComparison,
  useReplayThesis,
  useProposeThesisFromAnalysis,
} from '../api/theses';
import ThesisDiffView from './ThesisDiffView';
import ThesisEditor from './ThesisEditor';
import type { AnalysisData } from '../types/api';
import type { AnalysisSnapshot, CreateThesisRequest, ThesisComparison } from '../types/thesis';
import { cn } from '../utils/cn';

interface ThesisPanelProps {
  analysis: AnalysisData;
  onAlertCreated?: () => void;
}

function buildSnapshot(analysis: AnalysisData): AnalysisSnapshot {
  return {
    sentiment: analysis.overall_sentiment || 'Insufficient Data',
    confidence: analysis.overall_confidence ?? 0,
    skeptic_verdict: analysis.skeptic_sentiment || undefined,
    key_themes: (analysis.key_themes || []).map((t) => t.theme),
    timestamp: analysis.timestamp || new Date().toISOString(),
  };
}

export default function ThesisPanel({ analysis, onAlertCreated }: ThesisPanelProps) {
  const { user } = useAuth();
  const ticker = analysis.ticker;
  const { data: thesisData, refetch } = useThesisForTicker(ticker);
  const activeThesis = thesisData?.theses?.[0] ?? null;
  const comparison = useThesisComparison(activeThesis?.id ?? null);
  const createThesis = useCreateThesis();
  const propose = useProposeThesisFromAnalysis();
  const replay = useReplayThesis();
  const [editorOpen, setEditorOpen] = useState(false);
  const [diffResult, setDiffResult] = useState<ThesisComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  const snapshot = useMemo(() => buildSnapshot(analysis), [analysis]);
  const evidenceLedger = analysis.evidence_ledger as
    | { id?: string; metric?: string; value?: unknown; type?: string; source?: string }[]
    | undefined;

  const activeDiff = diffResult || comparison.data || null;
  const originEvidence =
    (activeThesis?.origin_evidence as typeof evidenceLedger) || evidenceLedger || [];
  const attachedEvidence = (activeThesis?.attached_evidence || []) as NonNullable<
    typeof evidenceLedger
  >;

  const handleProposeAndCreate = async () => {
    setError(null);
    if (!user) {
      setError('Sign in to create a thesis');
      return;
    }
    try {
      const proposal = await propose.mutateAsync({
        ticker,
        analysis: {
          id: analysis.id,
          ticker: analysis.ticker,
          summary: analysis.summary,
          overall_sentiment: analysis.overall_sentiment,
          overall_confidence: analysis.overall_confidence,
          skeptic_sentiment: analysis.skeptic_sentiment,
          key_themes: analysis.key_themes,
          risks_identified: analysis.risks_identified,
          timestamp: analysis.timestamp,
          evidence_ledger: analysis.evidence_ledger,
          fundamental_data: analysis.fundamental_data,
          news_articles: analysis.news_articles,
          price_data: analysis.price_data,
        },
      });

      const body: CreateThesisRequest = {
        ticker: proposal.ticker,
        thesis_summary: proposal.thesis_summary,
        conviction_level: proposal.conviction_level,
        kill_criteria: proposal.kill_criteria,
        origin_analysis_id: proposal.origin_analysis_id ?? analysis.id,
        origin_analysis_snapshot: proposal.origin_analysis_snapshot || snapshot,
        origin_evidence: proposal.origin_evidence || evidenceLedger,
        structured_kill_criteria: proposal.structured_kill_criteria,
      };
      await createThesis.mutateAsync(body);
      await refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create thesis');
    }
  };

  const handleReplay = async () => {
    if (!activeThesis) return;
    setError(null);
    try {
      const result = await replay.mutateAsync({
        thesisId: activeThesis.id,
        label: 'nvda_t1',
        createAlert: true,
      });
      setDiffResult(result);
      await comparison.refetch();
      onAlertCreated?.();
    } catch (e) {
      // Fallback label for non-NVDA
      try {
        const result = await replay.mutateAsync({
          thesisId: activeThesis.id,
          label: 'adverse_shock',
          createAlert: true,
        });
        setDiffResult(result);
        onAlertCreated?.();
      } catch (e2) {
        setError(e2 instanceof Error ? e2.message : 'Replay failed');
      }
    }
  };

  const pending = propose.isPending || createThesis.isPending;

  return (
    <div className="border border-border-base bg-surface-1 rounded-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border-base bg-surface-2">
        <h3 className="text-micro font-mono font-bold uppercase tracking-widest text-accent">
          LIVING_THESIS
        </h3>
        <span className="text-micro font-mono text-txt-muted uppercase tracking-widest">
          {activeThesis ? 'ACTIVE' : 'NO_THESIS'}
        </span>
      </div>

      <div className="p-4 space-y-3">
        {!user && (
          <p className="text-micro font-mono text-txt-muted uppercase tracking-widest flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-accent" />
            Sign in to freeze a thesis snapshot and run Replay.
          </p>
        )}

        {activeThesis ? (
          <>
            <p className="font-mono text-micro text-txt-secondary leading-relaxed uppercase tracking-wide">
              {'> '} {activeThesis.thesis_summary.slice(0, 220)}
              {activeThesis.thesis_summary.length > 220 ? '…' : ''}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                onClick={handleReplay}
                disabled={replay.isPending}
                className="gap-2 font-mono text-micro uppercase tracking-widest rounded-sm h-8"
              >
                {replay.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                REPLAY_ADVERSE
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setEditorOpen(true)}
                className="font-mono text-micro uppercase tracking-widest border border-border-base rounded-sm h-8"
              >
                EDIT_THESIS
              </Button>
            </div>

            {attachedEvidence.length > 0 && (
              <div className="border border-border-base/60 bg-surface-2/40 rounded-sm p-3 space-y-1">
                <p className="text-micro font-mono font-bold uppercase tracking-widest text-accent">
                  ATTACHED_EXPERIMENTS
                </p>
                {attachedEvidence.map((e, i) => (
                  <div
                    key={(e.id as string) || i}
                    className="text-micro font-mono text-txt-secondary uppercase tracking-wide"
                  >
                    {String(e.type || 'research')} · {String(e.metric || '—')} ={' '}
                    {String(e.value ?? '—')}
                  </div>
                ))}
              </div>
            )}

            <ThesisDiffView
              comparison={activeDiff}
              originEvidence={originEvidence}
              attachedEvidence={attachedEvidence}
              replayEvidence={[]}
            />
          </>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={handleProposeAndCreate}
              disabled={!user || pending}
              className={cn(
                'gap-2 font-mono text-micro uppercase tracking-widest rounded-sm h-8'
              )}
            >
              {pending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              PROPOSE_AND_CREATE_THESIS
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setEditorOpen(true)}
              disabled={!user}
              className="font-mono text-micro uppercase tracking-widest border border-border-base rounded-sm h-8 gap-2"
            >
              <BookMarked className="h-3 w-3" />
              CUSTOMIZE
            </Button>
          </div>
        )}

        {error && (
          <p className="text-micro font-mono text-bear uppercase tracking-widest">{error}</p>
        )}
      </div>

      <ThesisEditor
        isOpen={editorOpen}
        onClose={() => {
          setEditorOpen(false);
          refetch();
        }}
        ticker={ticker}
        existingThesis={activeThesis}
        analysisSnapshot={snapshot}
        originEvidence={evidenceLedger as Record<string, unknown>[] | undefined}
        originAnalysisId={analysis.id}
      />
    </div>
  );
}
