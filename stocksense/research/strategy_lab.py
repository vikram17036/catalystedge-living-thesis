"""Pure SMA crossover backtest engine.

StrategySpec + PriceSeries → BacktestResult.
No UUID, datetime.now(), LLM, network, evidence IDs, or exec().
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from stocksense.core.contracts import (
    BacktestMetrics,
    BacktestReproducibility,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    StrategyKind,
    StrategySpec,
)
from stocksense.research.event_study import PriceSeries

ENGINE_VERSION = "strategy_lab_v1"


def _sma(closes: Tuple[float, ...], window: int, i: int) -> Optional[float]:
    if i + 1 < window:
        return None
    chunk = closes[i - window + 1 : i + 1]
    return sum(chunk) / window


def _max_drawdown(equities: List[float]) -> float:
    if not equities:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (peak - e) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _hit_rate(trades: List[BacktestTrade]) -> Optional[float]:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return None
    wins = sum(1 for t in closed if (t.pnl or 0.0) > 0)
    return wins / len(closed)


def _run_single(
    spec: StrategySpec,
    prices: PriceSeries,
) -> Tuple[List[BacktestTrade], List[EquityPoint], float]:
    """Run one cost regime. Returns trades, equity_curve (from start), final_return."""
    if spec.kind != StrategyKind.SMA_CROSSOVER:
        raise ValueError("only sma_crossover supported")

    fast_w = spec.strategy.fast_window
    slow_w = spec.strategy.slow_window
    slip_r = spec.slippage_bps / 10_000.0
    comm_r = spec.commission_bps / 10_000.0

    dates = prices.dates
    closes = prices.closes
    n = len(dates)

    # Index bounds for reporting window
    start_i = 0
    for i, d in enumerate(dates):
        if d >= spec.start:
            start_i = i
            break
    else:
        raise ValueError("start date after all price data")

    end_i = n - 1
    if spec.end:
        for i, d in enumerate(dates):
            if d <= spec.end:
                end_i = i
            else:
                break

    cash = float(spec.initial_cash)
    shares = 0.0
    in_pos = False
    entry_signal_date: Optional[str] = None
    entry_exec_date: Optional[str] = None
    entry_market = 0.0
    entry_eff = 0.0
    entry_comm = 0.0
    pending_entry_signal: Optional[int] = None  # exec index
    pending_exit_signal: Optional[int] = None
    pending_entry_sig_date: Optional[str] = None
    pending_exit_sig_date: Optional[str] = None

    trades: List[BacktestTrade] = []
    equity_curve: List[EquityPoint] = []

    # Need i-1 for crossover → start scanning from slow_w (first index with valid slow SMA)
    first_signal_i = slow_w  # index where slow SMA first exists; compare with i-1 needs i>=slow_w

    for i in range(n):
        # Execute pending fills at this bar (from signals at i-1)
        if pending_entry_signal is not None and i == pending_entry_signal and not in_pos:
            P = closes[i]
            eff = P * (1.0 + slip_r)
            # size including commission
            denom = eff * (1.0 + comm_r)
            sh = cash / denom if denom > 0 else 0.0
            notional = sh * eff
            commission = notional * comm_r
            cash = cash - notional - commission
            shares = sh
            in_pos = True
            entry_signal_date = pending_entry_sig_date or dates[i]
            entry_exec_date = dates[i]
            entry_market = P
            entry_eff = eff
            entry_comm = commission
            pending_entry_signal = None
            pending_entry_sig_date = None

        if pending_exit_signal is not None and i == pending_exit_signal and in_pos:
            P = closes[i]
            eff = P * (1.0 - slip_r)
            gross = shares * eff
            commission = gross * comm_r
            cash = gross - commission
            pnl = cash - spec.initial_cash  # wrong for multi-trade — fix below
            # Per-trade PnL: vs cash deployed at entry (notional + entry commission)
            cost_basis = shares * entry_eff + entry_comm
            pnl = (gross - commission) - cost_basis
            trade_ret = pnl / cost_basis if cost_basis else 0.0
            trades.append(
                BacktestTrade(
                    entry_signal_date=entry_signal_date or "",
                    entry_exec_date=entry_exec_date or "",
                    entry_market_price=entry_market,
                    entry_effective_price=entry_eff,
                    entry_commission=entry_comm,
                    shares=shares,
                    exit_signal_date=pending_exit_sig_date,
                    exit_exec_date=dates[i],
                    exit_market_price=P,
                    exit_effective_price=eff,
                    exit_commission=commission,
                    pnl=pnl,
                    trade_return=trade_ret,
                    forced_end_close=False,
                )
            )
            shares = 0.0
            in_pos = False
            pending_exit_signal = None
            pending_exit_sig_date = None

        # Force liquidate on final day if still long (exception to t+1)
        if i == end_i and in_pos:
            P = closes[i]
            eff = P * (1.0 - slip_r)
            gross = shares * eff
            commission = gross * comm_r
            proceeds = gross - commission
            cost_basis = shares * entry_eff + entry_comm
            pnl = proceeds - cost_basis
            trade_ret = pnl / cost_basis if cost_basis else 0.0
            cash = proceeds
            trades.append(
                BacktestTrade(
                    entry_signal_date=entry_signal_date or "",
                    entry_exec_date=entry_exec_date or "",
                    entry_market_price=entry_market,
                    entry_effective_price=entry_eff,
                    entry_commission=entry_comm,
                    shares=shares,
                    exit_signal_date=dates[i],
                    exit_exec_date=dates[i],
                    exit_market_price=P,
                    exit_effective_price=eff,
                    exit_commission=commission,
                    pnl=pnl,
                    trade_return=trade_ret,
                    forced_end_close=True,
                )
            )
            shares = 0.0
            in_pos = False
            pending_exit_signal = None

        # Signals only inside [start_i, end_i], and not on last bar for normal t+1
        # (signal on end_i would need end_i+1 which doesn't exist — skip)
        if (
            i >= first_signal_i
            and i >= start_i
            and i < end_i
            and pending_entry_signal is None
            and pending_exit_signal is None
        ):
            f = _sma(closes, fast_w, i)
            s = _sma(closes, slow_w, i)
            f_prev = _sma(closes, fast_w, i - 1)
            s_prev = _sma(closes, slow_w, i - 1)
            if f is not None and s is not None and f_prev is not None and s_prev is not None:
                if (not in_pos) and f > s and f_prev <= s_prev:
                    pending_entry_signal = i + 1
                    pending_entry_sig_date = dates[i]
                elif in_pos and f < s and f_prev >= s_prev:
                    pending_exit_signal = i + 1
                    pending_exit_sig_date = dates[i]

        # Daily equity from start_i..end_i (after fills this bar)
        if start_i <= i <= end_i:
            if in_pos:
                equity = cash + shares * closes[i]
            else:
                equity = cash
            equity_curve.append(
                EquityPoint(
                    date=dates[i],
                    equity=equity,
                    in_position=in_pos,
                    cash=cash,
                )
            )

    initial = float(spec.initial_cash)
    final_eq = equity_curve[-1].equity if equity_curve else initial
    total_return = (final_eq / initial) - 1.0 if initial else 0.0
    return trades, equity_curve, total_return


def run_backtest(spec: StrategySpec, prices: PriceSeries) -> BacktestResult:
    """Pure backtest with counterfactual gross / commission-only / net."""
    # Net (as specified)
    trades, equity, net_ret = _run_single(spec, prices)

    # A: gross
    gross_spec = spec.model_copy(update={"commission_bps": 0.0, "slippage_bps": 0.0})
    _, _, gross_ret = _run_single(gross_spec, prices)

    # B: commission only
    comm_only_spec = spec.model_copy(update={"slippage_bps": 0.0})
    _, _, comm_only_ret = _run_single(comm_only_spec, prices)

    metrics = BacktestMetrics(
        total_return=net_ret,
        gross_return=gross_ret,
        commission_only_return=comm_only_ret,
        commission_impact=gross_ret - comm_only_ret,
        slippage_impact=comm_only_ret - net_ret,
        max_drawdown=_max_drawdown([p.equity for p in equity]),
        hit_rate=_hit_rate(trades),
        n_trades=len(trades),
    )

    repro = BacktestReproducibility(
        engine_version=ENGINE_VERSION,
        price_source=prices.source,
        price_mode=prices.mode,
        price_start=prices.start,
        price_end=prices.end,
        price_data_hash=prices.fingerprint(),
    )

    return BacktestResult(
        spec=spec,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        reproducibility=repro,
    )
