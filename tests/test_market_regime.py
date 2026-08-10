"""Unit tests for market_regime pure engine."""

from __future__ import annotations

from datetime import date, timedelta

from stocksense.research.event_study import PriceSeries
from stocksense.research.market_regime import compute_market_regime


def _rising_series(n: int = 260, start: float = 100.0) -> PriceSeries:
    base = date(2020, 1, 1)
    pairs = []
    px = start
    for i in range(n):
        px *= 1.002
        pairs.append(((base + timedelta(days=i)).isoformat(), px))
    return PriceSeries.from_pairs(pairs)


def test_compute_market_regime_uptrend():
    prices = _rising_series()
    r = compute_market_regime("NVDA", prices)
    assert r["ticker"] == "NVDA"
    assert r["last_close"] is not None
    assert r["sma20"] is not None
    assert r["sma50"] is not None
    assert r["sma200"] is not None
    assert r["vs_sma20"] == "above"
    assert r["vs_sma50"] == "above"
    assert r["sma20_vs_sma50"] == "bullish"
    assert r["engine_version"] == "market_regime_v1"
    assert r["bars"] == 260
