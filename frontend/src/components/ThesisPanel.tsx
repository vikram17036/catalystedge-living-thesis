/**
 * ThesisPanel — Propose/Create thesis + Replay + Diff + Evidence Why
 * Active thesis first; deliberate “Start new thesis” closes old → creates new.
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
  useStartNewThesis,
  thesisApiErrorMessage,
} from '../api/theses';
import ThesisDiffView from './ThesisDiffView';
import ThesisEditor from './ThesisEditor';
import type { AnalysisData } from '../types/api';
import type {
  AnalysisSnapshot,
  CreateThesisRequest,
  Thesis,
  ThesisComparison,
} from '../types/thesis';
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

function isActiveStatus(status?: string) {
  return !status || status === 'active' || status === 'validated';
}

function formatCreated(iso?: string) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return null;
  }
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
  const theses = thesisData?.theses ?? [];
  const activeThesis =
    theses.find((t: Thesis) => isActiveStatus(t.status)) ?? null;
  const closedCount = theses.filter(
    (t: Thesis) => !isActiveStatus(t.status)
  ).length;

  const comparison = useThesisComparison(activeThesis?.id ?? null);
  const createThesis = useCreateThesis();
  const startNewThesis = useStartNewThesis();
  const propose = useProposeThesisFromAnalysis();
  const replay = useReplayThesis();
  const [editorOpen, setEditorOpen] = useState(false);
  const [confirmNewOpen, setConfirmNewOpen] = useState(false);
  const [diffResult, setDiffResult] = useState<ThesisComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startNewError, setStartNewError] = useState<string | null>(null);
  const [startNewSuccess, setStartNewSuccess] = useState<string | null>(null);

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

  const createdLabel = formatCreated(activeThesis?.created_at);

  const createFromLatestAnalysis = async (opts?: { skipLlmPropose?: boolean }) => {
    // Fast path for “start new”: skip /from-analysis Gemini polish; build locally.
    if (opts?.skipLlmPropose) {
      const sentiment = analysis.overall_sentiment || 'Unknown';
      const conf = analysis.overall_confidence ?? 0;
      const summary =
        (analysis.summary || '').trim().length >= 10
          ? analysis.summary!.trim()
          : `${ticker} living thesis: current catalyst read is ${sentiment} at ${Math.round(conf * 100)}% confidence.`;
      const kill = [
        'One-day drop greater than 5%',
      ];
      const body: CreateThesisRequest = {
        ticker: ticker.toUpperCase(),
        thesis_summary: summary.slice(0, 2000),
        conviction_level: conf >= 0.75 ? 'high' : conf >= 0.45 ? 'medium' : 'low',
        kill_criteria: kill,
        origin_analysis_id: analysis.id,
        origin_analysis_snapshot: snapshot,
        origin_evidence: evidenceLedger as Record<string, unknown>[] | undefined,
        structured_kill_criteria: [
          {
            id: 'kc_day_drop',
            kind: 'deterministic',
            label: 'One-day drop greater than 5%',
            metric: 'one_day_return',
            op: 'lte',
            threshold: -0.05,
          },
        ],
      };
      await createThesis.mutateAsync(body);
      return;
    }

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
  };

  const handleProposeAndCreate = async () => {
    setError(null);
    if (!user) {
      setError('Sign in to create a thesis');
      return;
    }
    try {
      await createFromLatestAnalysis();
      await refetch();
    } catch (e) {
      setError(thesisApiErrorMessage(e, 'Failed to create thesis'));
    }
  };

  const handleStartNewThesis = async () => {
    setStartNewError(null);
    setStartNewSuccess(null);
    setError(null);
    if (!user) {
      setStartNewError('Sign in to start a new thesis');
      return;
    }
    if (!activeThesis) {
      setStartNewError('No active thesis to close');
      return;
    }
    const previousId = activeThesis.id;
    try {
      const sentiment = analysis.overall_sentiment || 'Unknown';
      const conf = analysis.overall_confidence ?? 0;
      const summary =
        (analysis.summary || '').trim().length >= 10
          ? analysis.summary!.trim()
          : `${ticker} living thesis: current catalyst read is ${sentiment} at ${Math.round(conf * 100)}% confidence.`;

      const originId =
        typeof analysis.id === 'number' && Number.isFinite(analysis.id)
          ? Math.trunc(analysis.id)
          : undefined;

      const created = await startNewThesis.mutateAsync({
        ticker: ticker.toUpperCase(),
        thesis_summary: summary.slice(0, 2000),
        conviction_level: conf >= 0.75 ? 'high' : conf >= 0.45 ? 'medium' : 'low',
        kill_criteria: ['One-day drop greater than 5%'],
        origin_analysis_id: originId,
        origin_analysis_snapshot: snapshot,
        origin_evidence: Array.isArray(evidenceLedger)
          ? (evidenceLedger as Record<string, unknown>[]).slice(0, 25)
          : undefined,
        structured_kill_criteria: [
          {
            id: 'kc_day_drop',
            kind: 'deterministic',
            label: 'One-day drop greater than 5%',
            metric: 'one_day_return',
            op: 'lte',
            threshold: -0.05,
          },
        ],
        change_reason:
          'Closed to start a new active thesis from the latest analysis',
      });
      setDiffResult(null);
      setConfirmNewOpen(false);
      setStartNewError(null);
      setError(null);
      const refreshed = await refetch();
      const newest = (refreshed.data?.theses || []).find((t: Thesis) =>
        isActiveStatus(t.status)
      );
      if (!created?.id) {
        setError('New thesis create returned empty response — refresh and check Theses.');
        return;
      }
      if (newest?.id === previousId) {
        setError(
          `Close/create may have failed — still seeing thesis ${previousId.slice(0, 8)}… Refresh the page.`
        );
        return;
      }
      setStartNewSuccess(
        `New active thesis created (${created.id.slice(0, 8)}…). Previous thesis closed and kept as history.`
      );
    } catch (e) {
      const msg = thesisApiErrorMessage(e, 'Failed to start a new thesis');
      setStartNewError(msg);
      setError(msg);
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

  const pending =
    propose.isPending || createThesis.isPending || startNewThesis.isPending;
  const research = attachedEvidence.filter(
    (e) => String(e.type || '').toLowerCase() !== 'scenario'
  );
  const whatIfs = attachedEvidence.filter(
    (e) => String(e.type || '').toLowerCase() === 'scenario'
  );

  return (
    <div className="ui-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border-base px-4 py-2.5">
        <h3 className="ui-label text-txt-secondary">
          {ticker} · Living thesis
        </h3>
        <span className="font-mono text-micro tracking-wide text-txt-muted">
          {activeThesis ? 'Active' : 'No active thesis'}
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
              {createdLabel ? (
                <p className="mt-1 text-micro text-txt-muted">
                  Created {createdLabel}
                  {closedCount > 0
                    ? ` · ${closedCount} prior thesis${closedCount === 1 ? '' : 'es'} closed`
                    : ''}
                </p>
              ) : null}
              <p className="mt-1.5 text-sm leading-relaxed text-txt-secondary">
                {thesisCopy.body}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                onClick={handleReplay}
                disabled={replay.isPending || pending}
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
                disabled={pending}
                className="h-8"
              >
                Edit thesis
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setConfirmNewOpen(true)}
                disabled={!user || pending}
                className="h-8"
              >
                Start new thesis
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
          <div className="space-y-3">
            {closedCount > 0 ? (
              <p className="text-sm text-txt-secondary">
                No active thesis. {closedCount} prior thesis
                {closedCount === 1 ? '' : 'es'} preserved as history.
              </p>
            ) : null}
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
          </div>
        )}

        {startNewSuccess && (
          <p className="rounded-md border border-bull/40 bg-bull/10 px-3 py-2 text-sm text-bull">
            {startNewSuccess}
          </p>
        )}

        {error && <p className="text-sm text-bear">{error}</p>}
      </div>

      {confirmNewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-md border border-border-base bg-surface-1 p-5 shadow-xl">
            <h4 className="text-sm font-semibold text-txt-primary">
              Start a new {ticker} thesis?
            </h4>
            <p className="mt-2 text-sm leading-relaxed text-txt-secondary">
              {ticker} already has an active thesis. Starting a new one will{' '}
              <span className="text-txt-primary">close</span> the current
              thesis (history, attachments, and origin evidence stay preserved)
              and create a new <span className="text-txt-primary">active</span>{' '}
              thesis from the latest analysis.
            </p>
            {startNewError ? (
              <div className="mt-3 rounded-md border border-bear/40 bg-bear/10 px-3 py-2 text-sm text-bear">
                {startNewError}
              </div>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={startNewThesis.isPending}
                onClick={() => {
                  setConfirmNewOpen(false);
                  setStartNewError(null);
                }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={startNewThesis.isPending}
                onClick={() => void handleStartNewThesis()}
                className="gap-2"
              >
                {startNewThesis.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : null}
                Close current & create new
              </Button>
            </div>
          </div>
        </div>
      )}

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
