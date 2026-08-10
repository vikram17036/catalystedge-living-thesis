"""Rule-first NL → StrategySpec. Hero turns without Gemini."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from stocksense.core.contracts import SmaCrossoverParams, StrategyKind, StrategySpec

_KNOWN = {"NVDA", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AMD", "SPY", "QQQ"}


class StrategyParseError(ValueError):
    pass


def _ticker(text: str, prior: Optional[StrategySpec]) -> Optional[str]:
    upper = text.upper()
    for t in sorted(_KNOWN, key=len, reverse=True):
        if re.search(rf"\b{t}\b", upper):
            return t
    m = re.search(r"\bon\s+([A-Za-z]{1,5})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    if prior:
        return prior.ticker
    return None


def _windows(text: str) -> Optional[Tuple[int, int]]:
    m = re.search(r"\b(\d+)\s*/\s*(\d+)\s*SMA\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(
        r"\b(\d+)\s*/\s*(\d+)\s*(?:day\s+)?(?:SMA\s+)?crossover\b",
        text,
        re.IGNORECASE,
    )
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(\d+)\s*[/-]\s*(\d+)\b", text)
    if m and ("sma" in text.lower() or "crossover" in text.lower()):
        return int(m.group(1)), int(m.group(2))
    return None


def _start_year(text: str) -> Optional[str]:
    m = re.search(r"\bsince\s+(20\d{2})\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-01-01"
    return None


def _costs(text: str) -> Optional[Tuple[float, float]]:
    """Return (commission_bps, slippage_bps) if cost language present."""
    t = text.lower()
    if "commission" not in t and "slippage" not in t and "bps" not in t:
        return None
    comm = None
    slip = None
    m_c = re.search(r"(\d+(?:\.\d+)?)\s*bps\s+commission", t)
    m_s = re.search(r"(\d+(?:\.\d+)?)\s*bps\s+slippage", t)
    if m_c:
        comm = float(m_c.group(1))
    if m_s:
        slip = float(m_s.group(1))
    # "Add 5 bps commission and 2 bps slippage"
    if comm is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*bps[^\d]{0,40}commission", t)
        if m:
            comm = float(m.group(1))
    if slip is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*bps[^\d]{0,40}slippage", t)
        if m:
            slip = float(m.group(1))
    if comm is None and slip is None:
        return None
    return (comm if comm is not None else 0.0, slip if slip is not None else 0.0)


def _is_view_only(text: str) -> bool:
    t = text.lower()
    return bool(
        re.search(r"\bshow\b", t)
        and (
            "drawdown" in t
            or "hit rate" in t
            or "max drawdown" in t
            or "metrics" in t
        )
    )


def spec_diff(prior: Optional[StrategySpec], new: StrategySpec) -> Dict[str, Any]:
    if prior is None:
        return {"created": new.model_dump()}
    a, b = prior.model_dump(), new.model_dump()
    changes: Dict[str, Any] = {}
    for k in b:
        if a.get(k) != b.get(k):
            changes[k] = {"from": a.get(k), "to": b.get(k)}
    return changes


def parse_strategy_question(
    question: str,
    prior_spec: Optional[StrategySpec] = None,
) -> Tuple[StrategySpec, Dict[str, Any], str]:
    """Returns (spec, diff, mode) where mode is create|mutate_costs|view_metrics."""
    q = (question or "").strip()
    if not q:
        raise StrategyParseError("Question required.")

    if _is_view_only(q):
        if prior_spec is None:
            raise StrategyParseError(
                "No prior backtest to show metrics for. "
                'Example: "Backtest a 20/50 SMA crossover on NVDA since 2020."'
            )
        return prior_spec, {}, "view_metrics"

    ticker = _ticker(q, prior_spec)
    if not ticker:
        raise StrategyParseError(
            'Ticker required. Example: "Backtest a 20/50 SMA crossover on NVDA since 2020."'
        )

    costs = _costs(q)
    windows = _windows(q)
    start = _start_year(q)

    if prior_spec is None:
        if windows is None:
            windows = (20, 50)
        if start is None:
            start = "2020-01-01"
        if "sma" not in q.lower() and "crossover" not in q.lower() and "backtest" not in q.lower():
            raise StrategyParseError(
                'Strategy required. Example: "Backtest a 20/50 SMA crossover on NVDA since 2020."'
            )
        comm, slip = costs if costs else (0.0, 0.0)
        spec = StrategySpec(
            ticker=ticker,
            kind=StrategyKind.SMA_CROSSOVER,
            strategy=SmaCrossoverParams(fast_window=windows[0], slow_window=windows[1]),
            start=start,
            commission_bps=comm,
            slippage_bps=slip,
            initial_cash=10_000.0,
        )
        return spec, spec_diff(None, spec), "create"

    # Follow-up mutate
    data = prior_spec.model_dump()
    data["ticker"] = ticker
    mode = "mutate"
    if costs is not None:
        data["commission_bps"], data["slippage_bps"] = costs
        mode = "mutate_costs"
    if windows is not None:
        data["strategy"] = {"fast_window": windows[0], "slow_window": windows[1]}
    if start is not None:
        data["start"] = start
    spec = StrategySpec.model_validate(data)
    return spec, spec_diff(prior_spec, spec), mode
