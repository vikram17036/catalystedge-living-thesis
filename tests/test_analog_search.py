"""Golden / unit tests for analog_search_v1 locked math."""

from __future__ import annotations

import math

import pytest

from stocksense.core.contracts import AnalogSpec
from stocksense.research.analog_search import (
    _euclidean,
    _lookback_returns,
    _windows_overlap,
    _zscore_window,
    run_analog_search,
)
from stocksense.research.event_study import PriceSeries


def _series_from_closes(closes: list[float], start: str = "2020-01-01") -> PriceSeries:
    """Build weekday-ish ISO dates for len(closes) sessions."""
    # Simple sequential calendar dates (engine only needs sorted ISO strings)
    from datetime import date, timedelta

    d0 = date.fromisoformat(start)
    pairs = []
    d = d0
    for c in closes:
        # skip weekends for slightly realistic spacing
        while d.weekday() >= 5:
            d += timedelta(days=1)
        pairs.append((d.isoformat(), c))
        d += timedelta(days=1)
    return PriceSeries.from_pairs(pairs, source="fixture", mode="adjusted_close")


def test_zscore_within_window_zero_mean_unit_scale():
    v = _zscore_window([1.0, 2.0, 3.0])
    assert abs(sum(v)) < 1e-9
    # population std of [1,2,3] = sqrt(2/3)
    std = math.sqrt(2.0 / 3.0)
    assert abs(v[0] - (1 - 2) / std) < 1e-9


def test_zscore_zero_std_is_zero_vector():
    assert _zscore_window([0.05, 0.05, 0.05]) == (0.0, 0.0, 0.0)


def test_euclidean_identical_is_zero():
    a = _zscore_window([0.01, -0.02, 0.03, 0.0, -0.01])
    assert _euclidean(a, a) == 0.0


def test_forward_return_formula_and_ranking():
    """Distinct twin of the target shape earlier in history; neighbors embargoed."""
    # Build returns pattern: ... noise ... then SHAPE ... gap ... SHAPE(target)
    # Use closes so returns are exact.
    L, P, K = 4, 2, 2

    def closes_from_returns(r0: float, rets: list[float]) -> list[float]:
        out = [r0]
        for r in rets:
            out.append(out[-1] * (1.0 + r))
        return out

    shape = [0.02, -0.01, 0.03, -0.02]  # L returns
    # Early twin ending far before target
    early = [0.0] * 10 + shape + [0.01, 0.02]  # +P forwards after twin end
    # Neighbors of twin (shift by 1) — should be embargoed if twin selected
    # Mid filler so no overlap with target
    mid = [0.001] * 20
    # Target shape at end + need P after? Target is last day — no forward on target
    # Target lookback = last L returns; series ends at target endpoint
    target_block = shape  # last L returns
    all_rets = early + mid + target_block
    closes = closes_from_returns(100.0, all_rets)
    prices = _series_from_closes(closes)

    spec = AnalogSpec(ticker="NVDA", lookback=L, post_window=P, top_k=K)
    result = run_analog_search(spec, prices)

    assert result.matches_returned >= 1
    # Nearest should be distance ~0 (identical z-scored shape)
    assert result.matches[0].distance < 1e-9

    # Forward for first match: close(C+P)/close(C)-1
    m0 = result.matches[0]
    idx = prices.index_map()[m0.endpoint]
    expected_fwd = prices.closes[idx + P] / prices.closes[idx] - 1.0
    assert abs(m0.forward_return - expected_fwd) < 1e-12

    # Aggregates over selected only
    fwds = [m.forward_return for m in result.matches]
    assert result.forward_mean == pytest.approx(sum(fwds) / len(fwds))
    assert result.positive_hit_rate == pytest.approx(
        sum(1 for f in fwds if f > 0) / len(fwds)
    )


def test_overlap_embargo_skips_neighbors():
    L = 5
    # Two endpoints one day apart always overlap for L>=1
    assert _windows_overlap(20, 21, L) is True
    assert _windows_overlap(20, 20 + L + 1, L) is False


def test_no_lookahead_candidate_post_before_target_start():
    L, P = 5, 3
    # Enough history; target at end
    closes = [100.0 + i * 0.1 for i in range(80)]
    prices = _series_from_closes(closes)
    spec = AnalogSpec(ticker="NVDA", lookback=L, post_window=P, top_k=3)
    result = run_analog_search(spec, prices)
    target_idx = len(prices.dates) - 1
    target_start = target_idx - L
    for m in result.matches:
        c = prices.index_map()[m.endpoint]
        assert c + P < target_start


def test_post_window_change_keeps_eligible_ranking_order():
    """Similarity uses lookback only; increasing P may drop ineligible but order among survivors holds."""
    L = 4
    closes = [100.0]
    # varied returns
    import random

    rng = random.Random(42)
    for _ in range(120):
        closes.append(closes[-1] * (1.0 + rng.uniform(-0.02, 0.02)))
    prices = _series_from_closes(closes)

    r5 = run_analog_search(
        AnalogSpec(ticker="NVDA", lookback=L, post_window=5, top_k=3), prices
    )
    r10 = run_analog_search(
        AnalogSpec(ticker="NVDA", lookback=L, post_window=10, top_k=3), prices
    )
    # Endpoints that remain eligible under P=10 should appear in same relative order as in P=5
    ends5 = [m.endpoint for m in r5.matches]
    ends10 = [m.endpoint for m in r10.matches]
    survivors = [e for e in ends5 if e in ends10]
    filtered10 = [e for e in ends10 if e in ends5]
    assert survivors == filtered10


def test_sample_accounting_fields_present():
    closes = [100.0 + i * 0.05 for i in range(60)]
    prices = _series_from_closes(closes)
    result = run_analog_search(
        AnalogSpec(ticker="NVDA", lookback=5, post_window=2, top_k=3), prices
    )
    assert result.candidate_windows > 0
    assert result.eligible_windows >= result.matches_returned
    assert result.excluded_lookahead >= 0
    assert result.excluded_overlap >= 0
    assert result.excluded_future_coverage >= 0
    assert result.reproducibility.engine_version == "analog_search_v1"
    assert result.reproducibility.target_end == prices.dates[-1]
    assert result.reproducibility.price_data_hash.startswith("sha256:")


def test_lookback_returns_length():
    closes = [100.0, 101.0, 102.0, 101.0, 103.0, 104.0]
    prices = _series_from_closes(closes)
    rets = [None]
    for i in range(1, len(prices.closes)):
        rets.append(prices.closes[i] / prices.closes[i - 1] - 1.0)
    chunk = _lookback_returns(rets, 5, 4)
    assert chunk is not None and len(chunk) == 4
