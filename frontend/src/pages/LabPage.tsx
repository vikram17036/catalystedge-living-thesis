import { useState } from 'react';
import { Loader2, LineChart } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import {
  runBacktest,
  type BacktestResponse,
  type BacktestResult,
  type StrategySpec,
} from '../api/strategyLab';
import { attachEvidenceByTicker, thesisKeys } from '../api/theses';

const CHIPS = [
  'Backtest a 20/50 SMA crossover on NVDA since 2020.',
  'Add 5 bps commission and 2 bps slippage.',
  'Show max drawdown and hit rate.',
];

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${(v * 100).toFixed(2)}%`;
}

export default function LabPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState(CHIPS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<BacktestResponse | null>(null);
  const [showWhy, setShowWhy] = useState(true);
  const [attachMsg, setAttachMsg] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);

  const priorSpec: StrategySpec | null = response?.spec ?? null;
  const priorResult: BacktestResult | null = response?.result ?? null;

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
          ? `Already attached (${n} on thesis). Open dashboard LIVING_THESIS.`
          : `Attached (${n} on thesis — origin unchanged). Open dashboard LIVING_THESIS.`
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
      const data = await runBacktest(q, priorSpec, priorResult);
      setResponse(data);
      setQuestion('');
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Backtest failed';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }

  const result = response?.result;
  const spec = response?.spec;
  const m = result?.metrics;

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-5xl">
      <p className="font-mono text-micro font-bold uppercase tracking-widest text-accent">
        LAB
      </p>
      <h1 className="mt-2 font-mono text-2xl font-bold tracking-tight text-txt-primary">
        Strategy Lab
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
        Typed long-only SMA crossover. Signal at t, fill at t+1. No exec() of LLM code.
      </p>

      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) void submit(question.trim());
        }}
      >
        <label className="font-mono text-micro uppercase tracking-widest text-txt-muted">
          Describe a strategy to simulate
        </label>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="flex-1 rounded-sm border border-border-base bg-surface-1 px-3 py-2.5 font-mono text-sm text-txt-primary outline-none focus:border-accent"
            placeholder={CHIPS[0]}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-2 rounded-sm border border-accent bg-accent/10 px-4 py-2 font-mono text-micro font-bold uppercase tracking-widest text-accent disabled:opacity-40"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LineChart className="h-4 w-4" />}
            Run
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => {
                setQuestion(chip);
                void submit(chip);
              }}
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
        {result && spec && m && (
          <motion.div
            key={`${spec.ticker}-${spec.commission_bps}-${spec.slippage_bps}-${response.mode}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-6"
          >
            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="font-mono text-lg font-bold text-txt-primary">
                  {spec.ticker} · SMA CROSSOVER
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-micro uppercase text-txt-muted">
                    {result.reproducibility.engine_version} · mode={response.mode}
                  </span>
                  <button
                    type="button"
                    onClick={() => void attachToThesis()}
                    disabled={attaching}
                    className="rounded-sm border border-accent bg-accent/10 px-2.5 py-1 font-mono text-micro font-bold uppercase tracking-widest text-accent disabled:opacity-40"
                  >
                    {attaching ? '…' : 'ATTACH_TO_THESIS'}
                  </button>
                </div>
              </div>
              {attachMsg && (
                <p className="mt-2 font-mono text-micro text-txt-secondary">{attachMsg}</p>
              )}
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <div className="font-mono text-micro uppercase text-txt-muted">Fast / Slow</div>
                  <div className="mt-1 font-mono text-sm text-accent">
                    {spec.strategy.fast_window}D / {spec.strategy.slow_window}D
                  </div>
                </div>
                <div>
                  <div className="font-mono text-micro uppercase text-txt-muted">Period</div>
                  <div className="mt-1 font-mono text-sm">{spec.start} → {spec.end || 'latest'}</div>
                </div>
                <div>
                  <div className="font-mono text-micro uppercase text-txt-muted">Costs / side</div>
                  <div className="mt-1 font-mono text-sm">
                    Comm {spec.commission_bps} bps · Slip {spec.slippage_bps} bps
                  </div>
                </div>
                <div>
                  <div className="font-mono text-micro uppercase text-txt-muted">Trades</div>
                  <div className="mt-1 font-mono text-sm">{m.n_trades}</div>
                </div>
              </div>
            </section>

            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="font-mono text-micro uppercase text-txt-muted mb-3">Result</div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <div className="text-micro text-txt-muted">NET RETURN</div>
                  <div className="font-mono text-lg">{pct(m.total_return)}</div>
                </div>
                <div>
                  <div className="text-micro text-txt-muted">MAX DRAWDOWN</div>
                  <div className="font-mono text-lg">{pct(m.max_drawdown)}</div>
                </div>
                <div>
                  <div className="text-micro text-txt-muted">HIT RATE</div>
                  <div className="font-mono text-lg">{pct(m.hit_rate)}</div>
                </div>
                <div>
                  <div className="text-micro text-txt-muted">GROSS → NET</div>
                  <div className="font-mono text-sm mt-1">
                    {pct(m.gross_return)} → {pct(m.total_return)}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-sm border border-border-base bg-surface-1 p-5">
              <div className="font-mono text-micro uppercase text-txt-muted">Interpretation</div>
              <p className="mt-2 text-sm text-txt-primary">{response.interpretation.summary}</p>
            </section>

            <section className="rounded-sm border border-border-base bg-surface-1">
              <button
                type="button"
                className="w-full px-5 py-3 text-left font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary hover:text-accent"
                onClick={() => setShowWhy((v) => !v)}
              >
                Why / Costs / Spec Diff
              </button>
              {showWhy && (
                <div className="border-t border-border-base px-5 py-3 space-y-3 font-mono text-micro text-txt-secondary">
                  <div>
                    Gross {pct(m.gross_return)} − commission impact {pct(m.commission_impact)} −
                    slippage impact {pct(m.slippage_impact)} = net {pct(m.total_return)}
                  </div>
                  <div>Price hash: {result.reproducibility.price_data_hash}</div>
                  <pre className="overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(response.spec_diff, null, 2)}
                  </pre>
                  <div className="max-h-48 overflow-y-auto">
                    Trades:{' '}
                    {result.trades.map((t, i) => (
                      <div key={i}>
                        #{i + 1} entry {String(t.entry_exec_date)} @ {String(t.entry_market_price)} →
                        exit {String(t.exit_exec_date)} @ {String(t.exit_market_price)}
                        {t.forced_end_close ? ' (forced end)' : ''}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
