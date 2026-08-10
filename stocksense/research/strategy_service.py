"""Application layer for Strategy Lab backtests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from stocksense.core.contracts import Evidence, EvidenceType, StrategySpec
from stocksense.core.evidence_ledger import _eid
from stocksense.research.event_study import PriceSeries
from stocksense.research.prices import fetch_adjusted_closes
from stocksense.research.event_calendar import CalendarEvent
from stocksense.research.strategy_lab import run_backtest
from stocksense.research.strategy_parse import StrategyParseError, parse_strategy_question


def _fetch_prices_for_spec(spec: StrategySpec) -> PriceSeries:
    """Fetch adjusted closes with SMA warm-up padding before start."""
    # Reuse yfinance via a synthetic event span
    start = spec.start
    end = spec.end or datetime.now(timezone.utc).date().isoformat()
    pad_days = max(spec.strategy.slow_window * 3, 90)
    # Build fake calendar endpoints for fetch_adjusted_closes padding logic
    events = [
        CalendarEvent(date=start, decision="hold"),
        CalendarEvent(date=end, decision="hold"),
    ]
    # fetch_adjusted_closes pads by pre/post window — pass slow_window as pre
    return fetch_adjusted_closes(
        spec.ticker,
        events,
        pre_window=pad_days,
        post_window=5,
    )


def from_backtest_result(
    result,
    *,
    observed_at: Optional[datetime] = None,
) -> Evidence:
    ts = observed_at or datetime.now(timezone.utc)
    spec = result.spec
    m = result.metrics
    repro = result.reproducibility
    eid = _eid(
        spec.ticker,
        "backtest",
        spec.kind.value,
        str(spec.strategy.fast_window),
        str(spec.strategy.slow_window),
        repro.price_data_hash,
        str(spec.commission_bps),
        str(spec.slippage_bps),
    )
    return Evidence(
        id=eid,
        type=EvidenceType.BACKTEST,
        entity=spec.ticker,
        observed_at=ts,
        available_at=ts,
        source="catalystedge:strategy-lab",
        metric="backtest_summary",
        value=m.total_return,
        data={
            "ticker": spec.ticker,
            "kind": spec.kind.value,
            "fast_window": spec.strategy.fast_window,
            "slow_window": spec.strategy.slow_window,
            "commission_bps": spec.commission_bps,
            "slippage_bps": spec.slippage_bps,
            "metrics": m.model_dump(),
            "n_trades": m.n_trades,
            "engine_version": repro.engine_version,
            "price_data_hash": repro.price_data_hash,
        },
        provenance={
            "engine_version": repro.engine_version,
            "price_data_hash": repro.price_data_hash,
            "price_mode": repro.price_mode,
        },
    )


def _deterministic_interpret(result, evidence_id: str) -> Dict[str, Any]:
    m = result.metrics
    spec = result.spec
    summary = (
        f"{spec.ticker} {spec.strategy.fast_window}/{spec.strategy.slow_window} SMA crossover: "
        f"net return {m.total_return*100:.2f}%, max drawdown {m.max_drawdown*100:.2f}%, "
        f"hit rate {(m.hit_rate*100) if m.hit_rate is not None else 0:.1f}% "
        f"over {m.n_trades} trades. "
        f"Gross {m.gross_return*100:.2f}% → commission impact {m.commission_impact*100:.2f}% → "
        f"slippage impact {m.slippage_impact*100:.2f}% → net."
    )
    return {
        "mode": "deterministic",
        "summary": summary,
        "observations": [
            {
                "text": summary,
                "evidence_id": evidence_id,
                "metrics": ["total_return", "max_drawdown", "hit_rate"],
            }
        ],
        "caveats": [
            "Long-only SMA crossover on adjusted close; signal t / fill t+1.",
            "Past performance is not predictive.",
        ],
    }


def run_strategy_request(
    question: str,
    prior_spec: Optional[StrategySpec] = None,
    prior_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    spec, diff, mode = parse_strategy_question(question, prior_spec)

    if mode == "view_metrics":
        if not prior_result:
            raise StrategyParseError("No prior result cached to display metrics.")
        return {
            "prior_spec": prior_spec.model_dump() if prior_spec else None,
            "spec": spec.model_dump(),
            "spec_diff": {},
            "mode": mode,
            "result": prior_result,
            "interpretation": {
                "mode": "view",
                "summary": (
                    f"Max drawdown {prior_result['metrics']['max_drawdown']*100:.2f}%; "
                    f"hit rate {(prior_result['metrics']['hit_rate'] or 0)*100:.1f}%."
                ),
                "observations": [],
                "caveats": ["No strategy mutation — displaying existing BacktestResult metrics."],
            },
            "evidence_ledger": [],
        }

    prices = _fetch_prices_for_spec(spec)
    result = run_backtest(spec, prices)
    evidence = from_backtest_result(result)
    interpretation = _deterministic_interpret(result, evidence.id)

    return {
        "prior_spec": prior_spec.model_dump() if prior_spec else None,
        "spec": spec.model_dump(),
        "spec_diff": diff,
        "mode": mode,
        "result": result.model_dump(mode="json"),
        "interpretation": interpretation,
        "evidence_ledger": [evidence.model_dump(mode="json")],
    }


__all__ = ["run_strategy_request", "StrategyParseError"]
