/**
 * Present attached Evidence objects as human-readable research cards.
 * Underlying schema is unchanged — this is display only.
 */

export type AttachedEvidenceLike = {
  id?: string;
  type?: string;
  entity?: string;
  metric?: string;
  value?: unknown;
  data?: Record<string, unknown>;
  hypothetical?: boolean;
  [key: string]: unknown;
};

export type EvidenceCard = {
  id: string;
  kindLabel: string;
  title: string;
  detail: string;
  hypothetical?: boolean;
};

function pct(n: unknown, digits = 1): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${(n * 100).toFixed(digits)}%`;
}

function num(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 1 });
}

function asData(e: AttachedEvidenceLike): Record<string, unknown> {
  return (e.data && typeof e.data === 'object' ? e.data : {}) as Record<
    string,
    unknown
  >;
}

export function formatAttachedEvidenceCard(
  e: AttachedEvidenceLike,
  index: number
): EvidenceCard {
  const type = String(e.type || '').toLowerCase();
  const data = asData(e);
  const ticker = String(e.entity || data.ticker || '').toUpperCase() || 'Ticker';
  const id = String(e.id || `${type}-${index}`);

  if (type === 'event_study') {
    const filter = String(data.event_filter || 'events');
    const analyzed = data.events_analyzed ?? e.value;
    const calRaw = String(data.calendar_id || '').replace(/_/g, ' ');
    const cal = /fomc/i.test(calRaw)
      ? 'FOMC decisions'
      : calRaw || filter.replace(/_/g, ' ');
    return {
      id,
      kindLabel: 'Event study',
      title: `${ticker} around ${cal}`,
      detail: `${num(analyzed)} events analyzed`,
    };
  }

  if (type === 'analog_search') {
    const lookback = data.lookback ?? '—';
    const post = data.post_window ?? '—';
    const fwd = data.forward_mean ?? e.value;
    return {
      id,
      kindLabel: 'Historical analogs',
      title: `${lookback}-day pattern · next ${post} days`,
      detail: `Mean forward return ${pct(fwd)}`,
    };
  }

  if (type === 'backtest') {
    const metrics =
      data.metrics && typeof data.metrics === 'object'
        ? (data.metrics as Record<string, unknown>)
        : {};
    const fast = data.fast_window;
    const slow = data.slow_window;
    const kind = String(data.kind || '').replace(/_/g, ' ');
    const strategy =
      fast != null && slow != null
        ? `${fast}/${slow} SMA crossover`
        : String(data.strategy || data.strategy_id || kind || 'Strategy').replace(
            /_/g,
            ' '
          );
    const net =
      metrics.total_return ??
      data.net_return ??
      data.total_return ??
      (typeof e.value === 'number' ? e.value : undefined);
    // Engine stores total_return as a fraction (e.g. 7.087 → +708.7%)
    const label =
      typeof net === 'number'
        ? `${net > 0 ? '+' : ''}${(net * 100).toFixed(1)}%`
        : '—';
    return {
      id,
      kindLabel: 'Strategy lab',
      title: strategy,
      detail: `Net return ${label}`,
    };
  }

  if (type === 'scenario') {
    const shock = Number(data.shock_value ?? e.value);
    const triggered = Number(data.criteria_triggered ?? 0);
    const pctMove =
      Number.isFinite(shock) && Math.abs(shock) <= 1
        ? Math.abs(shock * 100).toFixed(0)
        : String(Math.abs(shock));
    const direction = shock < 0 ? 'falls' : 'rises';
    return {
      id,
      kindLabel: 'What-if',
      title: `${ticker} ${direction} ${pctMove}% in one day`,
      detail:
        triggered > 0
          ? `Hypothetical · ${triggered} kill ${triggered === 1 ? 'criterion' : 'criteria'} triggered`
          : 'Hypothetical · no kill criteria triggered',
      hypothetical: true,
    };
  }

  // Fallback — still readable
  return {
    id,
    kindLabel: type.replace(/_/g, ' ') || 'Research',
    title: String(e.metric || type || 'Attached evidence').replace(/_/g, ' '),
    detail: e.value != null ? String(e.value) : 'Attached to thesis',
  };
}

export function summarizeThesisCopy(input: {
  summary: string;
  conviction?: string | null;
  snapshot?: {
    sentiment?: string;
    confidence?: number;
    key_themes?: string[];
  } | null;
}): { headline: string; body: string } {
  const conviction = (input.conviction || 'medium').toLowerCase();
  const snap = input.snapshot;
  const sentiment = (snap?.sentiment || '').trim();
  const conf =
    typeof snap?.confidence === 'number'
      ? Math.round(
          snap.confidence <= 1 ? snap.confidence * 100 : snap.confidence
        )
      : null;

  const headlineParts: string[] = [];
  if (sentiment) {
    const pretty =
      sentiment.charAt(0).toUpperCase() + sentiment.slice(1).toLowerCase();
    headlineParts.push(pretty);
  } else {
    headlineParts.push(conviction.charAt(0).toUpperCase() + conviction.slice(1));
  }
  if (conf != null) headlineParts.push(`${conf}% confidence`);

  let body = (input.summary || '').trim();
  // Strip common terminal prefixes
  body = body.replace(/^STOCK ANALYSIS SUMMARY FOR [A-Z]+:\s*/i, '');
  body = body.replace(/^>\s*/, '');
  if (body.length > 320) body = `${body.slice(0, 317)}…`;

  const themes = (snap?.key_themes || []).filter(Boolean).slice(0, 3);
  if (themes.length && body.length < 80) {
    body = `${themes.join(', ')} remain central to the thesis. ${body}`.trim();
  }

  return {
    headline: headlineParts.join(' · '),
    body: body || 'Thesis frozen from the origin analysis snapshot.',
  };
}
