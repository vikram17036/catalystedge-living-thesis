import { useEffect, useMemo, useState } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  reindexResearchMemory,
  runResearchAgent,
  type ResearchAgentResponse,
} from '../api/researchAgent';
import { cn } from '../utils/cn';

const HERO =
  "I'm reconsidering NVDA. Look at my previous research, find similar historical periods, stress test another 8% drop, and tell me whether my thesis still makes sense.";

const FOLLOW = 'Make that a 12% drop.';

const TOOL_LABELS: Record<string, string> = {
  get_market_regime: 'Reading market regime (SMAs)',
  find_analogs: 'Finding historical analogs',
  run_scenario: 'Stress-testing scenario',
  run_event_study: 'Running event study',
  run_backtest: 'Running strategy lab',
  get_thesis: 'Loading thesis',
  retrieve_research_memory: 'Retrieved prior research',
  attach_evidence: 'Attaching evidence',
};

function label(tool: string) {
  return TOOL_LABELS[tool] || tool.replace(/_/g, ' ');
}

function shockPct(v: number | null | undefined) {
  if (v == null || Number.isNaN(Number(v))) return '—';
  return `${(Number(v) * 100).toFixed(0)}% one-day return`;
}

type ProgressStep = {
  id: string;
  text: string;
  state: 'done' | 'active' | 'pending';
};

function buildLoadingSteps(elapsedMs: number): ProgressStep[] {
  const stages = [
    { id: 'plan', text: 'Building research plan…', at: 0 },
    { id: 'memory', text: 'Retrieving prior research', at: 1200 },
    { id: 'research', text: 'Running selected research tools', at: 2800 },
    { id: 'cite', text: 'Validating citations', at: 5200 },
  ];
  return stages.map((s, i) => {
    const nextAt = stages[i + 1]?.at ?? Number.POSITIVE_INFINITY;
    let state: ProgressStep['state'] = 'pending';
    if (elapsedMs >= nextAt) state = 'done';
    else if (elapsedMs >= s.at) state = 'active';
    return { id: s.id, text: s.text, state };
  });
}

export default function AgentPage() {
  const { user } = useAuth();
  const [message, setMessage] = useState(HERO);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reindexMsg, setReindexMsg] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [last, setLast] = useState<ResearchAgentResponse | null>(null);
  const [history, setHistory] = useState<
    { role: 'user' | 'assistant'; content: string }[]
  >([]);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!loading) {
      setElapsedMs(0);
      return;
    }
    const started = Date.now();
    const id = window.setInterval(() => setElapsedMs(Date.now() - started), 400);
    return () => window.clearInterval(id);
  }, [loading]);

  const loadingSteps = useMemo(() => buildLoadingSteps(elapsedMs), [elapsedMs]);

  async function submit(q: string) {
    if (!user) {
      setError('Sign in required.');
      return;
    }
    setLoading(true);
    setError(null);
    setHistory((h) => [...h, { role: 'user', content: q }]);
    try {
      const data = await runResearchAgent(q, {
        thread_id: threadId,
        ticker: last?.ticker,
        thesis_id: last?.thesis_id,
      });
      setLast(data);
      setThreadId(data.thread_id);
      setHistory((h) => [...h, { role: 'assistant', content: data.answer }]);
      setMessage('');
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Agent failed';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }

  async function onReindex() {
    if (!user) {
      setError('Sign in required.');
      return;
    }
    setReindexing(true);
    setReindexMsg(null);
    try {
      const res = await reindexResearchMemory(last?.ticker || undefined);
      const sources = res.sources_indexed ?? 0;
      const chunks = res.chunks_indexed ?? res.indexed_vectors ?? 0;
      if (res.errors?.length) {
        setReindexMsg(
          `Indexed ${sources} sources / ${chunks} chunks — errors: ${res.errors.join('; ')}`
        );
      } else {
        setReindexMsg(`${sources} sources / ${chunks} chunks indexed`);
      }
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Reindex failed';
      setReindexMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setReindexing(false);
    }
  }

  const tr = last?.trace;
  const research = tr?.research_tools_selected || last?.research_plan?.research_tools_selected || [];
  const notReq = tr?.not_selected || last?.research_plan?.not_selected || [];
  const mem = tr?.memory;
  const citesOk = tr?.citations_validated ?? last?.citations?.length ?? 0;
  const citesTotal = tr?.citations_total ?? last?.citations?.length ?? 0;

  return (
    <div className="max-w-5xl p-4 md:p-6 lg:p-8">
      <p className="ui-label">Agent</p>
      <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-txt-primary">
        Research Agent
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-txt-secondary">
        Orchestrates deterministic labs with memory retrieval. Conversation state is
        process-local; durable research stays in Supabase and Pinecone.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setMessage(HERO);
            void submit(HERO);
          }}
          className="rounded-md border border-border-base px-2.5 py-1.5 text-micro text-txt-secondary transition-colors hover:border-accent hover:text-accent"
        >
          Hero NVDA
        </button>
        <button
          type="button"
          disabled={!threadId || loading}
          onClick={() => {
            setMessage(FOLLOW);
            void submit(FOLLOW);
          }}
          className="rounded-md border border-border-base px-2.5 py-1.5 text-micro text-txt-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
        >
          Follow-up −12%
        </button>
        <button
          type="button"
          onClick={() => {
            setThreadId(null);
            setLast(null);
            setHistory([]);
            setReindexMsg(null);
          }}
          className="rounded-md border border-border-base px-2.5 py-1.5 text-micro text-txt-muted transition-colors hover:text-txt-primary"
        >
          New thread
        </button>
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="rounded-md border border-transparent px-2.5 py-1.5 text-micro text-txt-muted hover:text-txt-secondary"
        >
          {showAdvanced ? 'Hide advanced' : 'Advanced'}
        </button>
      </div>

      {showAdvanced ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={reindexing}
            onClick={() => void onReindex()}
            className="rounded-md border border-border-base px-2.5 py-1.5 text-micro text-txt-muted hover:border-border-strong hover:text-txt-secondary disabled:opacity-40"
          >
            {reindexing ? 'Reindexing…' : 'Reindex memory'}
          </button>
          {reindexMsg ? (
            <p className="font-mono text-micro text-txt-secondary">{reindexMsg}</p>
          ) : null}
        </div>
      ) : null}

      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim() && !loading) void submit(message.trim());
        }}
      >
        <label className="ui-label">Ask the research agent</label>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="Reconsider a thesis, find analogs, stress a drop…"
          className="w-full resize-y rounded-md border border-border-base bg-surface-1 px-3 py-2.5 font-mono text-sm leading-relaxed text-txt-primary outline-none focus:border-accent"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !message.trim()}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 font-mono text-micro font-semibold tracking-wide text-canvas disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
            Run
          </button>
        </div>
      </form>

      {error ? <p className="mt-4 text-sm text-kill">{error}</p> : null}

      <div className="mt-6 space-y-3">
        {history.map((m, i) => (
          <div
            key={`${m.role}-${i}`}
            className={cn(
              'rounded-md border border-border-base/60 p-3',
              m.role === 'user' ? 'bg-surface-1' : 'bg-surface-2/50'
            )}
          >
            <p className="ui-label">{m.role === 'user' ? 'You' : 'Agent'}</p>
            <div className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-txt-primary">
              {m.content}
            </div>
          </div>
        ))}

        {loading ? (
          <div className="rounded-md border border-accent/35 bg-accent/5 p-4">
            <p className="ui-label text-accent">Running</p>
            <ul className="mt-3 space-y-2">
              {loadingSteps.map((s) => (
                <li
                  key={s.id}
                  className={cn(
                    'flex items-center gap-2 text-sm',
                    s.state === 'done' && 'text-txt-secondary',
                    s.state === 'active' && 'font-medium text-accent',
                    s.state === 'pending' && 'text-txt-muted'
                  )}
                >
                  <span className="w-4 text-center font-mono text-micro">
                    {s.state === 'done' ? '✓' : s.state === 'active' ? '→' : '○'}
                  </span>
                  {s.text}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {last && tr && !loading ? (
        <div className="ui-panel mt-6 p-4 text-sm text-txt-secondary">
          <p className="ui-label">Execution receipt</p>
          <div className="mt-3 space-y-3">
            <div>
              <p className="ui-label">Intent</p>
              <p className="mt-0.5 text-txt-primary">{tr.intent || '—'}</p>
            </div>
            <div>
              <p className="ui-label">Research selected</p>
              <ul className="mt-1 space-y-0.5 text-txt-secondary">
                {research.length === 0 ? (
                  <li className="text-txt-muted">None</li>
                ) : (
                  research.map((t) => (
                    <li key={t} className="text-txt-primary">
                      · {label(t)}
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <p className="ui-label">Not required</p>
              <ul className="mt-1 space-y-0.5 text-txt-muted">
                {notReq.map((t) => (
                  <li key={t}>· {label(t)}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="ui-label">Memory</p>
              <p className="mt-0.5">
                {mem?.available === false
                  ? `Unavailable · ${mem.error || 'n/a'}`
                  : `${mem?.records ?? 0} prior records`}
              </p>
            </div>
            <div>
              <p className="ui-label">Scenario</p>
              <p className="mt-0.5 text-txt-primary">{shockPct(tr.scenario_shock)}</p>
            </div>
            <div>
              <p className="ui-label">Evidence</p>
              <p className="mt-0.5">
                {citesOk} / {citesTotal} citations validated
              </p>
            </div>
            <div>
              <p className="ui-label">Reproducibility</p>
              <ul className="mt-1 space-y-0.5 font-mono text-micro text-txt-muted">
                {(tr.engine_repro || []).length === 0 ? (
                  <li>—</li>
                ) : (
                  (tr.engine_repro || []).map((e, i) => (
                    <li key={`${e.tool}-${i}`}>
                      {e.engine_version || e.tool}
                      {e.price_data_hash
                        ? ` · price ${String(e.price_data_hash).slice(0, 8)}`
                        : ''}
                      {e.criteria_hash
                        ? ` · criteria ${String(e.criteria_hash).slice(0, 8)}`
                        : ''}
                    </li>
                  ))
                )}
              </ul>
            </div>
            {(tr.tool_errors || []).length > 0 ? (
              <div>
                <p className="ui-label text-kill">Tool errors</p>
                <ul className="mt-1 space-y-0.5 font-mono text-micro text-kill">
                  {(tr.tool_errors || []).map((e, i) => (
                    <li key={`${e.tool}-${i}`}>
                      {e.tool}: {e.error_code} — {e.message}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-6 border-t border-border-subtle pt-3">
              <div>
                <p className="ui-label">Writes</p>
                <p className="mt-0.5 text-txt-primary">
                  {(tr.writes ?? last.writes ?? 0) === 0
                    ? 'None'
                    : String(tr.writes ?? last.writes)}
                </p>
              </div>
              <div>
                <p className="ui-label">Total</p>
                <p className="mt-0.5 text-txt-primary">{tr.latency_ms_total ?? '—'} ms</p>
              </div>
            </div>
            <p className="font-mono text-micro text-txt-muted">
              {tr.trace_version} · {last.thread_id}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
