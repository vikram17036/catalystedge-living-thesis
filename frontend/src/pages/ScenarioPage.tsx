import { useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { runScenario, type ScenarioResponse, type ScenarioSpec } from '../api/scenarioLab';
import { attachEvidenceByTicker, thesisKeys } from '../api/theses';

const CHIPS = [
  'What if NVDA drops 10% in one day?',
  'Make it a 5% drop.',
];

function Bucket({
  title,
  items,
  accent,
}: {
  title: string;
  items: { id: string; label: string; detail?: string | null }[];
  accent?: boolean;
}) {
  return (
    <div className="rounded-sm border border-border-base/60 bg-surface-2/40 p-3">
      <p
        className={`font-mono text-micro font-bold uppercase tracking-widest ${
          accent ? 'text-kill' : 'text-txt-muted'
        }`}
      >
        {title} ({items.length})
      </p>
      {items.length === 0 ? (
        <p className="mt-1 font-mono text-micro text-txt-muted">—</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {items.map((c) => (
            <li key={c.id} className="font-mono text-sm text-txt-secondary">
              {accent ? '! ' : ''}
              {c.label}
              {c.detail ? (
                <span className="block text-micro text-txt-muted">
                  {c.detail.replace(/_/g, ' ')}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ScenarioPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState(CHIPS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ScenarioResponse | null>(null);
  const [attachMsg, setAttachMsg] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);

  const priorSpec: ScenarioSpec | null = response?.spec ?? null;

  async function attachToThesis() {
    const ev = response?.evidence_ledger?.[0];
    const ticker = response?.spec?.ticker;
    if (!ev || !ticker) {
      setAttachMsg('No what-if to attach.');
      return;
    }
    setAttaching(true);
    setAttachMsg(null);
    try {
      const res = await attachEvidenceByTicker(ticker, ev);
      const n = res.thesis?.attached_evidence?.length ?? 0;
      setAttachMsg(
        res.already_attached
          ? `Already attached (${n} on thesis).`
          : `Attached WHAT-IF (${n} on thesis — origin unchanged).`
      );
      await queryClient.invalidateQueries({ queryKey: thesisKeys.all });
      await queryClient.invalidateQueries({ queryKey: thesisKeys.byTicker(ticker) });
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Attach failed';
      setAttachMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setAttaching(false);
    }
  }

  async function submit(q: string) {
    if (!user) {
      setError('Sign in required (header AUTH).');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await runScenario(q, priorSpec);
      setResponse(data);
      setQuestion('');
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Scenario failed';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }

  const result = response?.result;
  const spec = response?.spec;

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-5xl">
      <p className="font-mono text-micro font-bold uppercase tracking-widest text-accent">
        SCENARIOS
      </p>
      <h1 className="mt-2 font-mono text-2xl font-bold tracking-tight text-txt-primary">
        Scenario Lab
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
        Stress a living thesis with a typed what-if. Code evaluates kill criteria on the
        shocked metric only — this never rewrites origin evidence or Diff.
      </p>

      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) void submit(question.trim());
        }}
      >
        <label className="font-mono text-micro uppercase tracking-widest text-txt-muted">
          Ask a what-if
        </label>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What if NVDA drops 10% in one day?"
            className="flex-1 rounded-sm border border-border-base bg-surface-1 px-3 py-2.5 font-mono text-sm text-txt-primary outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-2 rounded-sm border border-accent bg-accent/10 px-4 py-2 font-mono text-micro font-bold uppercase tracking-widest text-accent hover:bg-accent/20 disabled:opacity-40"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <AlertTriangle className="h-4 w-4" />}
            Run
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => setQuestion(chip)}
              className="rounded-sm border border-border-base bg-surface-2 px-2.5 py-1 font-mono text-micro text-txt-secondary hover:border-accent hover:text-accent"
            >
              {chip}
            </button>
          ))}
        </div>
      </form>

      {error && (
        <div className="mt-4 rounded-sm border border-kill/40 bg-kill/10 px-3 py-2 font-mono text-sm text-kill">
          {error}
        </div>
      )}

      <AnimatePresence mode="wait">
        {result && spec && (
          <motion.div
            key={`${spec.ticker}-${spec.shock_value}-${result.reproducibility.criteria_hash}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-6"
          >
            <section className="rounded-sm border border-accent/40 bg-surface-1 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="font-mono text-lg font-bold text-accent">
                  What-if · {spec.ticker}
                </h2>
                <button
                  type="button"
                  onClick={() => void attachToThesis()}
                  disabled={attaching}
                  className="rounded-md border border-accent bg-accent/10 px-2.5 py-1 text-micro font-semibold tracking-wide text-accent hover:bg-accent/20 disabled:opacity-40"
                >
                  {attaching ? '…' : 'Attach what-if'}
                </button>
              </div>
              {attachMsg && (
                <p className="mt-2 font-mono text-micro text-txt-secondary">{attachMsg}</p>
              )}
              <p className="mt-3 text-sm font-medium text-txt-primary">
                One-day return shock ·{' '}
                {spec.shock_value < 0 ? '−' : '+'}
                {(Math.abs(spec.shock_value) * 100).toFixed(1)}%
              </p>
              <p className="mt-1 font-mono text-micro text-txt-muted">
                {spec.shock_metric} = {spec.shock_value}
              </p>
              <p className="mt-2 font-mono text-micro text-txt-muted uppercase tracking-wide">
                Evaluated {result.criteria_evaluated} · Triggered {result.criteria_triggered} ·
                Skipped unrelated {result.criteria_skipped_unaffected} · Skipped qualitative{' '}
                {result.criteria_skipped_qualitative}
              </p>
              <p className="mt-3 font-mono text-micro text-txt-secondary">
                {response.disclaimer}
              </p>
            </section>

            <div className="grid gap-3 sm:grid-cols-2">
              <Bucket title="Triggered" items={result.triggered_criteria} accent />
              <Bucket title="Not triggered" items={result.not_triggered_criteria} />
              <Bucket title="Skipped unaffected metric" items={result.skipped_unaffected_metric} />
              <Bucket title="Skipped qualitative" items={result.skipped_qualitative} />
            </div>

            {response.interpretation && (
              <section className="rounded-sm border border-border-base bg-surface-1 p-5">
                <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
                  Interpretation
                </h3>
                <p className="mt-2 font-mono text-sm text-txt-secondary">
                  {response.interpretation.summary}
                </p>
              </section>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
