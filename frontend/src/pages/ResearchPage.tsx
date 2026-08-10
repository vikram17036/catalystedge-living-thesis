import { useState } from 'react';
import { FlaskConical, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import {
  runEventStudy,
  type EventStudyResponse,
  type EventStudySpec,
  type WindowStats,
} from '../api/eventStudy';
import { attachEvidenceByTicker, thesisKeys } from '../api/theses';
import { cn } from '../utils/cn';

const CHIPS = [
  'What happens to NVDA around FOMC decisions?',
  'Only rate hikes.',
  'Compare five days before with five days after.',
];

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${(v * 100).toFixed(2)}%`;
}

function rate(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

function StatsRow({ label, stats }: { label: string; stats: WindowStats }) {
  return (
    <tr className="border-b border-border-base/60">
      <td className="py-2 pr-4 font-mono text-micro uppercase tracking-widest text-txt-muted">
        {label}
      </td>
      <td className="py-2 px-3 font-mono text-sm text-txt-primary">{pct(stats.mean)}</td>
      <td className="py-2 px-3 font-mono text-sm text-txt-primary">{pct(stats.median)}</td>
      <td className="py-2 px-3 font-mono text-sm text-txt-primary">
        {rate(stats.positive_rate)}
      </td>
    </tr>
  );
}

export default function ResearchPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState(CHIPS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<EventStudyResponse | null>(null);
  const [showObs, setShowObs] = useState(false);
  const [showWhy, setShowWhy] = useState(true);
  const [attachMsg, setAttachMsg] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);

  const priorSpec: EventStudySpec | null = response?.spec ?? null;

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
      const data = await runEventStudy(q, priorSpec, true);
      setResponse(data);
      setQuestion('');
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (e as { message?: string })?.message ||
        'Event study failed';
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
        RESEARCH
      </p>
      <h1 className="mt-2 font-mono text-2xl font-bold tracking-tight text-txt-primary">
        Historical Event Study
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
        Natural language defines the experiment. Deterministic code owns every return.
        The model may only interpret measured results.
      </p>

      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) void submit(question.trim());
        }}
      >
        <label className="font-mono text-micro uppercase tracking-widest text-txt-muted">
          Ask a historical market question
        </label>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder='e.g. What happens to NVDA around FOMC decisions?'
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
              <FlaskConical className="h-4 w-4" />
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
            key={`${spec.ticker}-${spec.event_filter}-${spec.pre_window}-${result.events_analyzed}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-6"
          >
            {/* Experiment Card */}
            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="font-mono text-lg font-bold text-txt-primary">
                  {spec.ticker} × FOMC
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

              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <div className="font-mono text-micro uppercase tracking-widest text-txt-muted">
                    Filter
                  </div>
                  <div className="mt-1 font-mono text-sm font-bold uppercase text-accent">
                    {response.spec_diff &&
                    typeof response.spec_diff === 'object' &&
                    'event_filter' in response.spec_diff ? (
                      <span>
                        {(response.spec_diff as { event_filter: { from: string; to: string } })
                          .event_filter.from?.toUpperCase()}{' '}
                        → {spec.event_filter.toUpperCase()}
                      </span>
                    ) : (
                      spec.event_filter
                    )}
                  </div>
                </div>
                <div>
                  <div className="font-mono text-micro uppercase tracking-widest text-txt-muted">
                    Window
                  </div>
                  <div className="mt-1 font-mono text-sm text-txt-primary">
                    {spec.pre_window}d before · event day · {spec.post_window}d after
                  </div>
                </div>
                <div>
                  <div className="font-mono text-micro uppercase tracking-widest text-txt-muted">
                    Sample
                  </div>
                  <div className="mt-1 font-mono text-sm text-txt-primary">
                    {result.calendar_events} calendar · {result.eligible_events} eligible ·{' '}
                    {result.events_analyzed} analyzed
                    {result.excluded_events > 0
                      ? ` · ${result.excluded_events} excluded`
                      : ''}
                  </div>
                </div>
              </div>
            </section>

            {/* Stats */}
            <section className="overflow-x-auto rounded-sm border border-border-base bg-surface-1 p-5">
              <table className="w-full min-w-[320px] text-left">
                <thead>
                  <tr className="border-b border-border-base">
                    <th className="pb-2 font-mono text-micro uppercase tracking-widest text-txt-muted">
                      Window
                    </th>
                    <th className="pb-2 px-3 font-mono text-micro uppercase tracking-widest text-txt-muted">
                      Mean
                    </th>
                    <th className="pb-2 px-3 font-mono text-micro uppercase tracking-widest text-txt-muted">
                      Median
                    </th>
                    <th className="pb-2 px-3 font-mono text-micro uppercase tracking-widest text-txt-muted">
                      Positive
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <StatsRow label="Before" stats={result.pre_stats} />
                  <StatsRow label="Event" stats={result.event_stats} />
                  <StatsRow label="After" stats={result.post_stats} />
                </tbody>
              </table>
            </section>

            {/* Interpretation */}
            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="font-mono text-micro uppercase tracking-widest text-txt-muted">
                Interpretation · {response.interpretation.mode}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-txt-primary">
                {response.interpretation.summary}
              </p>
              {response.interpretation.caveats?.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-txt-secondary">
                  {response.interpretation.caveats.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              )}
            </section>

            {/* WHY / Spec diff */}
            <section className="rounded-sm border border-border-base bg-surface-1">
              <button
                type="button"
                onClick={() => setShowWhy((v) => !v)}
                className="flex w-full items-center gap-2 px-5 py-3 font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary hover:text-accent"
              >
                {showWhy ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Why / reproducibility
              </button>
              {showWhy && (
                <div className="space-y-2 overflow-x-auto border-t border-border-base bg-surface-2/40 px-5 py-3 font-mono text-micro text-txt-secondary">
                  <p>
                    {result.reproducibility.engine_version} · {spec.calendar_id}
                  </p>
                  <p className="break-all">
                    Price hash · {result.reproducibility.price_data_hash}
                  </p>
                  <pre className="overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(response.spec_diff, null, 2)}
                  </pre>
                </div>
              )}
            </section>

            {/* Observations */}
            <section className="rounded-sm border border-border-base bg-surface-1">
              <button
                type="button"
                onClick={() => setShowObs((v) => !v)}
                className="flex w-full items-center gap-2 px-5 py-3 font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary hover:text-accent"
              >
                {showObs ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Observations ({result.observations.length})
              </button>
              {showObs && (
                <div className="overflow-x-auto border-t border-border-base">
                  <table className="w-full min-w-[520px] text-left text-xs">
                    <thead>
                      <tr className="border-b border-border-base bg-surface-2/40">
                        <th className="px-3 py-2 font-mono text-micro uppercase text-txt-muted">
                          Date
                        </th>
                        <th className="px-3 py-2 font-mono text-micro uppercase text-txt-muted">
                          Class
                        </th>
                        <th className="px-3 py-2 font-mono text-micro uppercase text-txt-muted">
                          Pre
                        </th>
                        <th className="px-3 py-2 font-mono text-micro uppercase text-txt-muted">
                          Event
                        </th>
                        <th className="px-3 py-2 font-mono text-micro uppercase text-txt-muted">
                          Post
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.observations.map((o) => (
                        <tr
                          key={o.event_date}
                          className="border-b border-border-base/50"
                        >
                          <td className="px-3 py-1.5 font-mono">{o.event_date}</td>
                          <td className="px-3 py-1.5 font-mono uppercase">{o.classification}</td>
                          <td
                            className={cn(
                              'px-3 py-1.5 font-mono',
                              o.pre_return >= 0 ? 'text-bull' : 'text-kill'
                            )}
                          >
                            {pct(o.pre_return)}
                          </td>
                          <td
                            className={cn(
                              'px-3 py-1.5 font-mono',
                              o.event_return >= 0 ? 'text-bull' : 'text-kill'
                            )}
                          >
                            {pct(o.event_return)}
                          </td>
                          <td
                            className={cn(
                              'px-3 py-1.5 font-mono',
                              o.post_return >= 0 ? 'text-bull' : 'text-kill'
                            )}
                          >
                            {pct(o.post_return)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {result.exclusions.length > 0 && (
                    <div className="border-t border-border-base px-5 py-3 font-mono text-micro text-txt-muted">
                      Exclusions:{' '}
                      {result.exclusions
                        .map((x) => `${x.date} (${x.reason})`)
                        .join(', ')}
                    </div>
                  )}
                </div>
              )}
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
