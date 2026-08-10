import { Button } from './ui/button';
import { cn } from '../utils/cn';

interface QuickSelectProps {
  onSelect: (ticker: string) => void;
  disabled?: boolean;
  activeTicker?: string | null;
}

const popularTickers = [
  { symbol: 'AAPL', name: 'Apple' },
  { symbol: 'MSFT', name: 'Microsoft' },
  { symbol: 'NVDA', name: 'NVIDIA' },
  { symbol: 'TSLA', name: 'Tesla' },
  { symbol: 'GOOGL', name: 'Google' },
];

const QuickSelect = ({
  onSelect,
  disabled = false,
  activeTicker = null,
}: QuickSelectProps) => {
  const active = (activeTicker || '').toUpperCase();

  return (
    <div className="flex min-h-12 w-full flex-wrap items-center gap-x-2 gap-y-1.5 rounded-md border border-border-base bg-surface-1 px-3 py-2">
      <span className="ui-label shrink-0">Quick</span>
      <div className="flex flex-wrap items-center gap-1">
        {popularTickers.map(({ symbol, name }) => {
          const isActive = active === symbol;
          return (
            <Button
              key={symbol}
              variant="ghost"
              size="sm"
              title={name}
              onClick={() => onSelect(symbol)}
              disabled={disabled}
              aria-pressed={isActive}
              className={cn(
                'h-8 shrink-0 rounded-md border px-2.5 font-mono text-micro uppercase tracking-wider transition-colors',
                isActive
                  ? 'border-accent/50 bg-accent/10 text-accent'
                  : 'border-transparent text-txt-tertiary hover:border-border-strong hover:bg-surface-2 hover:text-txt-primary',
                disabled && 'opacity-40'
              )}
            >
              {symbol}
            </Button>
          );
        })}
      </div>
    </div>
  );
};

export default QuickSelect;
