"""Deterministic market-regime snapshot from adjusted closes.

Pure: ticker metadata + PriceSeries → regime dict.
No UUID, datetime.now(), LLM, network, or exec().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from stocksense.research.event_study import PriceSeries

ENGINE_VERSION = "market_regime_v1"


def _sma(closes: Tuple[float, ...], window: int, i: int) -> Optional[float]:
    if i + 1 < window:
        return None
    chunk = closes[i - window + 1 : i + 1]
    return sum(chunk) / window


def _ret(closes: Tuple[float, ...], i: int, lookback: int) -> Optional[float]:
    j = i - lookback
    if j < 0 or closes[j] == 0:
        return None
    return (closes[i] / closes[j]) - 1.0


def _last_crossover(
    closes: Tuple[float, ...],
    dates: Tuple[str, ...],
    fast: int,
    slow: int,
) -> Optional[Dict[str, Any]]:
    """Most recent fast/slow SMA cross at or before last bar."""
    n = len(closes)
    if n < slow + 1:
        return None
    last_i = n - 1
    for i in range(last_i, slow - 1, -1):
        f = _sma(closes, fast, i)
        s = _sma(closes, slow, i)
        f_prev = _sma(closes, fast, i - 1)
        s_prev = _sma(closes, slow, i - 1)
        if None in (f, s, f_prev, s_prev):
            continue
        if f_prev <= s_prev and f > s:
            return {"date": dates[i], "direction": "bullish_cross", "fast": fast, "slow": slow}
        if f_prev >= s_prev and f < s:
            return {"date": dates[i], "direction": "bearish_cross", "fast": fast, "slow": slow}
    return None


def compute_market_regime(
    ticker: str,
    prices: PriceSeries,
    *,
    windows: Tuple[int, ...] = (20, 50, 200),
) -> Dict[str, Any]:
    """Return current technical regime facts (measured, not interpreted)."""
    if not prices.dates or not prices.closes:
        raise ValueError(f"No prices for {ticker}")

    closes = prices.closes
    dates = prices.dates
    i = len(closes) - 1
    last = float(closes[i])
    as_of = dates[i]

    smas: Dict[str, Optional[float]] = {}
    for w in windows:
        smas[f"sma{w}"] = _sma(closes, w, i)

    vs: Dict[str, Optional[str]] = {}
    for w in windows:
        key = f"sma{w}"
        v = smas[key]
        if v is None or v == 0:
            vs[f"vs_{key}"] = None
        else:
            vs[f"vs_{key}"] = "above" if last > v else "below"

    sma20, sma50 = smas.get("sma20"), smas.get("sma50")
    relationship_20_50: Optional[str] = None
    if sma20 is not None and sma50 is not None:
        relationship_20_50 = "bullish" if sma20 > sma50 else "bearish"

    return {
        "engine_version": ENGINE_VERSION,
        "ticker": ticker.upper(),
        "as_of": as_of,
        "last_close": last,
        "sma20": smas.get("sma20"),
        "sma50": smas.get("sma50"),
        "sma200": smas.get("sma200"),
        "vs_sma20": vs.get("vs_sma20"),
        "vs_sma50": vs.get("vs_sma50"),
        "vs_sma200": vs.get("vs_sma200"),
        "sma20_vs_sma50": relationship_20_50,
        "momentum_5d": _ret(closes, i, 5),
        "momentum_20d": _ret(closes, i, 20),
        "last_20_50_cross": _last_crossover(closes, dates, 20, 50),
        "price_data_hash": prices.fingerprint(),
        "price_source": prices.source,
        "price_mode": prices.mode,
        "bars": len(closes),
    }


def format_regime_interpretation(regime: Dict[str, Any]) -> str:
    """Short deterministic sentence for receipts (not LLM)."""
    parts: List[str] = [
        f"{regime.get('ticker')} as of {regime.get('as_of')}: "
        f"last={regime.get('last_close')}"
    ]
    for w in (20, 50, 200):
        sma = regime.get(f"sma{w}")
        vs = regime.get(f"vs_sma{w}")
        if sma is not None:
            parts.append(f"SMA{w}={sma:.4f} ({vs})")
    rel = regime.get("sma20_vs_sma50")
    if rel:
        parts.append(f"20/50 {rel}")
    return "; ".join(parts)
