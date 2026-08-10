"""Deterministic historical analog search.

Pure: AnalogSpec + PriceSeries → AnalogResult.
No UUIDs, no datetime.now(), no evidence IDs, no LLM, no I/O.

Locked math (v1):
  prices → daily simple returns → L-vector → within-window z-score → Euclidean
  overlap embargo on lookback windows
  candidate_post_end < target_start (no lookahead)
  forward_return = close(C+post) / close(C) - 1
"""

from __future__ import annotations

import math
import statistics
from typing import List, Optional, Sequence, Tuple

from stocksense.core.contracts import (
    AnalogMatch,
    AnalogReproducibility,
    AnalogResult,
    AnalogSpec,
)
from stocksense.research.event_study import PriceSeries

ENGINE_VERSION = "analog_search_v1"


def _daily_returns(closes: Sequence[float]) -> List[Optional[float]]:
    """Index-aligned with closes; r[0]=None, r[i]=close[i]/close[i-1]-1."""
    out: List[Optional[float]] = [None]
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            out.append(None)
        else:
            out.append(closes[i] / prev - 1.0)
    return out


def _zscore_window(vals: Sequence[float]) -> Tuple[float, ...]:
    """Within-window z-score. Zero-std → zero vector (shape undefined → neutral)."""
    if not vals:
        return tuple()
    mu = statistics.mean(vals)
    if len(vals) == 1:
        return (0.0,)
    var = statistics.pvariance(vals)  # population variance of the window
    std = math.sqrt(var)
    if std == 0.0:
        return tuple(0.0 for _ in vals)
    return tuple((v - mu) / std for v in vals)


def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector length mismatch")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _lookback_returns(
    returns: Sequence[Optional[float]], endpoint_idx: int, lookback: int
) -> Optional[List[float]]:
    """L returns ending at endpoint_idx inclusive. Needs indices [ep-L+1 .. ep]."""
    start = endpoint_idx - lookback + 1
    if start < 1 or endpoint_idx >= len(returns):
        return None
    chunk: List[float] = []
    for i in range(start, endpoint_idx + 1):
        r = returns[i]
        if r is None:
            return None
        chunk.append(r)
    if len(chunk) != lookback:
        return None
    return chunk


def _windows_overlap(a_end: int, b_end: int, lookback: int) -> bool:
    """Lookback price windows [end-L, end] inclusive overlap."""
    a0, a1 = a_end - lookback, a_end
    b0, b1 = b_end - lookback, b_end
    return not (a1 < b0 or b1 < a0)


def run_analog_search(spec: AnalogSpec, prices: PriceSeries) -> AnalogResult:
    """Rank distinct historical episodes by shape distance; compute forward outcomes."""
    L = spec.lookback
    P = spec.post_window
    K = spec.top_k
    dates = prices.dates
    closes = prices.closes
    n = len(dates)
    if n < L + P + 2:
        raise ValueError("Insufficient price history for lookback + post_window")

    returns = _daily_returns(closes)

    # Resolve target endpoint
    if spec.as_of:
        if spec.as_of not in prices.index_map():
            # next session on/after as_of, else last
            target_idx = None
            for i, d in enumerate(dates):
                if d >= spec.as_of:
                    target_idx = i
                    break
            if target_idx is None:
                target_idx = n - 1
        else:
            target_idx = prices.index_map()[spec.as_of]
    else:
        target_idx = n - 1

    target_vec_raw = _lookback_returns(returns, target_idx, L)
    if target_vec_raw is None:
        raise ValueError("Target lookback incomplete")
    target_vec = _zscore_window(target_vec_raw)
    target_end = dates[target_idx]
    target_start_idx = target_idx - L  # first price index of target lookback

    candidate_windows = 0
    eligible: List[Tuple[float, int, float]] = []  # distance, endpoint_idx, fwd
    excluded_future_coverage = 0
    excluded_lookahead = 0

    # Candidate endpoints: need lookback + post coverage; post end before target_start
    max_c = n - 1 - P
    for c in range(L, max_c + 1):
        candidate_windows += 1
        post_end = c + P
        if post_end >= n:
            excluded_future_coverage += 1
            continue
        if post_end >= target_start_idx:
            excluded_lookahead += 1
            continue
        raw = _lookback_returns(returns, c, L)
        if raw is None:
            excluded_future_coverage += 1
            continue
        dist = _euclidean(target_vec, _zscore_window(raw))
        fwd = closes[post_end] / closes[c] - 1.0
        eligible.append((dist, c, fwd))

    eligible.sort(key=lambda t: (t[0], t[1]))
    eligible_windows = len(eligible)

    selected: List[Tuple[float, int, float]] = []
    excluded_overlap = 0
    for dist, c, fwd in eligible:
        if any(_windows_overlap(c, s[1], L) for s in selected):
            excluded_overlap += 1
            continue
        selected.append((dist, c, fwd))
        if len(selected) >= K:
            break

    matches: List[AnalogMatch] = []
    fwds: List[float] = []
    for dist, c, fwd in selected:
        lb_start = c - L
        matches.append(
            AnalogMatch(
                endpoint=dates[c],
                lookback_start=dates[lb_start],
                lookback_end=dates[c],
                distance=float(dist),
                forward_return=float(fwd),
            )
        )
        fwds.append(fwd)

    forward_mean = float(statistics.mean(fwds)) if fwds else None
    forward_median = float(statistics.median(fwds)) if fwds else None
    positive_hit_rate = (
        float(sum(1 for v in fwds if v > 0) / len(fwds)) if fwds else None
    )

    repro = AnalogReproducibility(
        engine_version=ENGINE_VERSION,
        price_source=prices.source,
        price_mode=prices.mode,
        price_start=prices.start,
        price_end=prices.end,
        price_data_hash=prices.fingerprint(),
        as_of=spec.as_of or target_end,
        target_end=target_end,
        lookback=L,
        post_window=P,
        top_k=K,
    )

    return AnalogResult(
        spec=spec,
        candidate_windows=candidate_windows,
        eligible_windows=eligible_windows,
        matches_returned=len(matches),
        excluded_overlap=excluded_overlap,
        excluded_future_coverage=excluded_future_coverage,
        excluded_lookahead=excluded_lookahead,
        forward_mean=forward_mean,
        forward_median=forward_median,
        positive_hit_rate=positive_hit_rate,
        matches=matches,
        reproducibility=repro,
    )


__all__ = ["ENGINE_VERSION", "run_analog_search"]
