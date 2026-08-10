import { useEffect, useState } from 'react';
import { Loader2, Network } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  createDependency,
  deleteDependency,
  fetchThesisGraph,
  type GraphEdge,
  type GraphNode,
} from '../api/thesisGraph';

export default function ThesisGraphPage() {
  const { user } = useAuth();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [fromId, setFromId] = useState('');
  const [toId, setToId] = useState('');
  const [linkType, setLinkType] = useState('depends_on');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchThesisGraph();
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
      if (!fromId && data.nodes?.[0]) setFromId(data.nodes[0].id);
      if (!toId && data.nodes?.[1]) setToId(data.nodes[1].id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function onCreate() {
    setError(null);
    try {
      await createDependency({
        from_thesis_id: fromId,
        to_thesis_id: toId,
        link_type: linkType,
      });
      await refresh();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response
          ?.data?.detail ||
        (e as { message?: string })?.message ||
        'Create failed';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  }

  const label = (id: string) => {
    const n = nodes.find((x) => x.id === id);
    return n ? `${n.ticker}` : id.slice(0, 8);
  };

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-5xl">
      <p className="font-mono text-micro font-bold uppercase tracking-widest text-accent">
        GRAPH
      </p>
      <h1 className="mt-2 font-mono text-2xl font-bold tracking-tight text-txt-primary">
        Thesis Dependency Graph
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
        Supporting map of how theses relate. Scenario Lab remains the Phase 6 hero — this
        does not propagate what-ifs across edges.
      </p>

      {!user && (
        <p className="mt-4 font-mono text-micro text-txt-muted">Sign in required.</p>
      )}

      {error && (
        <div className="mt-4 rounded-sm border border-kill/40 bg-kill/10 px-3 py-2 font-mono text-sm text-kill">
          {error}
        </div>
      )}

      <section className="mt-6 rounded-sm border border-border-base bg-surface-1 p-5 space-y-3">
        <div className="flex items-center gap-2 font-mono text-micro uppercase tracking-widest text-txt-muted">
          <Network className="h-4 w-4" />
          Create edge
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={fromId}
            onChange={(e) => setFromId(e.target.value)}
            className="rounded-sm border border-border-base bg-surface-2 px-2 py-1.5 font-mono text-sm"
          >
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.ticker} · {n.thesis_summary.slice(0, 40)}
              </option>
            ))}
          </select>
          <select
            value={linkType}
            onChange={(e) => setLinkType(e.target.value)}
            className="rounded-sm border border-border-base bg-surface-2 px-2 py-1.5 font-mono text-sm"
          >
            <option value="depends_on">depends_on</option>
            <option value="related_ticker">related_ticker</option>
            <option value="shared_kill_metric">shared_kill_metric</option>
          </select>
          <select
            value={toId}
            onChange={(e) => setToId(e.target.value)}
            className="rounded-sm border border-border-base bg-surface-2 px-2 py-1.5 font-mono text-sm"
          >
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.ticker} · {n.thesis_summary.slice(0, 40)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void onCreate()}
            disabled={!fromId || !toId || loading}
            className="rounded-sm border border-accent bg-accent/10 px-3 py-1.5 font-mono text-micro font-bold uppercase tracking-widest text-accent disabled:opacity-40"
          >
            Link
          </button>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-sm border border-border-base px-3 py-1.5 font-mono text-micro uppercase tracking-widest text-txt-secondary"
          >
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Refresh'}
          </button>
        </div>
      </section>

      <section className="mt-6 rounded-sm border border-border-base bg-surface-1 p-5">
        <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
          Nodes ({nodes.length})
        </h3>
        <ul className="mt-2 space-y-1">
          {nodes.map((n) => (
            <li key={n.id} className="font-mono text-sm text-txt-secondary">
              <span className="text-accent">{n.ticker}</span> · {n.thesis_summary}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-4 rounded-sm border border-border-base bg-surface-1 p-5">
        <h3 className="font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
          Edges ({edges.length})
        </h3>
        <ul className="mt-2 space-y-2">
          {edges.map((e) => (
            <li
              key={e.id}
              className="flex flex-wrap items-center justify-between gap-2 font-mono text-sm text-txt-secondary"
            >
              <span>
                {label(e.from_thesis_id)} —{e.link_type}→ {label(e.to_thesis_id)}
              </span>
              <button
                type="button"
                onClick={() => void deleteDependency(e.id).then(refresh)}
                className="text-micro text-kill uppercase"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
