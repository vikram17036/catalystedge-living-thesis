import {
  useState,
  FormEvent,
  useMemo,
  forwardRef,
  useImperativeHandle,
  useRef,
} from 'react';
import { AlertCircle, Command, Search } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { cn } from '../utils/cn';

interface TickerInputProps {
  onAnalyze: (ticker: string) => void;
  disabled?: boolean;
}

export interface TickerInputRef {
  focus: () => void;
}

interface CompanyOption {
  symbol: string;
  name: string;
}

const COMPANY_OPTIONS: CompanyOption[] = [
  { symbol: 'AAPL', name: 'Apple Inc.' },
  { symbol: 'MSFT', name: 'Microsoft Corporation' },
  { symbol: 'NVDA', name: 'NVIDIA Corporation' },
  { symbol: 'TSLA', name: 'Tesla, Inc.' },
  { symbol: 'AMZN', name: 'Amazon.com, Inc.' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.' },
  { symbol: 'META', name: 'Meta Platforms, Inc.' },
  { symbol: 'NFLX', name: 'Netflix, Inc.' },
  { symbol: 'AMD', name: 'Advanced Micro Devices, Inc.' },
  { symbol: 'INTC', name: 'Intel Corporation' },
  { symbol: 'JPM', name: 'JPMorgan Chase & Co.' },
  { symbol: 'BAC', name: 'Bank of America Corporation' },
  { symbol: 'WMT', name: 'Walmart Inc.' },
  { symbol: 'COST', name: 'Costco Wholesale Corporation' },
  { symbol: 'DIS', name: 'The Walt Disney Company' },
  { symbol: 'CRM', name: 'Salesforce, Inc.' },
  { symbol: 'ORCL', name: 'Oracle Corporation' },
  { symbol: 'IBM', name: 'International Business Machines Corporation' },
  { symbol: 'UBER', name: 'Uber Technologies, Inc.' },
  { symbol: 'PYPL', name: 'PayPal Holdings, Inc.' },
];

const TICKER_PATTERN = /^[A-Z]{1,5}$/;

const isMac =
  typeof navigator !== 'undefined' &&
  navigator.platform.toUpperCase().includes('MAC');

const TickerInput = forwardRef<TickerInputRef, TickerInputProps>(
  ({ onAnalyze, disabled = false }, ref) => {
    const [query, setQuery] = useState('');
    const [selectedTicker, setSelectedTicker] = useState('');
    const [touched, setTouched] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);

    const normalizedQuery = query.trim().toUpperCase();

    const suggestions = useMemo(() => {
      if (!query.trim()) {
        return [];
      }

      const searchValue = query.trim().toLowerCase();

      return COMPANY_OPTIONS.filter(
        (company) =>
          company.symbol.toLowerCase().includes(searchValue) ||
          company.name.toLowerCase().includes(searchValue)
      ).slice(0, 6);
    }, [query]);

    const directTickerValid = TICKER_PATTERN.test(normalizedQuery);
    const resolvedTicker = selectedTicker || (directTickerValid ? normalizedQuery : '');
    const showSuggestions = isFocused && suggestions.length > 0;

    const showError =
      touched &&
      query.trim().length > 0 &&
      !resolvedTicker &&
      suggestions.length === 0;

    useImperativeHandle(ref, () => ({
      focus: () => inputRef.current?.focus(),
    }));

    const selectCompany = (company: CompanyOption) => {
      setQuery(`${company.name} — ${company.symbol}`);
      setSelectedTicker(company.symbol);
      setTouched(false);
      setHighlightedIndex(0);
      inputRef.current?.focus();
    };

    const handleChange = (value: string) => {
      setQuery(value);
      setSelectedTicker('');
      setTouched(false);
      setHighlightedIndex(0);
    };

    const handleSubmit = (event: FormEvent) => {
      event.preventDefault();

      if (!resolvedTicker) {
        setTouched(true);
        return;
      }

      onAnalyze(resolvedTicker);
      setQuery('');
      setSelectedTicker('');
      setTouched(false);
      setHighlightedIndex(0);
      inputRef.current?.blur();
    };

    const handleKeyDown = (
      event: React.KeyboardEvent<HTMLInputElement>
    ) => {
      if (!showSuggestions) {
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setHighlightedIndex((current) =>
          Math.min(current + 1, suggestions.length - 1)
        );
      }

      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setHighlightedIndex((current) => Math.max(current - 1, 0));
      }

      if (event.key === 'Enter' && suggestions[highlightedIndex]) {
        event.preventDefault();
        selectCompany(suggestions[highlightedIndex]);
      }

      if (event.key === 'Escape') {
        setIsFocused(false);
        inputRef.current?.blur();
      }
    };

    return (
      <div className="w-full">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-txt-muted" />

            <Input
              ref={inputRef}
              placeholder="SEARCH_COMPANY_OR_TICKER"
              value={query}
              onChange={(event) => handleChange(event.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => {
                window.setTimeout(() => {
                  setTouched(true);
                  setIsFocused(false);
                }, 150);
              }}
              disabled={disabled}
              autoComplete="off"
              className={cn(
                'h-12 rounded-sm border border-border-base bg-surface-1 pl-11 pr-16 font-mono text-sm tracking-widest text-txt-primary outline-none transition-colors placeholder:text-txt-muted/50',
                isFocused && 'border-txt-secondary bg-surface-2',
                showError && 'border-bear text-bear'
              )}
              aria-invalid={showError}
              aria-describedby={showError ? 'ticker-error' : undefined}
            />

            <div
              className={cn(
                'absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1 font-mono text-micro tracking-widest text-txt-muted transition-opacity',
                isFocused ? 'opacity-0' : 'opacity-100'
              )}
            >
              {isMac ? (
                <>
                  <Command className="h-3 w-3" />
                  <span>K</span>
                </>
              ) : (
                <span>CTRL+K</span>
              )}
            </div>

            {showSuggestions && (
              <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-sm border border-border-base bg-surface-1 shadow-xl">
                {suggestions.map((company, index) => (
                  <button
                    key={company.symbol}
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectCompany(company)}
                    className={cn(
                      'flex w-full items-center justify-between px-4 py-3 text-left transition-colors',
                      highlightedIndex === index
                        ? 'bg-surface-2 text-accent'
                        : 'text-txt-primary hover:bg-surface-2'
                    )}
                  >
                    <span className="font-mono text-sm font-bold">
                      {company.name}
                    </span>
                    <span className="font-mono text-micro font-bold tracking-widest text-txt-muted">
                      {company.symbol}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <Button
            type="submit"
            disabled={disabled || !resolvedTicker}
            className="h-12 min-w-[160px] rounded-sm border border-transparent bg-accent font-mono text-micro font-bold uppercase tracking-widest text-canvas transition-colors hover:bg-accent/90 disabled:border-border-base disabled:bg-surface-2 disabled:text-txt-muted disabled:opacity-50"
          >
            WHY IS IT MOVING?
          </Button>
        </form>

        {showError && (
          <div
            id="ticker-error"
            className="mt-2 flex items-center gap-2 font-mono text-micro uppercase tracking-widest text-bear"
          >
            <AlertCircle className="h-3 w-3" />
            <span>SELECT A COMPANY OR ENTER A VALID TICKER</span>
          </div>
        )}
      </div>
    );
  }
);

TickerInput.displayName = 'TickerInput';

export default TickerInput;
