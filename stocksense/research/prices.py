"""Load adjusted close series for event studies (I/O layer — not the pure engine)."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Sequence, Tuple

import yfinance as yf

from stocksense.research.event_calendar import CalendarEvent
from stocksense.research.event_study import PriceSeries

logger = logging.getLogger(__name__)

# Process-local TTL cache — cuts repeat yfinance hits within one agent turn / demo.
_PRICE_CACHE: Dict[str, Tuple[float, PriceSeries]] = {}
_PRICE_CACHE_TTL_SEC = 300.0


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def clear_price_cache_for_tests() -> None:
    _PRICE_CACHE.clear()


def fetch_adjusted_closes(
    ticker: str,
    events: Sequence[CalendarEvent],
    *,
    pre_window: int,
    post_window: int,
) -> PriceSeries:
    """Fetch adjusted closes covering event windows with calendar padding."""
    if not events:
        raise ValueError("No events to fetch prices for")

    first = min(e.date for e in events)
    last = max(e.date for e in events)
    # ~1.5 trading days per calendar day pad + window
    pad_pre = max(30, (pre_window + 5) * 2)
    pad_post = max(30, (post_window + 5) * 2)
    start = (_parse_date(first) - timedelta(days=pad_pre)).isoformat()
    end = (_parse_date(last) + timedelta(days=pad_post)).isoformat()
    return fetch_adjusted_closes_range(ticker, start, end)


def fetch_adjusted_closes_range(
    ticker: str,
    start: str,
    end: Optional[str] = None,
) -> PriceSeries:
    """Fetch adjusted closes for [start, end) via yfinance (TTL-cached)."""
    key = f"{ticker.upper()}|{start}|{end or ''}"
    now = time.time()
    hit = _PRICE_CACHE.get(key)
    if hit and (now - hit[0]) < _PRICE_CACHE_TTL_SEC:
        return hit[1]

    hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No price history for {ticker}")

    pairs = []
    for idx, row in hist.iterrows():
        d = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        pairs.append((d, float(row["Close"])))

    series = PriceSeries.from_pairs(pairs, source="yfinance", mode="adjusted_close")
    _PRICE_CACHE[key] = (now, series)
    # Bound cache size for long-lived workers
    if len(_PRICE_CACHE) > 64:
        oldest = sorted(_PRICE_CACHE.items(), key=lambda kv: kv[1][0])[:16]
        for k, _ in oldest:
            _PRICE_CACHE.pop(k, None)
    return series
