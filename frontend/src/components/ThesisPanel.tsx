/**
 * ThesisPanel — Propose/Create thesis + Replay + Diff + Evidence Why
 * Phase 1 Living Thesis DoD — content presentation (readable cards)
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
import {
  formatAttachedEvidenceCard,
  summarizeThesisCopy,
  type AttachedEvidenceLike,
} from '../utils/formatAttachedEvidence';

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

function EvidenceCardView({
  card,
}: {
  card: ReturnType<typeof formatAttachedEvidenceCard>;
}) {
  return (
    <div
      className={cn(
        'rounded-md border border-border-base bg-surface-1 px-3 py-2.5',
        card.hypothetical && 'border-accent/35'
      )}
    >
      <p className="ui-label">{card.kindLabel}</p>
      <p className="mt-1 text-sm font-medium leading-snug text-txt-primary">
        {card.title}
      </p>
      <p className="mt-0.5 text-micro leading-relaxed text-txt-secondary">
        {card.detail}
      </p>
      {card.hypothetical ? (
        <span className="mt-2 inline-block rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-accent">
          Hypothetical
        </span>
      ) : null}
    </div>
  );
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
    | AttachedEvidenceLike[]
    | undefined;

  const activeDiff = diffResult || comparison.data || null;
  const originEvidence =
    (activeThesis?.origin_evidence as typeof evidenceLedger) || evidenceLedger || [];
  const attachedEvidence = (activeThesis?.attached_evidence ||
    []) as AttachedEvidenceLike[];

  const thesisCopy = useMemo(() => {
    if (!activeThesis) return null;
    return summarizeThesisCopy({
      summary: activeThesis.thesis_summary,
      conviction: activeThesis.conviction_level,
      snapshot:
        (activeThesis.origin_analysis_snapshot as AnalysisSnapshot | undefined) ||
        snapshot,
    });
  }, [activeThesis, snapshot]);

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
    } catch {
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
  const research = attachedEvidence.filter(
    (e) => String(e.type || '').toLowerCase() !== 'scenario'
  );
  const whatIfs = attachedEvidence.filter(
    (e) => String(e.type || '').toLowerCase() === 'scenario'
  );

  return (
    <div className="ui-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border-base px-4 py-2.5">
        <h3 className="ui-label text-txt-secondary">Living thesis</h3>
        <span className="font-mono text-micro tracking-wide text-txt-muted">
          {activeThesis ? 'Active' : 'No thesis'}
        </span>
      </div>

      <div className="space-y-4 p-4">
        {!user && (
          <p className="flex items-center gap-2 text-sm text-txt-tertiary">
            <AlertTriangle className="h-3.5 w-3.5 text-accent" />
            Sign in to freeze a thesis snapshot and run Replay.
          </p>
        )}

        {activeThesis && thesisCopy ? (
          <>
            <div>
              <p className="text-sm font-semibold tracking-tight text-txt-primary">
                {thesisCopy.headline}
              </p>
              <p className="mt-1.5 text-sm leading-relaxed text-txt-secondary">
                {thesisCopy.body}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                onClick={handleReplay}
                disabled={replay.isPending}
                className="h-8 gap-2"
              >
                {replay.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                Replay adverse
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEditorOpen(true)}
                className="h-8"
              >
                Edit thesis
              </Button>
            </div>

            <div className="space-y-2">
              <p className="ui-label">
                Attached research · {research.length}
              </p>
              {research.length === 0 ? (
                <p className="text-sm text-txt-muted">
                  None yet — attach from Research, Lab, or Analogs.
                </p>
              ) : (
                <div className="space-y-2">
                  {research.map((e, i) => (
                    <EvidenceCardView
                      key={String(e.id || i)}
                      card={formatAttachedEvidenceCard(e, i)}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <p className="ui-label">Attached what-ifs · {whatIfs.length}</p>
              {whatIfs.length === 0 ? (
                <p className="text-sm text-txt-muted">
                  None yet — attach from Scenarios (always hypothetical).
                </p>
              ) : (
                <div className="space-y-2">
                  {whatIfs.map((e, i) => (
                    <EvidenceCardView
                      key={String(e.id || i)}
                      card={formatAttachedEvidenceCard(e, i)}
                    />
                  ))}
                </div>
              )}
            </div>

            <ThesisDiffView
              comparison={activeDiff}
              originEvidence={originEvidence}
              attachedEvidence={research}
              replayEvidence={[]}
            />
            {whatIfs.length > 0 && (
              <p className="px-1 text-micro text-txt-muted">
                Attached what-ifs are hypothetical and excluded from Diff baseline.
              </p>
            )}
          </>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={handleProposeAndCreate}
              disabled={!user || pending}
              className="h-8 gap-2"
            >
              {pending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              Propose & create thesis
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setEditorOpen(true)}
              disabled={!user}
              className="h-8 gap-2"
            >
              <BookMarked className="h-3 w-3" />
              Customize
            </Button>
          </div>
        )}

        {error && <p className="text-sm text-bear">{error}</p>}
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
