"""Load adjusted close series for event studies (I/O layer — not the pure engine)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Sequence

import yfinance as yf

from stocksense.research.event_calendar import CalendarEvent
from stocksense.research.event_study import PriceSeries


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


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

    hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No price history for {ticker}")

    pairs = []
    for idx, row in hist.iterrows():
        d = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        pairs.append((d, float(row["Close"])))

    return PriceSeries.from_pairs(pairs, source="yfinance", mode="adjusted_close")
