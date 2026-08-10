/**
 * ThesisEditor — create / edit / start-new living thesis
 * Shows analysis confidence & themes when drafting from latest analysis.
 */

import { useState, useEffect } from 'react';
import { X, Save, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../context/AuthContext';
import {
  useCreateThesis,
  useUpdateThesis,
  useStartNewThesis,
  thesisApiErrorMessage,
} from '../api/theses';
import type {
  Thesis,
  CreateThesisRequest,
  AnalysisSnapshot,
} from '../types/thesis';

export type ThesisEditorMode = 'create' | 'edit' | 'start-new';

interface ThesisEditorProps {
  isOpen: boolean;
  onClose: () => void;
  ticker: string;
  mode?: ThesisEditorMode;
  existingThesis?: Thesis | null;
  analysisSnapshot?: AnalysisSnapshot | null;
  originEvidence?: Record<string, unknown>[];
  originAnalysisId?: number;
  /** Prefill when creating / starting new (from latest analysis). */
  draftDefaults?: {
    thesis_summary?: string;
    conviction_level?: 'low' | 'medium' | 'high';
    kill_criteria?: string[];
  } | null;
  onSuccess?: (created?: Thesis) => void;
}

const CONVICTION_LEVELS = [
  { value: 'low', label: 'LOW', description: 'Speculative' },
  { value: 'medium', label: 'MED', description: 'Reasonable' },
  { value: 'high', label: 'HIGH', description: 'Strong' },
] as const;

function defaultKillLine() {
  return 'One-day drop greater than 5%';
}

function convictionFromConfidence(conf: number): 'low' | 'medium' | 'high' {
  if (conf >= 0.75) return 'high';
  if (conf >= 0.45) return 'medium';
  return 'low';
}

export default function ThesisEditor({
  isOpen,
  onClose,
  ticker,
  mode: modeProp,
  existingThesis,
  analysisSnapshot,
  originEvidence,
  originAnalysisId,
  draftDefaults,
  onSuccess,
}: ThesisEditorProps) {
  const { user } = useAuth();
  const createThesis = useCreateThesis();
  const updateThesis = useUpdateThesis();
  const startNewThesis = useStartNewThesis();

  const mode: ThesisEditorMode =
    modeProp || (existingThesis ? 'edit' : 'create');

  const [thesisSummary, setThesisSummary] = useState('');
  const [convictionLevel, setConvictionLevel] = useState<
    'low' | 'medium' | 'high'
  >('medium');
  const [killCriteria, setKillCriteria] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);

    if (mode === 'edit' && existingThesis) {
      setThesisSummary(existingThesis.thesis_summary);
      setConvictionLevel(existingThesis.conviction_level);
      setKillCriteria(existingThesis.kill_criteria.join('\n'));
      return;
    }

    const conf = analysisSnapshot?.confidence ?? 0;
    const summary =
      (draftDefaults?.thesis_summary || '').trim() ||
      (analysisSnapshot
        ? `${ticker} living thesis: ${analysisSnapshot.sentiment} at ${Math.round(conf * 100)}% confidence.`
        : '');
    const conviction =
      draftDefaults?.conviction_level ||
      convictionFromConfidence(conf);
    const kills =
      draftDefaults?.kill_criteria?.length
        ? draftDefaults.kill_criteria.join('\n')
        : defaultKillLine();

    setThesisSummary(summary.slice(0, 2000));
    setConvictionLevel(conviction);
    setKillCriteria(kills);
  }, [
    isOpen,
    mode,
    existingThesis,
    analysisSnapshot,
    draftDefaults,
    ticker,
  ]);

  if (!isOpen) return null;

  if (!user) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="mx-4 w-full max-w-md overflow-hidden rounded-sm border border-border-base bg-surface-1">
          <div className="p-6 text-center">
            <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-accent" />
            <h3 className="mb-2 font-mono text-lg font-bold uppercase tracking-wider text-txt-primary">
              AUTH_REQUIRED
            </h3>
            <p className="mb-4 font-mono text-micro uppercase tracking-widest text-txt-muted">
              Sign in required to save theses.
            </p>
            <Button
              variant="outline"
              onClick={onClose}
              className="rounded-sm border-border-base font-mono text-micro uppercase tracking-widest"
            >
              [CLOSE]
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (thesisSummary.trim().length < 10) {
      setError('Please provide a more detailed thesis (at least 10 characters)');
      return;
    }

    const killCriteriaList = killCriteria
      .split('\n')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    const structured =
      killCriteriaList.length > 0
        ? [
            {
              id: 'kc_day_drop',
              kind: 'deterministic' as const,
              label: killCriteriaList[0],
              metric: 'one_day_return',
              op: 'lte' as const,
              threshold: -0.05,
            },
          ]
        : undefined;

    try {
      if (mode === 'edit' && existingThesis) {
        await updateThesis.mutateAsync({
          thesisId: existingThesis.id,
          updates: {
            thesis_summary: thesisSummary.trim(),
            conviction_level: convictionLevel,
            kill_criteria: killCriteriaList,
            change_reason: 'Updated thesis',
          },
        });
        onSuccess?.();
        onClose();
        return;
      }

      const payload: CreateThesisRequest & { change_reason?: string } = {
        ticker: ticker.toUpperCase(),
        thesis_summary: thesisSummary.trim().slice(0, 2000),
        conviction_level: convictionLevel,
        kill_criteria: killCriteriaList,
        origin_analysis_id:
          typeof originAnalysisId === 'number' &&
          Number.isFinite(originAnalysisId)
            ? Math.trunc(originAnalysisId)
            : undefined,
        origin_analysis_snapshot: analysisSnapshot || undefined,
        origin_evidence: originEvidence?.slice(0, 25),
        structured_kill_criteria: structured,
        change_reason:
          mode === 'start-new'
            ? 'Closed to start a new active thesis from the latest analysis'
            : undefined,
      };

      if (mode === 'start-new') {
        const created = await startNewThesis.mutateAsync(payload);
        onSuccess?.(created);
        onClose();
        return;
      }

      const created = await createThesis.mutateAsync(payload);
      onSuccess?.(created);
      onClose();
    } catch (err) {
      setError(thesisApiErrorMessage(err, 'Failed to save thesis'));
    }
  };

  const isLoading =
    createThesis.isPending ||
    updateThesis.isPending ||
    startNewThesis.isPending;

  const title =
    mode === 'edit'
      ? `EDIT_THESIS: ${ticker}`
      : mode === 'start-new'
        ? `START_NEW_THESIS: ${ticker}`
        : `CREATE_THESIS: ${ticker}`;

  const subtitle =
    mode === 'start-new'
      ? 'Review confidence & customize, then close current and create'
      : mode === 'edit'
        ? 'Update your belief record'
        : 'Record why you care about this asset';

  const confPct = Math.round((analysisSnapshot?.confidence ?? 0) * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-sm border border-border-base bg-surface-1">
        <div className="relative border-b border-border-base bg-surface-2 px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-3 top-3 rounded-sm p-1 text-txt-muted transition-colors hover:bg-surface-3 hover:text-txt-primary"
          >
            <X className="h-4 w-4" />
          </button>
          <h2 className="font-mono text-sm font-bold uppercase tracking-widest text-txt-primary">
            {title}
          </h2>
          <p className="mt-1 font-mono text-micro uppercase tracking-widest text-txt-muted">
            {subtitle}
          </p>
        </div>

        <div className="bg-canvas p-4">
          {analysisSnapshot && mode !== 'edit' ? (
            <div className="mb-4 rounded-sm border border-border-base bg-surface-1 px-3 py-2.5">
              <p className="font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary">
                Latest analysis
              </p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-sm text-txt-primary">
                <span>
                  Sentiment:{' '}
                  <span className="text-accent">
                    {analysisSnapshot.sentiment || '—'}
                  </span>
                </span>
                <span>
                  Confidence:{' '}
                  <span className="text-accent">{confPct}%</span>
                </span>
                {analysisSnapshot.skeptic_verdict ? (
                  <span>
                    Skeptic:{' '}
                    <span className="text-txt-secondary">
                      {analysisSnapshot.skeptic_verdict}
                    </span>
                  </span>
                ) : null}
              </div>
              {analysisSnapshot.key_themes?.length ? (
                <p className="mt-2 text-micro leading-relaxed text-txt-secondary">
                  Themes: {analysisSnapshot.key_themes.slice(0, 5).join(' · ')}
                </p>
              ) : null}
              <p className="mt-2 text-micro text-txt-muted">
                Conviction below is yours to set — analysis confidence is shown
                above for reference.
              </p>
            </div>
          ) : null}

          {mode === 'start-new' ? (
            <p className="mb-4 text-sm leading-relaxed text-txt-secondary">
              Saving will <span className="text-txt-primary">close</span> the
              current active thesis (history kept) and create a new{' '}
              <span className="text-txt-primary">active</span> one with your
              edits.
            </p>
          ) : null}

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div className="space-y-2">
              <label className="font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary">
                THESIS_SUMMARY
              </label>
              <textarea
                value={thesisSummary}
                onChange={(e) => setThesisSummary(e.target.value)}
                placeholder="I believe this company will... because..."
                required
                minLength={10}
                rows={5}
                className="w-full resize-none rounded-sm border border-border-base bg-surface-1 px-3 py-2 font-mono text-sm text-txt-primary placeholder:text-txt-muted/50 focus:border-border-focus focus:outline-none"
              />
            </div>

            <div className="space-y-2">
              <label className="font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary">
                YOUR_CONVICTION
              </label>
              <div className="grid grid-cols-3 gap-2">
                {CONVICTION_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    type="button"
                    onClick={() => setConvictionLevel(level.value)}
                    className={`rounded-sm border p-3 text-center transition-colors ${
                      convictionLevel === level.value
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-border-base bg-surface-1 text-txt-muted hover:border-border-strong hover:text-txt-secondary'
                    }`}
                  >
                    <span className="block font-mono text-micro font-bold uppercase tracking-widest">
                      {level.label}
                    </span>
                    <span className="mt-0.5 block font-mono text-micro uppercase tracking-wider text-txt-muted/70">
                      {level.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary">
                KILL_CRITERIA
              </label>
              <p className="font-mono text-micro uppercase tracking-wider text-txt-muted">
                What conditions would make you exit? One per line.
              </p>
              <textarea
                value={killCriteria}
                onChange={(e) => setKillCriteria(e.target.value)}
                placeholder={
                  'Revenue growth slows below 10%\nCEO leaves the company\nMajor competitor enters market'
                }
                rows={3}
                className="w-full resize-none rounded-sm border border-border-base bg-surface-1 px-3 py-2 font-mono text-sm text-txt-primary placeholder:text-txt-muted/50 focus:border-border-focus focus:outline-none"
              />
            </div>

            {error ? (
              <p className="font-mono text-micro font-bold uppercase tracking-widest text-kill">
                {error}
              </p>
            ) : null}

            <div className="flex gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                onClick={onClose}
                disabled={isLoading}
                className="h-9 flex-1 rounded-sm border border-border-base font-mono text-micro uppercase tracking-widest hover:bg-surface-2"
              >
                [CANCEL]
              </Button>
              <Button
                type="submit"
                disabled={isLoading}
                className="h-9 flex-1 gap-2 rounded-sm border border-accent bg-accent/10 font-mono text-micro uppercase tracking-widest text-accent hover:bg-accent/20"
              >
                {isLoading ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Save className="h-3 w-3" />
                )}
                {mode === 'edit'
                  ? '[UPDATE]'
                  : mode === 'start-new'
                    ? '[CLOSE & CREATE]'
                    : '[SAVE]'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
