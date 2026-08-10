"""I/O wrapper for market regime — fetch prices, run pure engine."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from stocksense.research.market_regime import (
    ENGINE_VERSION,
    compute_market_regime,
    format_regime_interpretation,
)
from stocksense.research.prices import fetch_adjusted_closes_range


def run_market_regime_request(
    ticker: str,
    *,
    lookback_calendar_days: int = 420,
) -> Dict[str, Any]:
    """
    Deterministic current-regime snapshot for agent / labs.
    Uses cached yfinance range when available.
    """
    t = (ticker or "").strip().upper()
    if not t:
        raise ValueError("ticker required")

    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=lookback_calendar_days)
    prices = fetch_adjusted_closes_range(
        t, start.isoformat(), end.isoformat()
    )
    regime = compute_market_regime(t, prices)
    summary = format_regime_interpretation(regime)
    evidence = {
        "id": f"ev_regime_{t}_{regime['as_of']}".replace("-", ""),
        "type": "market_regime",
        "entity": t,
        "metric": "market_regime_summary",
        "value": regime.get("last_close"),
        "source": "catalystedge:market-regime",
        "data": regime,
        "provenance": {
            "engine_version": ENGINE_VERSION,
            "price_data_hash": regime.get("price_data_hash"),
            "price_source": regime.get("price_source"),
            "price_mode": regime.get("price_mode"),
        },
        "observed_at": f"{regime['as_of']}T00:00:00Z",
        "available_at": f"{regime['as_of']}T00:00:00Z",
        "hypothetical": False,
    }
    return {
        "spec": {
            "ticker": t,
            "kind": "market_regime",
            "engine_version": ENGINE_VERSION,
        },
        "result": regime,
        "interpretation": {"summary": summary},
        "evidence_ledger": [evidence],
    }
