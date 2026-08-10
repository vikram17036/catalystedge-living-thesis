import { useState } from 'react';
import { GitCompare, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import {
  runAnalogSearch,
  type AnalogSearchResponse,
  type AnalogSpec,
} from '../api/analogSearch';
import { attachEvidenceByTicker, thesisKeys } from '../api/theses';

const CHIPS = [
  'Find past periods that look like the last 20 trading days for NVDA.',
  'What happened over the next 10 days?',
  'Top 5 analogs.',
];

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${(v * 100).toFixed(2)}%`;
}

export default function AnalogsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState(CHIPS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AnalogSearchResponse | null>(null);
  const [attachMsg, setAttachMsg] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);

  const priorSpec: AnalogSpec | null = response?.spec ?? null;

  async function attachToThesis() {
    const ev = response?.evidence_ledger?.[0];
    const ticker = response?.spec?.ticker;
    if (!ev || !ticker) {
      setAttachMsg('No evidence to attach.');
      return;
    }
    setAttaching(true);
    setAttachMsg(null);
    try {
      const res = await attachEvidenceByTicker(ticker, ev);
      const n = res.thesis?.attached_evidence?.length ?? 0;
      setAttachMsg(
        res.already_attached
          ? `Already attached (${n} on thesis). Open the living thesis on the dashboard.`
          : `Attached (${n} on thesis — origin unchanged). Open the living thesis on the dashboard.`
      );
      await queryClient.invalidateQueries({ queryKey: thesisKeys.all });
      await queryClient.invalidateQueries({
        queryKey: thesisKeys.byTicker(ticker),
      });
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
      const data = await runAnalogSearch(q, priorSpec);
      setResponse(data);
      setQuestion('');
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Analog search failed';
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
        ANALOGS
      </p>
      <h1 className="mt-2 font-mono text-2xl font-bold tracking-tight text-txt-primary">
        Historical Analog Search
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
        Code ranks shape-similar past return paths. The model may only interpret measured
        distances and forward outcomes — never pick the matches.
      </p>

      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) void submit(question.trim());
        }}
      >
        <label className="font-mono text-micro uppercase tracking-widest text-txt-muted">
          Ask for historical lookalikes
        </label>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Find past periods that look like the last 20 trading days for NVDA."
            className="flex-1 rounded-sm border border-border-base bg-surface-1 px-3 py-2.5 font-mono text-sm text-txt-primary outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-2 rounded-sm border border-accent bg-accent/10 px-4 py-2 font-mono text-micro font-bold uppercase tracking-widest text-accent hover:bg-accent/20 disabled:opacity-40"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <GitCompare className="h-4 w-4" />
            )}
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
            key={`${spec.ticker}-${spec.lookback}-${spec.post_window}-${result.matches_returned}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-6"
          >
            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="font-mono text-lg font-bold text-txt-primary">
                  {spec.ticker} · shape analogs
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void attachToThesis()}
                    disabled={attaching}
                    className="rounded-md border border-accent bg-accent/10 px-2.5 py-1 text-micro font-semibold tracking-wide text-accent hover:bg-accent/20 disabled:opacity-40"
                  >
                    {attaching ? '…' : 'Attach to thesis'}
                  </button>
                </div>
              </div>
              {attachMsg && (
                <p className="mt-2 font-mono text-micro text-txt-secondary">{attachMsg}</p>
              )}

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="rounded-sm border border-border-base/60 bg-surface-2/40 p-3">
                  <div className="font-mono text-micro uppercase tracking-widest text-accent">
                    Similarity query
                  </div>
                  <p className="mt-1 font-mono text-sm text-txt-primary">
                    Lookback {spec.lookback}d · within-window z-scored returns · Euclidean
                  </p>
                </div>
                <div className="rounded-sm border border-border-base/60 bg-surface-2/40 p-3">
                  <div className="font-mono text-micro uppercase tracking-widest text-accent">
                    Forward horizon
                  </div>
                  <p className="mt-1 font-mono text-sm text-txt-primary">
                    {spec.post_window}d · mean {pct(result.forward_mean)} · median{' '}
                    {pct(result.forward_median)} · hit {pct(result.positive_hit_rate)}
                  </p>
                </div>
              </div>

              <p className="mt-4 font-mono text-sm text-txt-secondary tracking-wide">
                Sample: {result.candidate_windows} candidates → {result.eligible_windows}{' '}
                eligible → {result.matches_returned} returned · excluded overlap{' '}
                {result.excluded_overlap} · lookahead {result.excluded_lookahead} · coverage{' '}
                {result.excluded_future_coverage}
              </p>
              <p className="mt-2 font-mono text-micro text-txt-muted">
                {result.reproducibility.engine_version} · target{' '}
                {result.reproducibility.target_end}
              </p>
            </section>

            <section className="rounded-sm border border-border-base bg-surface-1 p-5 overflow-x-auto">
              <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
                Distinct analogs
              </h3>
              <table className="mt-3 w-full text-left">
                <thead>
                  <tr className="border-b border-border-base font-mono text-micro uppercase tracking-widest text-txt-muted">
                    <th className="py-2 pr-3">Endpoint</th>
                    <th className="py-2 px-3">Lookback</th>
                    <th className="py-2 px-3">Distance</th>
                    <th className="py-2 px-3">Fwd {spec.post_window}d</th>
                  </tr>
                </thead>
                <tbody>
                  {result.matches.map((m) => (
                    <tr key={m.endpoint} className="border-b border-border-base/60">
                      <td className="py-2 pr-3 font-mono text-sm text-txt-primary">
                        {m.endpoint}
                      </td>
                      <td className="py-2 px-3 font-mono text-sm text-txt-secondary">
                        {m.lookback_start} → {m.lookback_end}
                      </td>
                      <td className="py-2 px-3 font-mono text-sm text-txt-primary">
                        {m.distance.toFixed(4)}
                      </td>
                      <td className="py-2 px-3 font-mono text-sm text-txt-primary">
                        {pct(m.forward_return)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            {response.interpretation && (
              <section className="rounded-sm border border-border-base bg-surface-1 p-5">
                <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
                  Interpretation
                </h3>
                <p className="mt-2 font-mono text-sm text-txt-secondary leading-relaxed">
                  {response.interpretation.summary}
                </p>
              </section>
            )}

            {response.spec_diff && Object.keys(response.spec_diff).length > 0 && (
              <section className="rounded-sm border border-border-base bg-surface-1 p-5">
                <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
                  Spec diff
                </h3>
                <pre className="mt-2 overflow-x-auto font-mono text-micro text-txt-secondary">
                  {JSON.stringify(response.spec_diff, null, 2)}
                </pre>
              </section>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
