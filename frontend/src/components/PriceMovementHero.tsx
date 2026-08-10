import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import type { AnalysisData } from '../types/api';
import { cn } from '../utils/cn';

interface PriceMovementHeroProps {
  result: AnalysisData;
}

const COMPANY_NAMES: Record<string, string> = {
  AAPL: 'Apple Inc.',
  MSFT: 'Microsoft Corporation',
  NVDA: 'NVIDIA Corporation',
  TSLA: 'Tesla, Inc.',
  AMZN: 'Amazon.com, Inc.',
  GOOGL: 'Alphabet Inc.',
  META: 'Meta Platforms, Inc.',
  NFLX: 'Netflix, Inc.',
  AMD: 'Advanced Micro Devices, Inc.',
  INTC: 'Intel Corporation',
  JPM: 'JPMorgan Chase & Co.',
  BAC: 'Bank of America Corporation',
  WMT: 'Walmart Inc.',
  COST: 'Costco Wholesale Corporation',
  DIS: 'The Walt Disney Company',
  CRM: 'Salesforce, Inc.',
  ORCL: 'Oracle Corporation',
  IBM: 'International Business Machines Corporation',
  UBER: 'Uber Technologies, Inc.',
  PYPL: 'PayPal Holdings, Inc.',
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

export default function PriceMovementHero({
  result,
}: PriceMovementHeroProps) {
  const validPrices = (result.price_data ?? []).filter(
    (point) => typeof point.Close === 'number'
  );

  const latest = validPrices[validPrices.length - 1];
  const previous = validPrices[validPrices.length - 2];

  if (
    !latest ||
    !previous ||
    typeof latest.Close !== 'number' ||
    typeof previous.Close !== 'number'
  ) {
    return null;
  }

  const change = latest.Close - previous.Close;
  const percentChange =
    previous.Close !== 0 ? (change / previous.Close) * 100 : 0;

  const isPositive = change > 0;
  const isNegative = change < 0;
  const MovementIcon = isPositive
    ? ArrowUpRight
    : isNegative
      ? ArrowDownRight
      : Minus;

  const companyName = COMPANY_NAMES[result.ticker] ?? result.ticker;

  return (
    <section className="overflow-hidden rounded-sm border border-border-base bg-surface-1">
      <div className="grid gap-0 lg:grid-cols-[1.35fr_1fr]">
        <div className="border-b border-border-base p-5 lg:border-b-0 lg:border-r">
          <p className="ui-label text-accent">Price movement</p>

          <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-2">
            <div className="min-w-0 max-w-full flex-1">
              <h2 className="truncate font-mono text-xl font-bold leading-tight text-txt-primary sm:text-2xl">
                {companyName}
              </h2>
              <p className="mt-1 font-mono text-sm uppercase tracking-widest text-txt-muted">
                {result.ticker} · Latest available session
              </p>
            </div>

            <div className="ml-auto text-right">
              <p className="font-mono text-3xl font-bold text-txt-primary">
                {formatCurrency(latest.Close)}
              </p>

              <div
                className={cn(
                  'mt-1 flex items-center justify-end gap-1 font-mono text-sm font-bold',
                  isPositive && 'text-bull',
                  isNegative && 'text-bear',
                  !isPositive && !isNegative && 'text-txt-muted'
                )}
              >
                <MovementIcon className="h-4 w-4" />
                <span>
                  {change >= 0 ? '+' : ''}
                  {change.toFixed(2)} ({percentChange >= 0 ? '+' : ''}
                  {percentChange.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-px bg-border-base">
          <div className="bg-canvas p-4">
            <p className="ui-label">Previous close</p>
            <p className="mt-2 font-mono text-lg font-bold text-txt-primary">
              {formatCurrency(previous.Close)}
            </p>
          </div>

          <div className="bg-canvas p-4">
            <p className="ui-label">Session date</p>
            <p className="mt-2 font-mono text-sm font-bold text-txt-primary">
              {new Date(latest.Date).toLocaleDateString()}
            </p>
          </div>

          <div className="col-span-2 bg-canvas p-4">
            <p className="ui-label">Signal context</p>
            <p className="mt-2 font-mono text-sm font-bold text-txt-primary">
              {result.overall_sentiment || 'Analysis pending'} ·{' '}
              {Math.round((result.overall_confidence ?? 0) * 100)}% confidence
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
