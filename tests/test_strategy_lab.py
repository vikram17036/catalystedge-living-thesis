"""Golden SMA backtest — hand-verified lifecycle + counterfactual costs."""

from __future__ import annotations

import pytest

from stocksense.core.contracts import SmaCrossoverParams, StrategySpec
from stocksense.research.event_study import PriceSeries
from stocksense.research.strategy_lab import run_backtest

# ---------------------------------------------------------------------------
# Tiny series: fast=2, slow=3
# closes: 100,100,100,110,120,130,120,110,100,100
# ---------------------------------------------------------------------------
# SMA2[i], SMA3[i]:
# i=2: 100, 100
# i=3: 105, 103.333...  ENTRY (105>103.33 and 100<=100) → fill i=4 @120
# i=7: 115, 120         EXIT  (115<120 and 125>=123.33) → fill i=8 @100
#
# Zero costs, cash=12000:
#   shares = 12000/120 = 100
#   exit proceeds = 100*100 = 10000
#   pnl = 10000 - 12000 = -2000
#   trade_return = -2000/12000 = -1/6
#   final equity = 10000 → total_return = 10000/12000 - 1 = -1/6
# ---------------------------------------------------------------------------

DATES = [
    "2020-01-02",
    "2020-01-03",
    "2020-01-06",
    "2020-01-07",
    "2020-01-08",
    "2020-01-09",
    "2020-01-10",
    "2020-01-13",
    "2020-01-14",
    "2020-01-15",
]
CLOSES = [100.0, 100.0, 100.0, 110.0, 120.0, 130.0, 120.0, 110.0, 100.0, 100.0]


def _prices() -> PriceSeries:
    return PriceSeries.from_pairs(list(zip(DATES, CLOSES)), source="fixture")


def _spec(**kwargs) -> StrategySpec:
    base = dict(
        ticker="TEST",
        strategy=SmaCrossoverParams(fast_window=2, slow_window=3),
        start="2020-01-06",  # index 2
        end="2020-01-15",
        commission_bps=0.0,
        slippage_bps=0.0,
        initial_cash=12_000.0,
    )
    base.update(kwargs)
    return StrategySpec(**base)


def test_golden_zero_cost_trade_lifecycle():
    result = run_backtest(_spec(), _prices())
    assert result.metrics.n_trades == 1
    t = result.trades[0]

    assert t.entry_signal_date == "2020-01-07"  # i=3
    assert t.entry_exec_date == "2020-01-08"  # i=4
    assert t.entry_market_price == pytest.approx(120.0)
    assert t.entry_effective_price == pytest.approx(120.0)
    assert t.entry_commission == pytest.approx(0.0)
    assert t.shares == pytest.approx(100.0)

    assert t.exit_signal_date == "2020-01-13"  # i=7
    assert t.exit_exec_date == "2020-01-14"  # i=8
    assert t.exit_market_price == pytest.approx(100.0)
    assert t.exit_effective_price == pytest.approx(100.0)
    assert t.exit_commission == pytest.approx(0.0)
    assert t.forced_end_close is False

    assert t.pnl == pytest.approx(-2000.0)
    assert t.trade_return == pytest.approx(-2000.0 / 12_000.0)

    assert result.metrics.total_return == pytest.approx(-1.0 / 6.0)
    assert result.metrics.gross_return == pytest.approx(-1.0 / 6.0)
    assert result.metrics.hit_rate == pytest.approx(0.0)


def test_golden_entry_sizing_with_commission():
    """shares = cash / (eff * (1+comm_rate)); cash after ≈ 0."""
    # 10 bps commission, 0 slippage; entry at 120
    # eff=120, rate=0.001
    # shares = 12000 / (120 * 1.001) = 12000 / 120.12
    shares = 12_000.0 / (120.0 * 1.001)
    notional = shares * 120.0
    entry_comm = notional * 0.001

    result = run_backtest(_spec(commission_bps=10.0, slippage_bps=0.0), _prices())
    t = result.trades[0]
    assert t.shares == pytest.approx(shares)
    assert t.entry_commission == pytest.approx(entry_comm)
    assert t.entry_effective_price == pytest.approx(120.0)


def test_golden_slippage_on_entry_and_exit():
    # 0 commission, 100 bps slippage
    # entry eff = 120 * 1.01 = 121.2
    # shares = 12000 / 121.2
    # exit eff = 100 * 0.99 = 99
    slip = 100.0
    result = run_backtest(_spec(commission_bps=0.0, slippage_bps=slip), _prices())
    t = result.trades[0]
    assert t.entry_effective_price == pytest.approx(120.0 * 1.01)
    assert t.exit_effective_price == pytest.approx(100.0 * 0.99)
    shares = 12_000.0 / (120.0 * 1.01)
    assert t.shares == pytest.approx(shares)
    cost_basis = shares * (120.0 * 1.01)
    proceeds = shares * (100.0 * 0.99)
    assert t.pnl == pytest.approx(proceeds - cost_basis)


def test_counterfactual_impacts_reconcile():
    result = run_backtest(
        _spec(commission_bps=10.0, slippage_bps=20.0), _prices()
    )
    m = result.metrics
    assert m.commission_impact == pytest.approx(m.gross_return - m.commission_only_return)
    assert m.slippage_impact == pytest.approx(m.commission_only_return - m.total_return)


def test_byte_equivalent_determinism():
    spec = _spec(commission_bps=5.0, slippage_bps=2.0)
    a = run_backtest(spec, _prices())
    b = run_backtest(spec, _prices())
    assert a.model_dump() == b.model_dump()


def test_signal_t_never_fills_same_bar():
    t = run_backtest(_spec(), _prices()).trades[0]
    assert t.entry_signal_date < t.entry_exec_date
    assert t.exit_signal_date < t.exit_exec_date


def test_max_drawdown_from_daily_equity():
    result = run_backtest(_spec(), _prices())
    eqs = [p.equity for p in result.equity_curve]
    peak = eqs[0]
    expected_dd = 0.0
    for e in eqs:
        peak = max(peak, e)
        expected_dd = max(expected_dd, (peak - e) / peak if peak else 0.0)
    assert result.metrics.max_drawdown == pytest.approx(expected_dd)


def test_forced_end_close_when_still_long():
    # End before exit fill: exit signal i=7 (2020-01-13), fill i=8.
    # End on 2020-01-13 → still long after signal day → force same-day liquidate.
    result = run_backtest(_spec(end="2020-01-13"), _prices())
    assert result.metrics.n_trades == 1
    t = result.trades[0]
    assert t.forced_end_close is True
    assert t.exit_exec_date == "2020-01-13"
    assert t.exit_market_price == pytest.approx(110.0)


def test_fast_must_be_lt_slow():
    with pytest.raises(Exception):
        StrategySpec(
            ticker="X",
            strategy=SmaCrossoverParams(fast_window=50, slow_window=20),
            start="2020-01-01",
        )
