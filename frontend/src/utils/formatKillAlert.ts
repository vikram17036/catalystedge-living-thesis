/**
 * Present kill-alert criteria as readable product copy.
 * Raw expressions remain available for WHY / details.
 */

export function formatKillCriterionHuman(
  raw: string,
  ticker?: string
): { headline: string; raw: string } {
  const text = (raw || '').trim();
  const t = (ticker || '').toUpperCase() || 'Ticker';

  // one_day_return=-0.07 lte -0.05
  const m = text.match(
    /one_day_return\s*=\s*(-?[\d.]+)\s+(lte|gte|lt|gt|eq)\s+(-?[\d.]+)/i
  );
  if (m) {
    const observed = Number(m[1]);
    const op = m[2].toLowerCase();
    const threshold = Number(m[3]);
    const obsPct = (observed * 100).toFixed(1);
    const thrPct = (threshold * 100).toFixed(1);
    const fell = observed < 0;
    const verb = fell ? 'fell' : 'rose';
    const crossing =
      op === 'lte' || op === 'lt'
        ? `crossing your −${Math.abs(Number(thrPct))}% kill threshold`
        : op === 'gte' || op === 'gt'
          ? `crossing your +${Math.abs(Number(thrPct))}% kill threshold`
          : `matching your ${thrPct}% kill threshold`;
    return {
      headline: `${t} ${verb} ${Math.abs(Number(obsPct))}% in one day, ${crossing}.`,
      raw: text,
    };
  }

  // Generic metric=value op threshold
  const m2 = text.match(
    /([a-z0-9_]+)\s*=\s*(-?[\d.]+)\s+(lte|gte|lt|gt|eq)\s+(-?[\d.]+)/i
  );
  if (m2) {
    const metric = m2[1].replace(/_/g, ' ');
    const observed = Number(m2[2]);
    const threshold = Number(m2[4]);
    const asPct = (n: number) =>
      Math.abs(n) <= 1 ? `${(n * 100).toFixed(1)}%` : String(n);
    return {
      headline: `${t}: ${metric} reached ${asPct(observed)} vs threshold ${asPct(threshold)}.`,
      raw: text,
    };
  }

  return { headline: text, raw: text };
}

export function formatTriggeringSignalHuman(raw: string): string {
  const text = (raw || '').trim();
  if (!text) return 'Kill criterion evaluated as triggered.';
  // Soften common engine strings
  return text
    .replace(/one_day_return/gi, 'one-day return')
    .replace(/_/g, ' ');
}
